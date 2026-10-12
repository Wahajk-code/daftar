"""users, audit_events and the shared enums

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

user_role = postgresql.ENUM("admin", "accountant", "approver", "staff", name="user_role", create_type=False)
document_status = postgresql.ENUM(
    "draft", "submitted", "approved", "rejected", "posted", "void", name="document_status", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    user_role.create(bind, checkfirst=True)
    document_status.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", user_role, nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("tour_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("email = lower(email)", name="email_lower"),
        sa.CheckConstraint("length(btrim(full_name)) > 0", name="full_name_not_blank"),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    op.create_table(
        "audit_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("actor_id", sa.BigInteger(), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.BigInteger(), nullable=True),
        sa.Column("before", postgresql.JSONB(), nullable=True),
        sa.Column("after", postgresql.JSONB(), nullable=True),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], name="fk_audit_events_actor_id_users"),
        sa.PrimaryKeyConstraint("id", name="pk_audit_events"),
    )
    op.create_index("ix_audit_events_entity", "audit_events", ["entity_type", "entity_id"])
    op.create_index("ix_audit_events_actor_id", "audit_events", ["actor_id"])
    op.create_index("ix_audit_events_occurred_at", "audit_events", ["occurred_at"])


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("users")
    bind = op.get_bind()
    document_status.drop(bind, checkfirst=True)
    user_role.drop(bind, checkfirst=True)
