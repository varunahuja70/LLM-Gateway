import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Select, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.budget import get_daily_period, get_monthly_period
from app.db.base import ensure_utc, utc_now
from app.db.models.project import Project
from app.db.models.request import RequestLog
from app.schemas.stats import (
    ModelQualityStat,
    OverviewStats,
    ProjectStatsResponse,
    TimeseriesBucket,
)


def compute_percentile_cont(values: Sequence[float | int], p: float) -> float | None:
    """Compute continuous linear interpolation percentile (matches PostgreSQL percentile_cont)."""
    if not values:
        return None
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    if n == 1:
        return float(sorted_vals[0])
    rank = p * (n - 1)
    low_idx = int(rank)
    high_idx = min(low_idx + 1, n - 1)
    weight = rank - low_idx
    return float(sorted_vals[low_idx] + weight * (sorted_vals[high_idx] - sorted_vals[low_idx]))


def _apply_filters(
    stmt: Select[Any],
    project_id: uuid.UUID | None = None,
    from_time: datetime | None = None,
    to_time: datetime | None = None,
) -> Select[Any]:
    if project_id is not None:
        stmt = stmt.where(RequestLog.project_id == project_id)
    if from_time is not None:
        stmt = stmt.where(RequestLog.created_at >= ensure_utc(from_time))
    if to_time is not None:
        stmt = stmt.where(RequestLog.created_at <= ensure_utc(to_time))
    return stmt


async def get_overview_stats(
    session: AsyncSession,
    project_id: uuid.UUID | None = None,
    from_time: datetime | None = None,
    to_time: datetime | None = None,
) -> OverviewStats:
    stmt = select(
        func.count(RequestLog.id).label("total_requests"),
        func.coalesce(func.sum(RequestLog.input_tokens), 0).label("input_tokens"),
        func.coalesce(func.sum(RequestLog.output_tokens), 0).label("output_tokens"),
        func.coalesce(func.sum(RequestLog.cached_input_tokens), 0).label("cached_input_tokens"),
        func.coalesce(func.sum(RequestLog.cost_micro_usd), 0).label("total_cost_micro_usd"),
        func.coalesce(func.sum(RequestLog.saved_micro_usd), 0).label("saved_micro_usd"),
        func.count(case((RequestLog.status == "error", 1))).label("error_count"),
        func.count(case((RequestLog.fallback_used.is_(True), 1))).label("fallback_count"),
        func.count(case((RequestLog.cache_hit.is_(True), 1))).label("cache_hit_count"),
        func.coalesce(func.avg(RequestLog.latency_ms), 0.0).label("avg_latency_ms"),
    )
    stmt = _apply_filters(stmt, project_id, from_time, to_time)
    result = await session.execute(stmt)
    row = result.one()

    total_requests = int(row.total_requests or 0)
    if total_requests == 0:
        return OverviewStats()

    input_tokens = int(row.input_tokens or 0)
    output_tokens = int(row.output_tokens or 0)
    cached_input_tokens = int(row.cached_input_tokens or 0)
    total_cost_micro_usd = int(row.total_cost_micro_usd or 0)
    saved_micro_usd = int(row.saved_micro_usd or 0)
    error_count = int(row.error_count or 0)
    fallback_count = int(row.fallback_count or 0)
    cache_hit_count = int(row.cache_hit_count or 0)
    avg_latency_ms = round(float(row.avg_latency_ms or 0.0), 2)

    return OverviewStats(
        total_requests=total_requests,
        total_tokens=input_tokens + output_tokens,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cached_input_tokens=cached_input_tokens,
        total_cost_micro_usd=total_cost_micro_usd,
        saved_micro_usd=saved_micro_usd,
        error_rate=round(error_count / total_requests, 4),
        fallback_rate=round(fallback_count / total_requests, 4),
        avg_latency_ms=avg_latency_ms,
        cache_hit_rate=round(cache_hit_count / total_requests, 4),
    )


