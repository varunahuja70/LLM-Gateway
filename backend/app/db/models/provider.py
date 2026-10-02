import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utc_now, uuid7


class ProviderCredential(Base):
    __tablename__ = "provider_credential"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    provider: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    base_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    encrypted_key: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    key_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    key_last4: Mapped[str] = mapped_column(String(4), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    disabled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )


class ModelPrice(Base):
    __tablename__ = "model_price"

    __table_args__ = (UniqueConstraint("provider", "model", name="uq_model_price_provider_model"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    input_micro_usd_per_mtok: Mapped[int] = mapped_column(BigInteger, nullable=False)
    output_micro_usd_per_mtok: Mapped[int] = mapped_column(BigInteger, nullable=False)
    cached_input_micro_usd_per_mtok: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    verified_on: Mapped[date] = mapped_column(Date, nullable=False)
    is_seed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
