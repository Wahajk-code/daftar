"""tokens, vendors, master data, tax rules, and the database rules around them

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def enum(name: str, *values: str) -> postgresql.ENUM:
    return postgresql.ENUM(*values, name=name, create_type=False)


auth_purpose = enum("auth_purpose", "invite", "password_reset")
account_type = enum("account_type", "asset", "liability", "income", "expense", "equity")
project_kind = enum("project_kind", "project", "product")
tax_type = enum("tax_type", "sales_tax_withholding", "income_tax_withholding")
tax_category = enum("tax_category", "goods", "services", "contracts", "any")
posting_key = enum(
    "posting_key", "cash", "bank", "input_sales_tax", "sales_tax_withheld", "income_tax_withheld"
)
user_role = enum("user_role", "admin", "accountant", "approver", "staff")
NEW_ENUMS = (auth_purpose, account_type, project_kind, tax_type, tax_category, posting_key)

# Rows in these tables are never deleted: master data deactivates, periods are reopened, rules are ended.
NEVER_DELETED = (
    "users",
    "vendors",
    "accounts",
    "categories",
    "cost_centers",
    "projects",
    "closed_periods",
    "tax_rules",
    "posting_accounts",
)


def timestamps() -> list[sa.Column]:  # type: ignore[type-arg]
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def identity() -> sa.Column:  # type: ignore[type-arg]
    return sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False)


def upgrade() -> None:
    bind = op.get_bind()
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    for new_enum in NEW_ENUMS:
        new_enum.create(bind, checkfirst=True)

    op.create_table(
        "refresh_tokens",
        identity(),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_refresh_tokens_user_id_users"),
        sa.PrimaryKeyConstraint("id", name="pk_refresh_tokens"),
        sa.UniqueConstraint("token_hash", name="uq_refresh_tokens_token_hash"),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])

    op.create_table(
        "auth_tokens",
        identity(),
        sa.Column("purpose", auth_purpose, nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("email", sa.String(254)),
        sa.Column("role", user_role),
        sa.Column("user_id", sa.BigInteger()),
        sa.Column("created_by", sa.BigInteger()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "(purpose = 'invite' AND email IS NOT NULL AND role IS NOT NULL AND user_id IS NULL)"
            " OR (purpose = 'password_reset' AND user_id IS NOT NULL AND email IS NULL AND role IS NULL)",
            name="shape_matches_purpose",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_auth_tokens_user_id_users"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_auth_tokens_created_by_users"),
        sa.PrimaryKeyConstraint("id", name="pk_auth_tokens"),
        sa.UniqueConstraint("token_hash", name="uq_auth_tokens_token_hash"),
    )
    op.create_index("ix_auth_tokens_user_id", "auth_tokens", ["user_id"])
    op.create_index(
        "uq_auth_tokens_pending_invite_email",
        "auth_tokens",
        ["email"],
        unique=True,
        postgresql_where=sa.text("purpose = 'invite' AND used_at IS NULL AND revoked_at IS NULL"),
    )

    op.create_table(
        "vendors",
        identity(),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("is_sales_tax_registered", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_filer", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("ntn", sa.String(30)),
        sa.Column("strn", sa.String(30)),
        sa.Column("contact_name", sa.String(200)),
        sa.Column("phone", sa.String(40)),
        sa.Column("email", sa.String(254)),
        sa.Column("address", sa.String(500)),
        sa.Column("bank_name", sa.String(120)),
        sa.Column("bank_account_encrypted", sa.String(500)),
        sa.Column("bank_account_last4", sa.String(4)),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        *timestamps(),
        sa.CheckConstraint(
            "NOT is_sales_tax_registered OR (length(btrim(coalesce(ntn, ''))) > 0"
            " AND length(btrim(coalesce(strn, ''))) > 0)",
            name="registered_has_ntn_and_strn",
        ),
        sa.CheckConstraint(
            "(bank_account_encrypted IS NULL) = (bank_account_last4 IS NULL)",
            name="bank_account_parts_agree",
        ),
        sa.CheckConstraint("length(btrim(name)) > 0", name="name_not_blank"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_vendors_created_by_users"),
        sa.PrimaryKeyConstraint("id", name="pk_vendors"),
    )
    op.execute("CREATE UNIQUE INDEX uq_vendors_name_lower ON vendors (lower(btrim(name)))")

    op.create_table(
        "accounts",
        identity(),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("type", account_type, nullable=False),
        sa.Column("parent_id", sa.BigInteger()),
        sa.Column("is_postable", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        *timestamps(),
        sa.CheckConstraint("code ~ '^[0-9A-Za-z.-]{1,20}$'", name="code_format"),
        sa.CheckConstraint("parent_id IS NULL OR parent_id <> id", name="not_its_own_parent"),
        sa.CheckConstraint("length(btrim(name)) > 0", name="name_not_blank"),
        sa.ForeignKeyConstraint(["parent_id"], ["accounts.id"], name="fk_accounts_parent_id_accounts"),
        sa.PrimaryKeyConstraint("id", name="pk_accounts"),
        sa.UniqueConstraint("code", name="uq_accounts_code"),
    )
    op.create_index("ix_accounts_parent_id", "accounts", ["parent_id"])

    op.create_table(
        "categories",
        identity(),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        *timestamps(),
        sa.CheckConstraint("length(btrim(name)) > 0", name="name_not_blank"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], name="fk_categories_account_id_accounts"),
        sa.PrimaryKeyConstraint("id", name="pk_categories"),
    )
    op.execute("CREATE UNIQUE INDEX uq_categories_name_lower ON categories (lower(btrim(name)))")
    op.create_index("ix_categories_account_id", "categories", ["account_id"])

    op.create_table(
        "cost_centers",
        identity(),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        *timestamps(),
        sa.CheckConstraint("code ~ '^[0-9A-Za-z.-]{1,20}$'", name="code_format"),
        sa.CheckConstraint("length(btrim(name)) > 0", name="name_not_blank"),
        sa.PrimaryKeyConstraint("id", name="pk_cost_centers"),
        sa.UniqueConstraint("code", name="uq_cost_centers_code"),
    )

    op.create_table(
        "projects",
        identity(),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("kind", project_kind, nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        *timestamps(),
        sa.CheckConstraint("code ~ '^[0-9A-Za-z.-]{1,20}$'", name="code_format"),
        sa.CheckConstraint("length(btrim(name)) > 0", name="name_not_blank"),
        sa.PrimaryKeyConstraint("id", name="pk_projects"),
        sa.UniqueConstraint("code", name="uq_projects_code"),
    )

    op.create_table(
        "closed_periods",
        identity(),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("closed_by", sa.BigInteger(), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reopened_by", sa.BigInteger()),
        sa.Column("reopened_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("start_date <= end_date", name="start_not_after_end"),
        sa.ForeignKeyConstraint(["closed_by"], ["users.id"], name="fk_closed_periods_closed_by_users"),
        sa.ForeignKeyConstraint(["reopened_by"], ["users.id"], name="fk_closed_periods_reopened_by_users"),
        sa.PrimaryKeyConstraint("id", name="pk_closed_periods"),
    )
    op.execute(
        "ALTER TABLE closed_periods ADD CONSTRAINT no_overlapping_closed_ranges"
        " EXCLUDE USING gist (daterange(start_date, end_date, '[]') WITH &&) WHERE (reopened_at IS NULL)"
    )

    op.create_table(
        "posting_accounts",
        sa.Column("key", posting_key, nullable=False),
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column("updated_by", sa.BigInteger()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], name="fk_posting_accounts_account_id_accounts"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], name="fk_posting_accounts_updated_by_users"),
        sa.PrimaryKeyConstraint("key", name="pk_posting_accounts"),
    )

    op.create_table(
        "tax_rules",
        identity(),
        sa.Column("tax_type", tax_type, nullable=False),
        sa.Column("supplier_registered", sa.Boolean(), nullable=False),
        sa.Column("supplier_filer", sa.Boolean(), nullable=False),
        sa.Column("category", tax_category, server_default=sa.text("'any'"), nullable=False),
        sa.Column("rate_bp", sa.SmallInteger(), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date()),
        sa.Column("source", sa.String(500), nullable=False),
        sa.Column("created_by", sa.BigInteger()),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        *timestamps(),
        sa.CheckConstraint("rate_bp BETWEEN 0 AND 10000", name="rate_in_range"),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_from <= effective_to", name="dates_in_order"
        ),
        sa.CheckConstraint("length(btrim(source)) > 0", name="source_not_blank"),
        sa.CheckConstraint(
            "(tax_type = 'sales_tax_withholding' AND supplier_filer = false)"
            " OR (tax_type = 'income_tax_withholding' AND supplier_registered = false)",
            name="only_the_relevant_flag",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_tax_rules_created_by_users"),
        sa.PrimaryKeyConstraint("id", name="pk_tax_rules"),
    )
    op.execute(
        "ALTER TABLE tax_rules ADD CONSTRAINT no_overlapping_rules EXCLUDE USING gist ("
        "tax_type WITH =, supplier_registered WITH =, supplier_filer WITH =, category WITH =,"
        " daterange(effective_from, effective_to, '[]') WITH &&)"
    )
    op.create_index("ix_tax_rules_lookup", "tax_rules", ["tax_type", "effective_from"])

    # Nothing is deleted.
    op.execute(
        """
        CREATE FUNCTION prevent_delete() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'rows in % are never deleted; deactivate or reverse instead', TG_TABLE_NAME
                USING ERRCODE = '23001';
        END $$
        """
    )
    for table in NEVER_DELETED:
        op.execute(
            f"CREATE TRIGGER {table}_no_delete BEFORE DELETE ON {table}"
            " FOR EACH ROW EXECUTE FUNCTION prevent_delete()"
        )

    # A parent account is never postable, and a postable account never has children. Checked at commit, so a service can
    # add a child and turn the parent off in one transaction.
    op.execute(
        """
        CREATE FUNCTION accounts_parent_not_postable() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
            current_row accounts%ROWTYPE;
        BEGIN
            -- A deferred trigger sees the row as it was when the event was queued, so read the row as it is now.
            SELECT * INTO current_row FROM accounts WHERE id = NEW.id;
            IF NOT FOUND THEN
                RETURN NULL;
            END IF;
            IF current_row.is_postable AND EXISTS (SELECT 1 FROM accounts WHERE parent_id = current_row.id) THEN
                RAISE EXCEPTION 'account % has child accounts and cannot be postable', current_row.code
                    USING ERRCODE = '23514', CONSTRAINT = 'accounts_parent_not_postable';
            END IF;
            IF current_row.parent_id IS NOT NULL
               AND (SELECT is_postable FROM accounts WHERE id = current_row.parent_id) THEN
                RAISE EXCEPTION 'the parent of account % is postable', current_row.code
                    USING ERRCODE = '23514', CONSTRAINT = 'accounts_parent_not_postable';
            END IF;
            RETURN NULL;
        END $$
        """
    )
    op.execute(
        "CREATE CONSTRAINT TRIGGER accounts_parent_not_postable AFTER INSERT OR UPDATE ON accounts"
        " DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION accounts_parent_not_postable()"
    )

    # The last active Admin cannot be demoted or deactivated. The service locks the Admin rows first so two Admins cannot
    # remove each other in parallel; this trigger is the backstop for any path that skips the service.
    op.execute(
        """
        CREATE FUNCTION users_keep_an_active_admin() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF OLD.role = 'admin' AND OLD.is_active AND NOT (NEW.role = 'admin' AND NEW.is_active)
               AND NOT EXISTS (SELECT 1 FROM users WHERE role = 'admin' AND is_active) THEN
                RAISE EXCEPTION 'the last active admin cannot be demoted or deactivated'
                    USING ERRCODE = '23514', CONSTRAINT = 'users_keep_an_active_admin';
            END IF;
            RETURN NULL;
        END $$
        """
    )
    op.execute(
        "CREATE CONSTRAINT TRIGGER users_keep_an_active_admin AFTER UPDATE ON users"
        " DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION users_keep_an_active_admin()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS users_keep_an_active_admin ON users")
    op.execute("DROP FUNCTION IF EXISTS users_keep_an_active_admin()")
    op.execute("DROP TRIGGER IF EXISTS users_no_delete ON users")
    op.execute("DROP TRIGGER IF EXISTS accounts_parent_not_postable ON accounts")
    op.execute("DROP FUNCTION IF EXISTS accounts_parent_not_postable()")
    for table in ("tax_rules", "posting_accounts", "closed_periods", "projects", "cost_centers", "categories"):
        op.drop_table(table)
    op.drop_table("accounts")
    op.drop_table("vendors")
    op.drop_table("auth_tokens")
    op.drop_table("refresh_tokens")
    op.execute("DROP FUNCTION IF EXISTS prevent_delete()")
    bind = op.get_bind()
    for old_enum in reversed(NEW_ENUMS):
        old_enum.drop(bind, checkfirst=True)