async def get_models_stats(
    session: AsyncSession,
    project_id: uuid.UUID | None = None,
    from_time: datetime | None = None,
    to_time: datetime | None = None,
) -> list[ModelQualityStat]:
    dialect = session.get_bind().dialect.name

    if dialect == "postgresql":
        stmt = (
            select(
                RequestLog.model_used,
                RequestLog.provider,
                func.count(RequestLog.id).label("total_requests"),
                func.coalesce(func.sum(RequestLog.input_tokens), 0).label("input_tokens"),
                func.coalesce(func.sum(RequestLog.output_tokens), 0).label("output_tokens"),
                func.coalesce(func.sum(RequestLog.cost_micro_usd), 0).label("total_cost_micro_usd"),
                func.count(case((RequestLog.status == "error", 1))).label("error_count"),
                func.count(case((RequestLog.fallback_used.is_(True), 1))).label("fallback_count"),
                func.count(case((RequestLog.empty_or_truncated.is_(True), 1))).label(
                    "empty_or_truncated_count"
                ),
                func.avg(RequestLog.ttft_ms).label("avg_ttft_ms"),
                func.avg(RequestLog.feedback_score).label("avg_feedback_score"),
                func.percentile_cont(0.50)
                .within_group(RequestLog.latency_ms.asc())
                .label("p50_latency"),
                func.percentile_cont(0.95)
                .within_group(RequestLog.latency_ms.asc())
                .label("p95_latency"),
                func.percentile_cont(0.99)
                .within_group(RequestLog.latency_ms.asc())
                .label("p99_latency"),
            )
            .group_by(RequestLog.model_used, RequestLog.provider)
            .order_by(func.count(RequestLog.id).desc())
        )
        stmt = _apply_filters(stmt, project_id, from_time, to_time)
        res = await session.execute(stmt)
        rows = res.all()

        output: list[ModelQualityStat] = []
        for r in rows:
            tot = int(r.total_requests or 0)
            if tot == 0:
                continue
            inp = int(r.input_tokens or 0)
            out = int(r.output_tokens or 0)
            err = int(r.error_count or 0)
            fb = int(r.fallback_count or 0)
            e_t = int(r.empty_or_truncated_count or 0)

            output.append(
                ModelQualityStat(
                    model=r.model_used,
                    provider=r.provider,
                    total_requests=tot,
                    total_tokens=inp + out,
                    total_cost_micro_usd=int(r.total_cost_micro_usd or 0),
                    error_rate=round(err / tot, 4),
                    fallback_rate=round(fb / tot, 4),
                    p50_latency_ms=round(float(r.p50_latency), 2)
                    if r.p50_latency is not None
                    else None,
                    p95_latency_ms=round(float(r.p95_latency), 2)
                    if r.p95_latency is not None
                    else None,
                    p99_latency_ms=round(float(r.p99_latency), 2)
                    if r.p99_latency is not None
                    else None,
                    avg_ttft_ms=round(float(r.avg_ttft_ms), 2)
                    if r.avg_ttft_ms is not None
                    else None,
                    empty_or_truncated_rate=round(e_t / tot, 4),
                    avg_feedback_score=round(float(r.avg_feedback_score), 2)
                    if r.avg_feedback_score is not None
                    else None,
                )
            )
        return output

    # SQLite / Generic dialect
    stmt = (
        select(
            RequestLog.model_used,
            RequestLog.provider,
            func.count(RequestLog.id).label("total_requests"),
            func.coalesce(func.sum(RequestLog.input_tokens), 0).label("input_tokens"),
            func.coalesce(func.sum(RequestLog.output_tokens), 0).label("output_tokens"),
            func.coalesce(func.sum(RequestLog.cost_micro_usd), 0).label("total_cost_micro_usd"),
            func.count(case((RequestLog.status == "error", 1))).label("error_count"),
            func.count(case((RequestLog.fallback_used.is_(True), 1))).label("fallback_count"),
            func.count(case((RequestLog.empty_or_truncated.is_(True), 1))).label(
                "empty_or_truncated_count"
            ),
            func.avg(RequestLog.ttft_ms).label("avg_ttft_ms"),
            func.avg(RequestLog.feedback_score).label("avg_feedback_score"),
        )
        .group_by(RequestLog.model_used, RequestLog.provider)
        .order_by(func.count(RequestLog.id).desc())
    )
    stmt = _apply_filters(stmt, project_id, from_time, to_time)
    res = await session.execute(stmt)
    agg_rows = res.all()

    # Query latencies to compute percentiles in Python for non-Postgres engines
    lat_stmt = select(RequestLog.model_used, RequestLog.provider, RequestLog.latency_ms)
    lat_stmt = _apply_filters(lat_stmt, project_id, from_time, to_time)
    lat_res = await session.execute(lat_stmt)
    lat_rows = lat_res.all()

    latencies_map: dict[tuple[str, str], list[int]] = {}
    for model_name, provider_name, latency_val in lat_rows:
        latencies_map.setdefault((model_name, provider_name), []).append(latency_val)

    output = []
    for r in agg_rows:
        tot = int(r.total_requests or 0)
        if tot == 0:
            continue
        key = (r.model_used, r.provider)
        group_lats = latencies_map.get(key, [])
        p50 = compute_percentile_cont(group_lats, 0.50)
        p95 = compute_percentile_cont(group_lats, 0.95)
        p99 = compute_percentile_cont(group_lats, 0.99)

        inp = int(r.input_tokens or 0)
        out = int(r.output_tokens or 0)
        err = int(r.error_count or 0)
        fb = int(r.fallback_count or 0)
        e_t = int(r.empty_or_truncated_count or 0)

        output.append(
            ModelQualityStat(
                model=r.model_used,
                provider=r.provider,
                total_requests=tot,
                total_tokens=inp + out,
                total_cost_micro_usd=int(r.total_cost_micro_usd or 0),
                error_rate=round(err / tot, 4),
                fallback_rate=round(fb / tot, 4),
                p50_latency_ms=round(p50, 2) if p50 is not None else None,
                p95_latency_ms=round(p95, 2) if p95 is not None else None,
                p99_latency_ms=round(p99, 2) if p99 is not None else None,
                avg_ttft_ms=round(float(r.avg_ttft_ms), 2) if r.avg_ttft_ms is not None else None,
                empty_or_truncated_rate=round(e_t / tot, 4),
                avg_feedback_score=round(float(r.avg_feedback_score), 2)
                if r.avg_feedback_score is not None
                else None,
            )
        )
    return output


