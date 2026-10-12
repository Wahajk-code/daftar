"""vouchers, voucher lines, number counters, the ledger rules around them, and a starting chart of accounts

Revision ID: 0005
Revises: 0004
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

voucher_type = postgresql.ENUM("PV", "RV", "JV", name="voucher_type", create_type=False)
document_status = postgresql.ENUM(
    "draft", "submitted", "approved", "rejected", "posted", "void", name="document_status", create_type=False
)
MONEY = sa.Numeric(14, 2)

# (code, name, type, parent code, postable). Parents hold their children and are never posted to.
CHART = [
    ("1000", "Assets", "asset", None, False),
    ("1100", "Cash in Hand", "asset", "1000", True),
    ("1200", "Bank - Meezan Current", "asset", "1000", True),
    ("1300", "Advance Tax Receivable", "asset", "1000", True),
    ("2000", "Liabilities", "liability", None, False),
    ("2100", "Accounts Payable", "liability", "2000", True),
    ("2200", "Sales Tax Payable", "liability", "2000", True),
    ("2300", "Withholding Tax Payable", "liability", "2000", True),
    ("3000", "Equity", "equity", None, False),
    ("3100", "Owner's Capital", "equity", "3000", True),
    ("4000", "Income", "income", None, False),
    ("4100", "Service Revenue", "income", "4000", True),
    ("5000", "Expenses", "expense", None, False),
    ("5100", "Rent", "expense", "5000", True),
    ("5200", "Utilities", "expense", "5000", True),
    ("5300", "Salaries", "expense", "5000", True),
    ("5400", "Materials", "expense", "5000", True),
    ("5500", "Travel", "expense", "5000", True),
    ("5600", "Office Supplies", "expense", "5000", True),
]
# Where a generated voucher posts by default; an Admin can change any of these.
POSTING_DEFAULTS = {
    "cash": "1100",
    "bank": "1200",
    "input_sales_tax": "1300",
    "sales_tax_withheld": "2200",
    "income_tax_withheld": "2300",
}
CATEGORIES = [
    ("Rent", "5100"),
    ("Utilities", "5200"),
    ("Salaries", "5300"),
    ("Materials", "5400"),
    ("Travel", "5500"),
    ("Office Supplies", "5600"),
]


def upgrade() -> None:
    bind = op.get_bind()
    voucher_type.create(bind, checkfirst=True)

    op.create_table(
        "number_counters",
        sa.Column("voucher_type", voucher_type, nullable=False),
        sa.Column("year", sa.SmallInteger(), nullable=False),
        sa.Column("last_seq", sa.Integer(), nullable=False),
        sa.CheckConstraint("last_seq >= 0", name="not_negative"),
        sa.PrimaryKeyConstraint("voucher_type", "year", name="pk_number_counters"),
    )

    op.create_table(
        "vouchers",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("voucher_type", voucher_type, nullable=False),
        sa.Column("status", document_status, server_default=sa.text("'draft'"), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=False),
        sa.Column("document_date", sa.Date(), nullable=False),
        sa.Column("description", sa.String(1000), server_default=sa.text("''"), nullable=False),
        sa.Column("number", sa.String(30)),
        sa.Column("year", sa.SmallInteger()),
        sa.Column("seq", sa.Integer()),
        sa.Column("expense_id", sa.BigInteger()),
        sa.Column("purchase_id", sa.BigInteger()),
        sa.Column("reversal_of_id", sa.BigInteger()),
        sa.Column("post_key", sa.String(100)),
        sa.Column("void_key", sa.String(100)),
        sa.Column("void_reason", sa.Text()),
        sa.Column("voided_at", sa.DateTime(timezone=True)),
        sa.Column("voided_by", sa.BigInteger()),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("(number IS NOT NULL) = (status IN ('posted', 'void'))", name="numbered_iff_posted_or_void"),
        sa.CheckConstraint(
            "(number IS NULL) = (year IS NULL) AND (number IS NULL) = (seq IS NULL)", name="number_parts_agree"
        ),
        sa.CheckConstraint(
            "(status = 'void' AND length(btrim(coalesce(void_reason, ''))) > 0 AND voided_by IS NOT NULL"
            " AND voided_at IS NOT NULL) OR (status <> 'void' AND void_reason IS NULL AND voided_by IS NULL"
            " AND voided_at IS NULL)",
            name="void_has_reason_and_actor",
        ),
        sa.CheckConstraint("reversal_of_id IS NULL OR status <> 'void'", name="a_reversal_cannot_be_voided"),
        sa.CheckConstraint("num_nonnulls(expense_id, purchase_id) <= 1", name="at_most_one_source"),
        sa.CheckConstraint(
            "reversal_of_id IS NULL OR num_nonnulls(expense_id, purchase_id) = 0", name="a_reversal_has_no_source"
        ),
        sa.CheckConstraint("void_key IS NULL OR status = 'void'", name="void_key_only_when_void"),
        sa.CheckConstraint("post_key IS NULL OR number IS NOT NULL", name="post_key_only_when_numbered"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_vouchers_created_by_users"),
        sa.ForeignKeyConstraint(["expense_id"], ["expenses.id"], name="fk_vouchers_expense_id_expenses"),
        sa.ForeignKeyConstraint(["purchase_id"], ["purchases.id"], name="fk_vouchers_purchase_id_purchases"),
        sa.ForeignKeyConstraint(["reversal_of_id"], ["vouchers.id"], name="fk_vouchers_reversal_of_id_vouchers"),
        sa.ForeignKeyConstraint(["voided_by"], ["users.id"], name="fk_vouchers_voided_by_users"),
        sa.PrimaryKeyConstraint("id", name="pk_vouchers"),
        sa.UniqueConstraint("voucher_type", "year", "seq", name="one_number_per_type_year"),
    )
    for name, column in (
        ("number", "number"),
        ("expense_id", "expense_id"),
        ("purchase_id", "purchase_id"),
        ("reversal_of_id", "reversal_of_id"),
        ("post_key", "post_key"),
        ("void_key", "void_key"),
    ):
        op.create_index(
            f"uq_vouchers_{name}",
            "vouchers",
            [column],
            unique=True,
            postgresql_where=sa.text(f"{column} IS NOT NULL"),
        )
    op.create_index("ix_vouchers_status", "vouchers", ["status"])
    op.create_index("ix_vouchers_document_date", "vouchers", ["document_date"])
    op.create_index("ix_vouchers_created_by", "vouchers", ["created_by"])

    op.create_table(
        "voucher_lines",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("voucher_id", sa.BigInteger(), nullable=False),
        sa.Column("line_no", sa.SmallInteger(), nullable=False),
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column("debit", MONEY, server_default=sa.text("0"), nullable=False),
        sa.Column("credit", MONEY, server_default=sa.text("0"), nullable=False),
        sa.Column("description", sa.String(500)),
        sa.Column("cost_center_id", sa.BigInteger()),
        sa.Column("project_id", sa.BigInteger()),
        sa.CheckConstraint("debit >= 0 AND credit >= 0 AND ((debit > 0) <> (credit > 0))", name="exactly_one_side"),
        sa.ForeignKeyConstraint(["voucher_id"], ["vouchers.id"], name="fk_voucher_lines_voucher_id_vouchers"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], name="fk_voucher_lines_account_id_accounts"),
        sa.ForeignKeyConstraint(
            ["cost_center_id"], ["cost_centers.id"], name="fk_voucher_lines_cost_center_id_cost_centers"
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name="fk_voucher_lines_project_id_projects"),
        sa.PrimaryKeyConstraint("id", name="pk_voucher_lines"),
        sa.UniqueConstraint("voucher_id", "line_no", name="one_voucher_line_per_number"),
    )
    op.create_index("ix_voucher_lines_voucher_id", "voucher_lines", ["voucher_id"])
    op.create_index("ix_voucher_lines_account_id", "voucher_lines", ["account_id"])
    op.create_index("ix_voucher_lines_cost_center_id", "voucher_lines", ["cost_center_id"])
    op.create_index("ix_voucher_lines_project_id", "voucher_lines", ["project_id"])

    # Lines of a draft are replaced when it is edited, so they can be deleted while Draft; once it leaves Draft the freeze
    # trigger below refuses any change to them, a delete included. The voucher and the counters are never deleted.
    for table in ("vouchers", "number_counters"):
        op.execute(
            f"CREATE TRIGGER {table}_no_delete BEFORE DELETE ON {table}"
            " FOR EACH ROW EXECUTE FUNCTION prevent_delete()"
        )

    # Debits equal credits, checked at commit. Lines arrive one at a time, so a normal trigger would fire after the first
    # and reject every voucher. The deferred trigger reads the lines as they are now, not as they were when queued.
    op.execute(
        """
        CREATE FUNCTION voucher_balanced() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
            target_id bigint;
            line_count integer;
            debit_total numeric;
            credit_total numeric;
        BEGIN
            target_id := COALESCE(NEW.voucher_id, OLD.voucher_id);
            SELECT count(*), COALESCE(sum(debit), 0), COALESCE(sum(credit), 0)
              INTO line_count, debit_total, credit_total
              FROM voucher_lines WHERE voucher_id = target_id;
            IF line_count > 0 AND debit_total <> credit_total THEN
                RAISE EXCEPTION 'voucher debits % and credits % are not equal', debit_total, credit_total
                    USING ERRCODE = '23514', CONSTRAINT = 'voucher_balanced';
            END IF;
            RETURN NULL;
        END $$
        """
    )
    op.execute(
        "CREATE CONSTRAINT TRIGGER voucher_balanced AFTER INSERT OR UPDATE OR DELETE ON voucher_lines"
        " DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION voucher_balanced()"
    )

    # A line may only post to an account that can be posted to. (Active is not required: a reversal must be able to mirror
    # a line on an account deactivated since.)
    op.execute(
        """
        CREATE FUNCTION voucher_line_account_postable() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NOT (SELECT is_postable FROM accounts WHERE id = NEW.account_id) THEN
                RAISE EXCEPTION 'account % is a parent account and cannot be posted to', NEW.account_id
                    USING ERRCODE = '23514', CONSTRAINT = 'voucher_line_account_postable';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER voucher_line_account_postable BEFORE INSERT OR UPDATE OF account_id ON voucher_lines"
        " FOR EACH ROW EXECUTE FUNCTION voucher_line_account_postable()"
    )

    # An account with postings cannot become a parent (it would stop being postable under existing entries).
    op.execute(
        """
        CREATE OR REPLACE FUNCTION accounts_parent_not_postable() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
            current_row accounts%ROWTYPE;
        BEGIN
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
            IF NOT current_row.is_postable AND EXISTS (SELECT 1 FROM voucher_lines WHERE account_id = current_row.id) THEN
                RAISE EXCEPTION 'account % has postings and cannot stop being postable', current_row.code
                    USING ERRCODE = '23514', CONSTRAINT = 'account_has_postings';
            END IF;
            RETURN NULL;
        END $$
        """
    )

    # Lines are frozen once the voucher leaves Draft. Extends the function from 0004 with the voucher branch.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION freeze_children_unless_draft() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
            parent_status document_status;
            parent_id bigint;
        BEGIN
            IF TG_TABLE_NAME = 'expense_allocations' THEN
                parent_id := COALESCE(NEW.expense_id, OLD.expense_id);
                SELECT status INTO parent_status FROM expenses WHERE id = parent_id;
            ELSIF TG_TABLE_NAME = 'purchase_lines' THEN
                parent_id := COALESCE(NEW.purchase_id, OLD.purchase_id);
                SELECT status INTO parent_status FROM purchases WHERE id = parent_id;
            ELSE
                parent_id := COALESCE(NEW.voucher_id, OLD.voucher_id);
                SELECT status INTO parent_status FROM vouchers WHERE id = parent_id;
            END IF;
            IF parent_status IS NOT NULL AND parent_status <> 'draft' THEN
                RAISE EXCEPTION 'the document is not a draft, so its lines can no longer be changed'
                    USING ERRCODE = '23514', CONSTRAINT = 'document_is_not_a_draft';
            END IF;
            RETURN COALESCE(NEW, OLD);
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER voucher_lines_freeze BEFORE INSERT OR UPDATE OR DELETE ON voucher_lines"
        " FOR EACH ROW EXECUTE FUNCTION freeze_children_unless_draft()"
    )

    # The voucher itself: after Draft only the status, the number, the idempotency keys and the void details may be written,
    # a number once given never changes, a void voucher stays void, and a posted one can only be voided.
    op.execute(
        """
        CREATE FUNCTION freeze_voucher_unless_draft() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
            mutable text[] := ARRAY['status', 'version', 'updated_at', 'number', 'year', 'seq', 'post_key', 'void_key',
                                    'void_reason', 'voided_at', 'voided_by'];
        BEGIN
            IF OLD.status = 'draft' THEN
                RETURN NEW;
            END IF;
            IF (to_jsonb(NEW) - mutable) IS DISTINCT FROM (to_jsonb(OLD) - mutable) THEN
                RAISE EXCEPTION 'a voucher is not a draft and can no longer be changed'
                    USING ERRCODE = '23514', CONSTRAINT = 'document_is_not_a_draft';
            END IF;
            IF OLD.number IS NOT NULL AND (NEW.number IS DISTINCT FROM OLD.number OR NEW.year IS DISTINCT FROM OLD.year
               OR NEW.seq IS DISTINCT FROM OLD.seq OR NEW.post_key IS DISTINCT FROM OLD.post_key) THEN
                RAISE EXCEPTION 'a voucher number is never changed'
                    USING ERRCODE = '23514', CONSTRAINT = 'voucher_number_is_permanent';
            END IF;
            IF OLD.status = 'void' AND NEW.status <> 'void' THEN
                RAISE EXCEPTION 'a void voucher stays void' USING ERRCODE = '23514', CONSTRAINT = 'voucher_stays_void';
            END IF;
            IF OLD.status = 'posted' AND NEW.status NOT IN ('posted', 'void') THEN
                RAISE EXCEPTION 'a posted voucher can only be voided'
                    USING ERRCODE = '23514', CONSTRAINT = 'voucher_stays_void';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER vouchers_freeze BEFORE UPDATE ON vouchers"
        " FOR EACH ROW EXECUTE FUNCTION freeze_voucher_unless_draft()"
    )

    # A starting chart, so a fresh install can generate a voucher. Accounts, categories and where tax posts are all
    # editable by an Admin; demonstration users and documents come from the seed in Pass 5.
    for code, name, kind, parent, postable in CHART:
        op.execute(
            sa.text(
                "INSERT INTO accounts (code, name, type, parent_id, is_postable) SELECT :code, :name,"
                " CAST(:kind AS account_type), (SELECT id FROM accounts WHERE code = :parent), :postable"
            ).bindparams(code=code, name=name, kind=kind, parent=parent, postable=postable)
        )
    for key, code in POSTING_DEFAULTS.items():
        op.execute(
            sa.text(
                "INSERT INTO posting_accounts (key, account_id) SELECT CAST(:key AS posting_key), id FROM accounts"
                " WHERE code = :code"
            ).bindparams(key=key, code=code)
        )
    for name, code in CATEGORIES:
        op.execute(
            sa.text(
                "INSERT INTO categories (name, account_id) SELECT :name, id FROM accounts WHERE code = :code"
            ).bindparams(name=name, code=code)
        )


def downgrade() -> None:
    op.drop_table("voucher_lines")
    op.drop_table("vouchers")
    op.drop_table("number_counters")
    for function in (
        "freeze_voucher_unless_draft",
        "voucher_line_account_postable",
        "voucher_balanced",
    ):
        op.execute(f"DROP FUNCTION IF EXISTS {function}()")
    # The seeded starting data is the one thing this migration may remove from tables that are never deleted from.
    codes = [c for c, *_ in CHART]
    for table in ("categories", "posting_accounts", "accounts"):
        op.execute(f"ALTER TABLE {table} DISABLE TRIGGER {table}_no_delete")
    for table in ("categories", "posting_accounts"):
        statement = f"DELETE FROM {table} WHERE account_id IN (SELECT id FROM accounts WHERE code = ANY(:c))"
        op.execute(sa.text(statement).bindparams(c=codes))
    op.execute(sa.text("DELETE FROM accounts WHERE code = ANY(:c) AND parent_id IS NOT NULL").bindparams(c=codes))
    op.execute(sa.text("DELETE FROM accounts WHERE code = ANY(:c)").bindparams(c=codes))
    for table in ("categories", "posting_accounts", "accounts"):
        op.execute(f"ALTER TABLE {table} ENABLE TRIGGER {table}_no_delete")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION accounts_parent_not_postable() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
            current_row accounts%ROWTYPE;
        BEGIN
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
        """
        CREATE OR REPLACE FUNCTION freeze_children_unless_draft() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
            parent_status document_status;
            parent_id bigint;
        BEGIN
            IF TG_TABLE_NAME = 'expense_allocations' THEN
                parent_id := COALESCE(NEW.expense_id, OLD.expense_id);
                SELECT status INTO parent_status FROM expenses WHERE id = parent_id;
            ELSE
                parent_id := COALESCE(NEW.purchase_id, OLD.purchase_id);
                SELECT status INTO parent_status FROM purchases WHERE id = parent_id;
            END IF;
            IF parent_status IS NOT NULL AND parent_status <> 'draft' THEN
                RAISE EXCEPTION 'the document is not a draft, so its lines can no longer be changed'
                    USING ERRCODE = '23514', CONSTRAINT = 'document_is_not_a_draft';
            END IF;
            RETURN COALESCE(NEW, OLD);
        END $$
        """
    )
    bind = op.get_bind()
    voucher_type.drop(bind, checkfirst=True)
