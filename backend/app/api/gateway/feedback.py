from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import GatewayAPIException
from app.db.models.project import GatewayKey, Project
from app.db.models.request import RequestLog
from app.db.session import get_db_session
from app.deps import require_gateway_key
from app.schemas.feedback import FeedbackRequest, FeedbackResponse

router = APIRouter(prefix="/v1", tags=["gateway-feedback"])


@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(
    payload: FeedbackRequest,
    auth_data: tuple[Project, GatewayKey] = Depends(require_gateway_key),
    db: AsyncSession = Depends(get_db_session),
) -> FeedbackResponse:
    """Submit thumbs up (1) or thumbs down (-1) feedback on a request.

    Enforces that callers can only provide feedback for requests belonging
    to their own project; requests of other projects return 404.
    """
    project, _gateway_key = auth_data

    stmt = select(RequestLog).where(
        RequestLog.id == payload.request_id,
        RequestLog.project_id == project.id,
    )
    result = await db.execute(stmt)
    log_record = result.scalar_one_or_none()

    if not log_record:
        raise GatewayAPIException(
            status_code=404,
            message=f"Request '{payload.request_id}' not found.",
            error_type="invalid_request_error",
            code="request_not_found",
            param="request_id",
        )

    log_record.feedback_score = payload.score
    await db.commit()

    return FeedbackResponse(
        status="ok",
        request_id=str(payload.request_id),
        score=payload.score,
    )
