import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    SmallInteger,
    String,
    Text,
    desc,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utc_now, uuid7


class RequestLog(Base):
    __tablename__ = "request_log"

    __table_args__ = (
        Index("ix_request_log_project_created", "project_id", desc("created_at")),
        Index("ix_request_log_created_at", "created_at"),
        Index("ix_request_log_model_created", "model_used", "created_at"),
        Index("ix_request_log_status_created", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="CASCADE"), nullable=False, index=True
    )
    gateway_key_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("gateway_key.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    endpoint: Mapped[str] = mapped_column(String(50), nullable=False)  # 'chat' | 'embeddings'
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model_requested: Mapped[str] = mapped_column(String(100), nullable=False)
    model_used: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # 'ok' | 'error' | 'blocked' | 'rate_limited'
    http_status: Mapped[int] = mapped_column(Integer, nullable=False)
    error_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message_safe: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cached_input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    usage_estimated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    cost_micro_usd: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    saved_micro_usd: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    ttft_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    streamed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    fallback_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    fallback_from: Mapped[str | None] = mapped_column(String(100), nullable=True)
    fallback_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)
    finish_reason: Mapped[str | None] = mapped_column(String(50), nullable=True)
    empty_or_truncated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    user_tag: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    feedback_score: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    request_hash: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)

    content: Mapped["RequestContent | None"] = relationship(
        "RequestContent",
        back_populates="request_log",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class RequestContent(Base):
    __tablename__ = "request_content"

    request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("request_log.id", ondelete="CASCADE"), primary_key=True
    )
    request_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    response_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    request_log: Mapped[RequestLog] = relationship(
        "RequestLog", back_populates="content", lazy="selectin"
    )
