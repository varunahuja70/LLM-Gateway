import uuid

from pydantic import BaseModel, field_validator


class FeedbackRequest(BaseModel):
    request_id: uuid.UUID
    score: int

    @field_validator("score")
    @classmethod
    def validate_score(cls, v: int) -> int:
        if v not in (1, -1):
            raise ValueError("Score must be 1 (thumbs up) or -1 (thumbs down).")
        return v


class FeedbackResponse(BaseModel):
    status: str = "ok"
    request_id: str
    score: int
