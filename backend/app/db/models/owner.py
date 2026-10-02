import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utc_now, uuid7


class OwnerUser(Base):
    __tablename__ = "owner_user"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    # Single owner guard: unique constraint on constant column guarantees max 1 row in V1
    single_owner_guard: Mapped[int] = mapped_column(Integer, default=1, unique=True, nullable=False)

    sessions: Mapped[list["Session"]] = relationship(
        "Session", back_populates="owner", cascade="all, delete-orphan", lazy="selectin"
    )


class Session(Base):
    __tablename__ = "session"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # SHA-256 of session token
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("owner_user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    csrf_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)

    owner: Mapped[OwnerUser] = relationship("OwnerUser", back_populates="sessions", lazy="selectin")
