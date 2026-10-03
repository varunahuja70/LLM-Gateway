"""Gateway Load and Overhead Benchmark.

Measures proxy path overhead against the mock provider (0ms upstream network latency).
Calculates p50, p90, p95, p99 latencies, throughput, and error rates.
"""

import asyncio
import base64
import os
import statistics
import time
from typing import Any

# Ensure master key and test env are set before any app imports
os.environ["GATEWAY_MASTER_KEY"] = base64.b64encode(b"0123456789abcdef0123456789abcdef").decode()
os.environ["ENV"] = "test"
os.environ["PUBLIC_URL"] = "http://localhost:3000"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.admin.auth import reset_rate_limits
from app.core.security import hash_key
from app.db.base import Base, uuid7
from app.db.models.project import GatewayKey, Project, ProjectConfig
from app.db.models.provider import ModelPrice
from app.db.session import get_db_session
from app.deps import clear_gateway_key_memory_cache
from app.main import create_app
from app.services.request_logger import request_logger


async def setup_benchmark_app() -> tuple[AsyncClient, str]:
    valid_key = base64.b64encode(b"0123456789abcdef0123456789abcdef").decode()
    os.environ["GATEWAY_MASTER_KEY"] = valid_key
    os.environ["ENV"] = "test"
    os.environ["PUBLIC_URL"] = "http://localhost:3000"

    import app.config as config_module

    config_module._settings = None
    reset_rate_limits()
    clear_gateway_key_memory_cache()

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    raw_key = "lgw_benchkey1234567890abcdef1234567890abcdef1"
    key_hash = hash_key(raw_key)

    project_id = uuid7()
    project = Project(
        id=project_id,
        name="Benchmark Project",
        slug="benchmark-project",
        description="Load testing gateway overhead",
    )
    config = ProjectConfig(
        project_id=project_id,
        cache_enabled=False,  # Disable cache so every request tests full proxy overhead
        cache_ttl_s=3600,
        rpm_limit=100000,
        log_content=False,
    )
    gw_key = GatewayKey(
        project_id=project_id,
        name="bench-key",
        key_hash=key_hash,
        prefix="lgw_benc",
    )
    import datetime as dt

    price = ModelPrice(
        provider="mock",
        model="gpt-4o-mini",
        input_micro_usd_per_mtok=150,
        output_micro_usd_per_mtok=600,
        source_url="https://example.com/prices",
        verified_on=dt.date.today(),
        is_seed=True,
    )

    async with session_factory() as session:
        session.add_all([project, config, gw_key, price])
        await session.commit()

    app = create_app()

    async def get_test_db() -> AsyncSession:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = get_test_db

    # Point session makers to the in-memory SQLite session_factory
    import app.db.session as db_session_module
    db_session_module._sessionmaker = session_factory
    request_logger._sessionmaker = session_factory

    transport = ASGITransport(app=app)
    client = AsyncClient(transport=transport, base_url="http://gateway.test")

    return client, raw_key


async def run_benchmark(
    target_rps: int = 100,
    duration_seconds: int = 20,
    concurrency: int = 20,
) -> dict[str, Any]:
    client, raw_key = await setup_benchmark_app()

    payload = {
        "model": "mock/gpt-4o-mini",
        "messages": [
            {"role": "user", "content": "Benchmark gateway proxy latency and token overhead."}
        ],
    }
    headers = {"Authorization": f"Bearer {raw_key}"}

    # Warmup
    for _ in range(30):
        resp = await client.post("/v1/chat/completions", json=payload, headers=headers)
        assert resp.status_code == 200

    latencies_ms: list[float] = []
    errors = 0
    total_requests = 0

    start_time = time.perf_counter()
    end_time = start_time + duration_seconds

    # Semaphore to bound concurrent in-flight requests
    sem = asyncio.Semaphore(concurrency)

    async def worker() -> None:
        nonlocal total_requests, errors
        while time.perf_counter() < end_time:
            async with sem:
                t0 = time.perf_counter()
                try:
                    resp = await client.post("/v1/chat/completions", json=payload, headers=headers)
                    t1 = time.perf_counter()
                    duration_ms = (t1 - t0) * 1000.0
                    if resp.status_code == 200:
                        latencies_ms.append(duration_ms)
                    else:
                        errors += 1
                except Exception:
                    errors += 1
                total_requests += 1

            # Sleep slightly to throttle to approx target_rps across concurrency workers
            await asyncio.sleep(concurrency / target_rps)

    workers = [asyncio.create_task(worker()) for _ in range(concurrency)]
    await asyncio.gather(*workers)
    actual_duration = time.perf_counter() - start_time

    # Flush background logging queue
    await request_logger.flush()
    await client.aclose()

    latencies_ms.sort()
    n = len(latencies_ms)
    p50 = latencies_ms[int(n * 0.50)] if n else 0.0
    p90 = latencies_ms[int(n * 0.90)] if n else 0.0
    p95 = latencies_ms[int(n * 0.95)] if n else 0.0
    p99 = latencies_ms[int(n * 0.99)] if n else 0.0
    avg = statistics.mean(latencies_ms) if n else 0.0
    min_lat = latencies_ms[0] if n else 0.0
    max_lat = latencies_ms[-1] if n else 0.0
    rps = n / actual_duration if actual_duration > 0 else 0.0

    return {
        "total_requests": total_requests,
        "successful_requests": n,
        "errors": errors,
        "duration_seconds": round(actual_duration, 2),
        "throughput_rps": round(rps, 1),
        "latency_min_ms": round(min_lat, 2),
        "latency_p50_ms": round(p50, 2),
        "latency_p90_ms": round(p90, 2),
        "latency_p95_ms": round(p95, 2),
        "latency_p99_ms": round(p99, 2),
        "latency_max_ms": round(max_lat, 2),
        "latency_avg_ms": round(avg, 2),
    }


def main() -> None:
    print("=" * 60)
    print("Running Gateway Load and Overhead Benchmark...")
    print("Target: High throughput against Mock Provider (0ms upstream network latency)")
    print("Requirement: p95 latency overhead < 50ms")
    print("=" * 60)

    results = asyncio.run(run_benchmark(target_rps=100, duration_seconds=30, concurrency=8))

    print(f"Total Requests:       {results['total_requests']}")
    print(f"Successful Requests:  {results['successful_requests']}")
    print(f"Errors:               {results['errors']}")
    print(f"Test Duration:        {results['duration_seconds']}s")
    print(f"Throughput:           {results['throughput_rps']} req/s")
    print("-" * 60)
    print(f"Min Latency:          {results['latency_min_ms']} ms")
    print(f"Average Latency:      {results['latency_avg_ms']} ms")
    print(f"p50 Latency:          {results['latency_p50_ms']} ms")
    print(f"p90 Latency:          {results['latency_p90_ms']} ms")
    print(f"p95 Latency:          {results['latency_p95_ms']} ms  <-- Target < 50ms")
    print(f"p99 Latency:          {results['latency_p99_ms']} ms")
    print(f"Max Latency:          {results['latency_max_ms']} ms")
    print("=" * 60)

    if results["latency_p95_ms"] < 50.0 and results["errors"] == 0:
        print("OVERHEAD CRITERIA PASSED: p95 is under 50ms!")
    else:
        print("WARNING: Criteria not met!")


if __name__ == "__main__":
    main()