async def get_timeseries_stats(
    session: AsyncSession,
    project_id: uuid.UUID | None = None,
    from_time: datetime | None = None,
    to_time: datetime | None = None,
    bucket: str = "hour",
) -> list[TimeseriesBucket]:
    if bucket not in ("hour", "day"):
        bucket = "hour"

    dialect = session.get_bind().dialect.name

    if dialect == "postgresql":
        bucket_col = func.date_trunc(bucket, RequestLog.created_at).label("bucket_time")
        stmt = (
            select(
                bucket_col,
                func.count(RequestLog.id).label("requests"),
                func.count(case((RequestLog.status == "error", 1))).label("errors"),
                func.coalesce(func.sum(RequestLog.input_tokens), 0).label("input_tokens"),
                func.coalesce(func.sum(RequestLog.output_tokens), 0).label("output_tokens"),
                func.coalesce(func.sum(RequestLog.cost_micro_usd), 0).label("cost_micro_usd"),
                func.coalesce(func.sum(RequestLog.saved_micro_usd), 0).label("saved_micro_usd"),
                func.count(case((RequestLog.cache_hit.is_(True), 1))).label("cache_hits"),
                func.percentile_cont(0.50)
                .within_group(RequestLog.latency_ms.asc())
                .label("p50_latency"),
                func.percentile_cont(0.95)
                .within_group(RequestLog.latency_ms.asc())
                .label("p95_latency"),
                func.percentile_cont(0.99)
                .within_group(RequestLog.latency_ms.asc())
                .label("p99_latency"),
            )
            .group_by(bucket_col)
            .order_by(bucket_col.asc())
        )
        stmt = _apply_filters(stmt, project_id, from_time, to_time)
        res = await session.execute(stmt)
        rows = res.all()

        data: list[TimeseriesBucket] = []
        for r in rows:
            inp = int(r.input_tokens or 0)
            out = int(r.output_tokens or 0)
            ts = r.bucket_time
            if not isinstance(ts, datetime):
                ts = datetime.fromisoformat(str(ts)).replace(tzinfo=UTC)
            else:
                ts = ensure_utc(ts)

            data.append(
                TimeseriesBucket(
                    timestamp=ts,
                    requests=int(r.requests or 0),
                    errors=int(r.errors or 0),
                    tokens=inp + out,
                    input_tokens=inp,
                    output_tokens=out,
                    cost_micro_usd=int(r.cost_micro_usd or 0),
                    saved_micro_usd=int(r.saved_micro_usd or 0),
                    cache_hits=int(r.cache_hits or 0),
                    p50_latency_ms=round(float(r.p50_latency), 2)
                    if r.p50_latency is not None
                    else None,
                    p95_latency_ms=round(float(r.p95_latency), 2)
                    if r.p95_latency is not None
                    else None,
                    p99_latency_ms=round(float(r.p99_latency), 2)
                    if r.p99_latency is not None
                    else None,
                )
            )
        return data

    # SQLite fallback
    fmt = "%Y-%m-%d %H:00:00" if bucket == "hour" else "%Y-%m-%d 00:00:00"
    bucket_col = func.strftime(fmt, RequestLog.created_at).label("bucket_time")

    stmt = (
        select(
            bucket_col,
            func.count(RequestLog.id).label("requests"),
            func.count(case((RequestLog.status == "error", 1))).label("errors"),
            func.coalesce(func.sum(RequestLog.input_tokens), 0).label("input_tokens"),
            func.coalesce(func.sum(RequestLog.output_tokens), 0).label("output_tokens"),
            func.coalesce(func.sum(RequestLog.cost_micro_usd), 0).label("cost_micro_usd"),
            func.coalesce(func.sum(RequestLog.saved_micro_usd), 0).label("saved_micro_usd"),
            func.count(case((RequestLog.cache_hit.is_(True), 1))).label("cache_hits"),
        )
        .group_by(bucket_col)
        .order_by(bucket_col.asc())
    )
    stmt = _apply_filters(stmt, project_id, from_time, to_time)
    res = await session.execute(stmt)
    agg_rows = res.all()

    # Latencies by bucket
    lat_stmt = select(bucket_col, RequestLog.latency_ms)
    lat_stmt = _apply_filters(lat_stmt, project_id, from_time, to_time)
    lat_res = await session.execute(lat_stmt)
    lat_rows = lat_res.all()

    bucket_lats: dict[str, list[int]] = {}
    for b_str, lat in lat_rows:
        bucket_lats.setdefault(str(b_str), []).append(lat)

    data = []
    for r in agg_rows:
        b_key = str(r.bucket_time)
        lats = bucket_lats.get(b_key, [])
        p50 = compute_percentile_cont(lats, 0.50)
        p95 = compute_percentile_cont(lats, 0.95)
        p99 = compute_percentile_cont(lats, 0.99)

        inp = int(r.input_tokens or 0)
        out = int(r.output_tokens or 0)
        ts = datetime.fromisoformat(b_key).replace(tzinfo=UTC)

        data.append(
            TimeseriesBucket(
                timestamp=ts,
                requests=int(r.requests or 0),
                errors=int(r.errors or 0),
                tokens=inp + out,
                input_tokens=inp,
                output_tokens=out,
                cost_micro_usd=int(r.cost_micro_usd or 0),
                saved_micro_usd=int(r.saved_micro_usd or 0),
                cache_hits=int(r.cache_hits or 0),
                p50_latency_ms=round(p50, 2) if p50 is not None else None,
                p95_latency_ms=round(p95, 2) if p95 is not None else None,
                p99_latency_ms=round(p99, 2) if p99 is not None else None,
            )
        )
    return data


