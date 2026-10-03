"""Add provider created_at index to request_log

Revision ID: 0002_provider_idx
Revises: 0001_initial_schema
Create Date: 2026-10-03 04:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002_provider_idx"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_request_log_provider_created",
        "request_log",
        ["provider", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_request_log_provider_created", table_name="request_log")
