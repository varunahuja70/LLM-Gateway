import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utc_now, uuid7


class Project(Base):
    __tablename__ = "project"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    config: Mapped["ProjectConfig"] = relationship(
        "ProjectConfig",
        back_populates="project",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    keys: Mapped[list["GatewayKey"]] = relationship(
        "GatewayKey",
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class ProjectConfig(Base):
    __tablename__ = "project_config"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="CASCADE"), primary_key=True
    )
    daily_budget_micro_usd: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    monthly_budget_micro_usd: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    warn_thresholds: Mapped[list[int]] = mapped_column(
        JSON, default=lambda: [50, 80, 100], nullable=False
    )
    block_at_limit: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    fallback_chain: Mapped[list[dict[str, str]]] = mapped_column(JSON, default=list, nullable=False)
    max_fallbacks: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    request_timeout_s: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    cache_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    cache_ttl_s: Mapped[int] = mapped_column(Integer, default=3600, nullable=False)
    rpm_limit: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    log_content: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    webhook_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    webhook_secret_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    provider_credential_id: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )

    project: Mapped[Project] = relationship("Project", back_populates="config", lazy="selectin")


class GatewayKey(Base):
    __tablename__ = "gateway_key"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    prefix: Mapped[str] = mapped_column(String(8), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    project: Mapped[Project] = relationship("Project", back_populates="keys", lazy="selectin")