async def get_project_stats(
    session: AsyncSession,
    project_id: uuid.UUID,
    redis_client: Any = None,
    from_time: datetime | None = None,
    to_time: datetime | None = None,
) -> ProjectStatsResponse:
    project_check = await session.execute(select(Project.id).where(Project.id == project_id))
    if project_check.scalar_one_or_none() is None:
        raise ValueError("Project not found.")

    overview = await get_overview_stats(
        session, project_id=project_id, from_time=from_time, to_time=to_time
    )
    models = await get_models_stats(
        session, project_id=project_id, from_time=from_time, to_time=to_time
    )

    # Budget current period spend
    now = utc_now()
    _, _, day_str = get_daily_period(now)
    _, _, month_str = get_monthly_period(now)

    daily_spend: int = 0
    monthly_spend: int = 0

    if redis_client is not None:
        try:
            d_val = await redis_client.get(f"budget:{project_id}:daily:{day_str}")
            if d_val is not None:
                daily_spend = int(d_val)
            m_val = await redis_client.get(f"budget:{project_id}:monthly:{month_str}")
            if m_val is not None:
                monthly_spend = int(m_val)
        except Exception:
            pass

    # If redis had no values, calculate from DB for current period
    if daily_spend == 0 or monthly_spend == 0:
        day_start, _, _ = get_daily_period(now)
        month_start, _, _ = get_monthly_period(now)

        db_day_spend = await session.scalar(
            select(func.coalesce(func.sum(RequestLog.cost_micro_usd), 0)).where(
                RequestLog.project_id == project_id,
                RequestLog.created_at >= day_start,
                RequestLog.cost_micro_usd.is_not(None),
            )
        )
        if daily_spend == 0 and db_day_spend is not None:
            daily_spend = int(db_day_spend)

        db_month_spend = await session.scalar(
            select(func.coalesce(func.sum(RequestLog.cost_micro_usd), 0)).where(
                RequestLog.project_id == project_id,
                RequestLog.created_at >= month_start,
                RequestLog.cost_micro_usd.is_not(None),
            )
        )
        if monthly_spend == 0 and db_month_spend is not None:
            monthly_spend = int(db_month_spend)

    return ProjectStatsResponse(
        project_id=project_id,
        overview=overview,
        models=models,
        budget_daily_used_micro_usd=daily_spend,
        budget_monthly_used_micro_usd=monthly_spend,
    )
