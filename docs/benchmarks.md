# Gateway Overhead Benchmark (Mock Provider)

> **Important Note on Methodology**: These measurements reflect **gateway proxy overhead only**, benchmarked using an in-memory zero-latency mock provider under a synthetic workload. They measure the CPU, memory, serialization, authentication, routing, and logging overhead added by the gateway itself. They do **not** represent real-world upstream network latency from third-party APIs (such as OpenAI, Anthropic, or Google), where response latency is dominated by remote model inference times and internet transit.

## Test Environment
- **Benchmark Type**: Mock-provider gateway overhead benchmark
- **Platform**: Windows 11 / AMD/Intel 64-bit Architecture
- **Runtime**: Python 3.13+ (compatible with Python 3.13 in CI and 3.14 in local development via `uv`)
- **Application Server**: FastAPI / Starlette async ASGI pipeline
- **Provider Tested**: Deterministic Mock Provider (`mock/gpt-4o-mini`) with 0ms upstream network latency
- **Database Engine**: In-memory async SQLite engine with connection isolation
- **Authentication**: O(1) in-memory cryptographic gateway key verification with SHA-256 key hashing

---

## 1. Gateway Proxy Overhead Measurement

Overhead was measured by benchmarking the round-trip latency of the complete gateway proxy stack (request validation, authentication check, budget & rate limit evaluation, routing, mock provider execution, JSON response generation, and async non-blocking audit logging).

### Measured Results (Sustained Load Run)

| Metric | Measured Value | Target / Requirement | Status |
| :--- | :--- | :--- | :--- |
| **Total Requests** | `2,040` | - | Complete |
| **Successful Requests** | `2,040` | 100% | **100% Success** |
| **Error Count** | `0` | `0` | **0 Errors** |
| **Test Duration** | `30.02s` | >= 20s | Complete |
| **Throughput** | `68.0 req/s` | ~50-100 req/s | High sustained |
| **Minimum Latency** | `9.15 ms` | - | - |
| **Average Latency** | `27.57 ms` | - | - |
| **p50 Latency** | `26.86 ms` | < 30 ms | **Met** |
| **p90 Latency** | `35.82 ms` | < 45 ms | **Met** |
| **p95 Latency** | **`41.71 ms`** | **< 50 ms** | **PASSED (< 50ms)** |
| **p99 Latency** | `61.10 ms` | < 100 ms | **Met** |
| **Maximum Latency** | `124.40 ms` | - | - |

---

## 2. Overhead Breakdown by Layer

1. **Authentication & Ingestion (`deps.py`)**:
   - Authorization Bearer header parsing.
   - SHA-256 key hashing (`< 0.1 ms`).
   - O(1) in-memory key validity & revocation check (`< 0.2 ms`).
2. **Rate Limit & Budget Evaluation (`core/rate_limit.py`, `core/budget.py`)**:
   - Sliding-window timestamp comparison against project RPM limit (`< 0.5 ms`).
   - Budget threshold checking against cached spend counters (`< 0.5 ms`).
3. **Routing & Fallback Assembly (`core/routing.py`)**:
   - Canonical model resolution and fallback candidate chain resolution (`< 0.5 ms`).
4. **Adapter Proxy Path (`providers/mock.py`)**:
   - Fast mock token generation with deterministic usage counters (`< 1.0 ms`).
5. **Serialization & Streaming Response**:
   - OpenAI-compatible JSON construction with usage details and gateway tracking headers (`< 2.0 ms`).
6. **Audit & Usage Queueing (`services/request_logger.py`)**:
   - Offloaded to asynchronous bounded queue (`< 0.1 ms` in request path; batch-flushed by background worker).

---

## 3. How to Reproduce

Run the automated benchmark script against the mock provider:

```bash
cd backend
$env:PYTHONPATH="."
uv run python scripts/benchmark.py
```
