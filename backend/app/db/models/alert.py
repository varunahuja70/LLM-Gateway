import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utc_now, uuid7


class BudgetAlert(Base):
    __tablename__ = "budget_alert"

    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "period",
            "period_start",
            "threshold_percent",
            name="uq_budget_alert_threshold",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="CASCADE"), nullable=False, index=True
    )
    period: Mapped[str] = mapped_column(String(20), nullable=False)  # 'daily' | 'monthly'
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    threshold_percent: Mapped[int] = mapped_column(Integer, nullable=False)
    spend_micro_usd: Mapped[int] = mapped_column(BigInteger, nullable=False)
    budget_micro_usd: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    webhook_status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False
    )  # 'pending' | 'sent' | 'failed' | 'skipped'
    webhook_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
