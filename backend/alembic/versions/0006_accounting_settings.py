"""the accounting settings: which month the voucher numbering year starts in

Revision ID: 0006
Revises: 0005
"""

import sqlalchemy as sa

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # One row, ever. An Accountant sets it; month 1 means the numbering year is the calendar year.
    op.create_table(
        "accounting_settings",
        sa.Column("id", sa.SmallInteger(), server_default=sa.text("1"), nullable=False),
        sa.Column("fiscal_year_start_month", sa.SmallInteger(), server_default=sa.text("1"), nullable=False),
        sa.Column("updated_by", sa.BigInteger()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("id = 1", name="only_one_row"),
        sa.CheckConstraint("fiscal_year_start_month BETWEEN 1 AND 12", name="a_real_month"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], name="fk_accounting_settings_updated_by_users"),
        sa.PrimaryKeyConstraint("id", name="pk_accounting_settings"),
    )
    op.execute("INSERT INTO accounting_settings (id, fiscal_year_start_month) VALUES (1, 1)")
    op.execute(
        "CREATE TRIGGER accounting_settings_no_delete BEFORE DELETE ON accounting_settings"
        " FOR EACH ROW EXECUTE FUNCTION prevent_delete()"
    )


def downgrade() -> None:
    op.drop_table("accounting_settings")
