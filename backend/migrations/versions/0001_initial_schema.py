"""Initial schema with all 12 tables and indexes

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-10-03 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. owner_user
    op.create_table(
        "owner_user",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("single_owner_guard", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("single_owner_guard", name="uq_owner_user_single_owner"),
    )
    op.create_index("ix_owner_user_email", "owner_user", ["email"], unique=True)

    # 2. session
    op.create_table(
        "session",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("csrf_token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("ip", sa.String(length=45), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["owner_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_session_owner_id", "session", ["owner_id"], unique=False)
    op.create_index("ix_session_expires_at", "session", ["expires_at"], unique=False)

    # 3. project
    op.create_table(
        "project",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_project_name"),
    )
    op.create_index("ix_project_slug", "project", ["slug"], unique=True)
    op.create_index("ix_project_archived_at", "project", ["archived_at"], unique=False)

    # 4. project_config
    op.create_table(
        "project_config",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("daily_budget_micro_usd", sa.BigInteger(), nullable=True),
        sa.Column("monthly_budget_micro_usd", sa.BigInteger(), nullable=True),
        sa.Column("warn_thresholds", sa.JSON(), nullable=False),
        sa.Column("block_at_limit", sa.Boolean(), nullable=False),
        sa.Column("fallback_chain", sa.JSON(), nullable=False),
        sa.Column("max_fallbacks", sa.Integer(), nullable=False),
        sa.Column("request_timeout_s", sa.Integer(), nullable=False),
        sa.Column("cache_enabled", sa.Boolean(), nullable=False),
        sa.Column("cache_ttl_s", sa.Integer(), nullable=False),
        sa.Column("rpm_limit", sa.Integer(), nullable=False),
        sa.Column("log_content", sa.Boolean(), nullable=False),
        sa.Column("webhook_url", sa.Text(), nullable=True),
        sa.Column("webhook_secret_encrypted", sa.LargeBinary(), nullable=True),
        sa.Column("provider_credential_id", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("project_id"),
    )

    # 5. gateway_key
    op.create_table(
        "gateway_key",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("prefix", sa.String(length=8), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_gateway_key_project_id", "gateway_key", ["project_id"], unique=False)
    op.create_index("ix_gateway_key_key_hash", "gateway_key", ["key_hash"], unique=True)
    op.create_index("ix_gateway_key_revoked_at", "gateway_key", ["revoked_at"], unique=False)
    op.create_index("ix_gateway_key_expires_at", "gateway_key", ["expires_at"], unique=False)

    # 6. provider_credential
    op.create_table(
        "provider_credential",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("base_url", sa.Text(), nullable=True),
        sa.Column("encrypted_key", sa.LargeBinary(), nullable=False),
        sa.Column("key_version", sa.Integer(), nullable=False),
        sa.Column("key_last4", sa.String(length=4), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_provider_credential_provider", "provider_credential", ["provider"], unique=False
    )
    op.create_index(
        "ix_provider_credential_disabled_at", "provider_credential", ["disabled_at"], unique=False
    )

    # 7. model_price
    op.create_table(
        "model_price",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("input_micro_usd_per_mtok", sa.BigInteger(), nullable=False),
        sa.Column("output_micro_usd_per_mtok", sa.BigInteger(), nullable=False),
        sa.Column("cached_input_micro_usd_per_mtok", sa.BigInteger(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("verified_on", sa.Date(), nullable=False),
        sa.Column("is_seed", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "model", name="uq_model_price_provider_model"),
    )

    # 8. request_log
    op.create_table(
        "request_log",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("gateway_key_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("endpoint", sa.String(length=50), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("model_requested", sa.String(length=100), nullable=False),
        sa.Column("model_used", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=False),
        sa.Column("error_type", sa.String(length=100), nullable=True),
        sa.Column("error_message_safe", sa.Text(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("cached_input_tokens", sa.Integer(), nullable=False),
        sa.Column("usage_estimated", sa.Boolean(), nullable=False),
        sa.Column("cost_micro_usd", sa.BigInteger(), nullable=True),
        sa.Column("saved_micro_usd", sa.BigInteger(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("ttft_ms", sa.Integer(), nullable=True),
        sa.Column("streamed", sa.Boolean(), nullable=False),
        sa.Column("cache_hit", sa.Boolean(), nullable=False),
        sa.Column("fallback_used", sa.Boolean(), nullable=False),
        sa.Column("fallback_from", sa.String(length=100), nullable=True),
        sa.Column("fallback_reason", sa.String(length=100), nullable=True),
        sa.Column("finish_reason", sa.String(length=50), nullable=True),
        sa.Column("empty_or_truncated", sa.Boolean(), nullable=False),
        sa.Column("user_tag", sa.String(length=128), nullable=True),
        sa.Column("feedback_score", sa.SmallInteger(), nullable=True),
        sa.Column("request_hash", sa.LargeBinary(), nullable=True),
        sa.ForeignKeyConstraint(["gateway_key_id"], ["gateway_key.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_request_log_project_id", "request_log", ["project_id"], unique=False)
    op.create_index(
        "ix_request_log_gateway_key_id", "request_log", ["gateway_key_id"], unique=False
    )
    op.create_index(
        "ix_request_log_project_created",
        "request_log",
        ["project_id", sa.text("created_at DESC")],
        unique=False,
    )
    op.create_index("ix_request_log_created_at", "request_log", ["created_at"], unique=False)
    op.create_index(
        "ix_request_log_model_created", "request_log", ["model_used", "created_at"], unique=False
    )
    op.create_index(
        "ix_request_log_status_created", "request_log", ["status", "created_at"], unique=False
    )
    op.create_index("ix_request_log_model_used", "request_log", ["model_used"], unique=False)
    op.create_index("ix_request_log_status", "request_log", ["status"], unique=False)
    op.create_index("ix_request_log_user_tag", "request_log", ["user_tag"], unique=False)

    # 9. request_content
    op.create_table(
        "request_content",
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("request_json", sa.JSON(), nullable=False),
        sa.Column("response_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["request_id"], ["request_log.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("request_id"),
    )

    # 10. budget_alert
    op.create_table(
        "budget_alert",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("period", sa.String(length=20), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("threshold_percent", sa.Integer(), nullable=False),
        sa.Column("spend_micro_usd", sa.BigInteger(), nullable=False),
        sa.Column("budget_micro_usd", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("webhook_status", sa.String(length=20), nullable=False),
        sa.Column("webhook_attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id",
            "period",
            "period_start",
            "threshold_percent",
            name="uq_budget_alert_threshold",
        ),
    )
    op.create_index("ix_budget_alert_project_id", "budget_alert", ["project_id"], unique=False)

    # 11. audit_event
    op.create_table(
        "audit_event",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("actor_type", sa.String(length=20), nullable=False),
        sa.Column("actor_id", sa.String(length=100), nullable=True),
        sa.Column("target_type", sa.String(length=50), nullable=True),
        sa.Column("target_id", sa.String(length=100), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_event_created_at", "audit_event", ["created_at"], unique=False)
    op.create_index("ix_audit_event_action", "audit_event", ["action"], unique=False)

    # 12. app_setting
    op.create_table(
        "app_setting",
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )


def downgrade() -> None:
    op.drop_table("app_setting")
    op.drop_table("audit_event")
    op.drop_table("budget_alert")
    op.drop_table("request_content")
    op.drop_table("request_log")
    op.drop_table("model_price")
    op.drop_table("provider_credential")
    op.drop_table("gateway_key")
    op.drop_table("project_config")
    op.drop_table("project")
    op.drop_table("session")
    op.drop_table("owner_user")
