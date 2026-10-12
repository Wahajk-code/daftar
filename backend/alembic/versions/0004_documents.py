"""expenses, allocations, purchases, purchase lines, attachments, the approval history, and the rules around them

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def enum(name: str, *values: str) -> postgresql.ENUM:
    return postgresql.ENUM(*values, name=name, create_type=False)


expense_type = enum("expense_type", "direct", "indirect")
allocation_method = enum("allocation_method", "percentage", "fixed")
payment_method = enum("payment_method", "cash", "bank_transfer", "card", "cheque")
purchase_kind = enum("purchase_kind", "tax_invoice", "purchase_memo")
document_type = enum("document_type", "expense", "purchase", "voucher")
document_status = enum("document_status", "draft", "submitted", "approved", "rejected", "posted", "void")
tax_category = enum("tax_category", "goods", "services", "contracts", "any")
NEW_ENUMS = (expense_type, allocation_method, payment_method, purchase_kind, document_type)

MONEY = sa.Numeric(14, 2)


def identity() -> sa.Column:  # type: ignore[type-arg]
    return sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False)


def money(name: str, default: str | None = None) -> sa.Column:  # type: ignore[type-arg]
    return sa.Column(name, MONEY, nullable=False, server_default=sa.text(default) if default else None)


def upgrade() -> None:
    bind = op.get_bind()
    for new_enum in NEW_ENUMS:
        new_enum.create(bind, checkfirst=True)

    op.create_table(
        "expenses",
        identity(),
        sa.Column("expense_type", expense_type, nullable=False),
        sa.Column("status", document_status, server_default=sa.text("'draft'"), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=False),
        sa.Column("document_date", sa.Date(), nullable=False),
        sa.Column("category_id", sa.BigInteger(), nullable=False),
        money("amount"),
        money("tax_amount", "0"),
        sa.Column("currency", sa.String(3), server_default=sa.text("'PKR'"), nullable=False),
        sa.Column("payment_method", payment_method, nullable=False),
        sa.Column("description", sa.String(1000), server_default=sa.text("''"), nullable=False),
        sa.Column("project_id", sa.BigInteger()),
        sa.Column("cost_center_id", sa.BigInteger()),
        sa.Column("allocation_method", allocation_method),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("amount > 0", name="amount_positive"),
        sa.CheckConstraint("tax_amount >= 0 AND tax_amount <= amount", name="tax_within_amount"),
        sa.CheckConstraint(
            "(expense_type = 'direct' AND (project_id IS NOT NULL OR cost_center_id IS NOT NULL)"
            " AND allocation_method IS NULL)"
            " OR (expense_type = 'indirect' AND project_id IS NULL AND cost_center_id IS NULL)",
            name="direct_has_attribution_indirect_has_none",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_expenses_created_by_users"),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], name="fk_expenses_category_id_categories"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name="fk_expenses_project_id_projects"),
        sa.ForeignKeyConstraint(["cost_center_id"], ["cost_centers.id"], name="fk_expenses_cost_center_id_cost_centers"),
        sa.PrimaryKeyConstraint("id", name="pk_expenses"),
    )
    op.create_index("ix_expenses_created_by", "expenses", ["created_by"])
    op.create_index("ix_expenses_status", "expenses", ["status"])
    op.create_index("ix_expenses_document_date", "expenses", ["document_date"])

    op.create_table(
        "expense_allocations",
        identity(),
        sa.Column("expense_id", sa.BigInteger(), nullable=False),
        sa.Column("cost_center_id", sa.BigInteger(), nullable=False),
        sa.Column("basis_points", sa.SmallInteger()),
        money("amount"),
        sa.CheckConstraint("amount >= 0", name="amount_not_negative"),
        sa.CheckConstraint("basis_points IS NULL OR basis_points BETWEEN 0 AND 10000", name="basis_points_in_range"),
        sa.ForeignKeyConstraint(["expense_id"], ["expenses.id"], name="fk_expense_allocations_expense_id_expenses"),
        sa.ForeignKeyConstraint(
            ["cost_center_id"], ["cost_centers.id"], name="fk_expense_allocations_cost_center_id_cost_centers"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_expense_allocations"),
        sa.UniqueConstraint("expense_id", "cost_center_id", name="one_row_per_cost_center"),
    )
    op.create_index("ix_expense_allocations_cost_center_id", "expense_allocations", ["cost_center_id"])

    op.create_table(
        "purchases",
        identity(),
        sa.Column("status", document_status, server_default=sa.text("'draft'"), nullable=False),
        sa.Column("vendor_id", sa.BigInteger(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=False),
        sa.Column("document_date", sa.Date(), nullable=False),
        sa.Column("document_kind", purchase_kind, nullable=False),
        sa.Column("invoice_number", sa.String(60)),
        sa.Column("description", sa.String(1000), server_default=sa.text("''"), nullable=False),
        sa.Column("vendor_registered", sa.Boolean(), nullable=False),
        sa.Column("vendor_filer", sa.Boolean(), nullable=False),
        sa.Column("currency", sa.String(3), server_default=sa.text("'PKR'"), nullable=False),
        money("subtotal"),
        money("sales_tax_total"),
        money("gross_total"),
        money("sales_tax_withheld"),
        money("income_tax_withheld"),
        money("payable"),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "(vendor_registered AND document_kind = 'tax_invoice')"
            " OR (NOT vendor_registered AND document_kind = 'purchase_memo')",
            name="kind_follows_registration",
        ),
        sa.CheckConstraint(
            "document_kind <> 'tax_invoice' OR length(btrim(coalesce(invoice_number, ''))) > 0",
            name="tax_invoice_has_a_number",
        ),
        sa.CheckConstraint("payable >= 0", name="payable_not_negative"),
        sa.CheckConstraint("gross_total = subtotal + sales_tax_total", name="gross_is_subtotal_plus_tax"),
        sa.CheckConstraint(
            "payable = gross_total - sales_tax_withheld - income_tax_withheld", name="payable_is_gross_less_withholdings"
        ),
        sa.ForeignKeyConstraint(["vendor_id"], ["vendors.id"], name="fk_purchases_vendor_id_vendors"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_purchases_created_by_users"),
        sa.PrimaryKeyConstraint("id", name="pk_purchases"),
    )
    op.create_index("ix_purchases_vendor_id", "purchases", ["vendor_id"])
    op.create_index("ix_purchases_created_by", "purchases", ["created_by"])
    op.create_index("ix_purchases_status", "purchases", ["status"])
    op.create_index("ix_purchases_document_date", "purchases", ["document_date"])

    op.create_table(
        "purchase_lines",
        identity(),
        sa.Column("purchase_id", sa.BigInteger(), nullable=False),
        sa.Column("line_no", sa.SmallInteger(), nullable=False),
        sa.Column("item", sa.String(200), nullable=False),
        sa.Column("category", tax_category, nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        money("rate"),
        sa.Column("sales_tax_bp", sa.SmallInteger(), nullable=False),
        money("subtotal"),
        money("sales_tax"),
        money("gross"),
        sa.Column("sales_withholding_rule_id", sa.BigInteger(), nullable=False),
        sa.Column("sales_withholding_bp", sa.SmallInteger(), nullable=False),
        money("sales_tax_withheld"),
        sa.Column("income_withholding_rule_id", sa.BigInteger(), nullable=False),
        sa.Column("income_withholding_bp", sa.SmallInteger(), nullable=False),
        money("income_tax_withheld"),
        money("payable"),
        sa.CheckConstraint("quantity > 0 AND rate > 0", name="quantity_and_rate_positive"),
        sa.CheckConstraint("subtotal > 0", name="subtotal_positive"),
        sa.CheckConstraint("sales_tax_bp BETWEEN 0 AND 10000", name="sales_tax_in_range"),
        sa.CheckConstraint("gross = subtotal + sales_tax", name="gross_is_subtotal_plus_tax"),
        sa.CheckConstraint(
            "payable = gross - sales_tax_withheld - income_tax_withheld", name="payable_is_gross_less_withholdings"
        ),
        sa.CheckConstraint("payable >= 0", name="payable_not_negative"),
        sa.ForeignKeyConstraint(["purchase_id"], ["purchases.id"], name="fk_purchase_lines_purchase_id_purchases"),
        sa.ForeignKeyConstraint(
            ["sales_withholding_rule_id"], ["tax_rules.id"], name="fk_purchase_lines_sales_withholding_rule_id_tax_rules"
        ),
        sa.ForeignKeyConstraint(
            ["income_withholding_rule_id"], ["tax_rules.id"], name="fk_purchase_lines_income_withholding_rule_id_tax_rules"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_purchase_lines"),
        sa.UniqueConstraint("purchase_id", "line_no", name="one_row_per_line_number"),
    )
    op.create_index("ix_purchase_lines_purchase_id", "purchase_lines", ["purchase_id"])

    op.create_table(
        "attachments",
        identity(),
        sa.Column("expense_id", sa.BigInteger()),
        sa.Column("purchase_id", sa.BigInteger()),
        sa.Column("storage_key", sa.String(200), nullable=False),
        sa.Column("content_type", sa.String(50), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("original_name", sa.String(255), nullable=False),
        sa.Column("uploaded_by", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("removed_at", sa.DateTime(timezone=True)),
        sa.Column("removed_by", sa.BigInteger()),
        sa.CheckConstraint("num_nonnulls(expense_id, purchase_id) = 1", name="exactly_one_parent"),
        sa.CheckConstraint("size_bytes > 0", name="size_positive"),
        sa.CheckConstraint("length(sha256) = 64", name="sha256_is_64_hex"),
        sa.CheckConstraint("(removed_at IS NULL) = (removed_by IS NULL)", name="removal_has_both_parts"),
        sa.ForeignKeyConstraint(["expense_id"], ["expenses.id"], name="fk_attachments_expense_id_expenses"),
        sa.ForeignKeyConstraint(["purchase_id"], ["purchases.id"], name="fk_attachments_purchase_id_purchases"),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"], name="fk_attachments_uploaded_by_users"),
        sa.ForeignKeyConstraint(["removed_by"], ["users.id"], name="fk_attachments_removed_by_users"),
        sa.PrimaryKeyConstraint("id", name="pk_attachments"),
        sa.UniqueConstraint("storage_key", name="uq_attachments_storage_key"),
    )
    op.create_index("ix_attachments_expense_id", "attachments", ["expense_id"])
    op.create_index("ix_attachments_purchase_id", "attachments", ["purchase_id"])
    op.create_index("ix_attachments_sha256", "attachments", ["sha256"])

    op.create_table(
        "document_events",
        identity(),
        sa.Column("document_type", document_type, nullable=False),
        sa.Column("document_id", sa.BigInteger(), nullable=False),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("from_status", document_status),
        sa.Column("to_status", document_status, nullable=False),
        sa.Column("actor_id", sa.BigInteger(), nullable=False),
        sa.Column("comment", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], name="fk_document_events_actor_id_users"),
        sa.PrimaryKeyConstraint("id", name="pk_document_events"),
    )
    op.create_index("ix_document_events_document", "document_events", ["document_type", "document_id", "id"])

    for table in ("expenses", "purchases", "attachments", "document_events"):
        op.execute(
            f"CREATE TRIGGER {table}_no_delete BEFORE DELETE ON {table}"
            " FOR EACH ROW EXECUTE FUNCTION prevent_delete()"
        )

    # Allocations add up, on both sides, checked at commit. Only an indirect expense has any; percentages total exactly
    # 10,000 basis points; amounts total exactly the expense. A deferred trigger sees the row as queued, so it reads the
    # expense and its allocations as they are now. (An indirect expense with no allocation rows passes: the service
    # refuses to submit it.)
    op.execute(
        """
        CREATE FUNCTION expense_allocations_consistent() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
            target_id bigint;
            expense expenses%ROWTYPE;
            row_count integer;
            amount_total numeric;
            bp_total bigint;
            bp_count integer;
        BEGIN
            IF TG_TABLE_NAME = 'expense_allocations' THEN
                target_id := COALESCE(NEW.expense_id, OLD.expense_id);
            ELSE
                target_id := NEW.id;
            END IF;
            SELECT * INTO expense FROM expenses WHERE id = target_id;
            IF NOT FOUND THEN
                RETURN NULL;
            END IF;
            SELECT count(*), COALESCE(sum(amount), 0), COALESCE(sum(basis_points), 0), count(basis_points)
              INTO row_count, amount_total, bp_total, bp_count
              FROM expense_allocations WHERE expense_id = target_id;
            IF row_count = 0 THEN
                RETURN NULL;
            END IF;
            IF expense.expense_type <> 'indirect' THEN
                RAISE EXCEPTION 'only an indirect expense has allocations'
                    USING ERRCODE = '23514', CONSTRAINT = 'expense_allocations_consistent';
            END IF;
            IF amount_total <> expense.amount THEN
                RAISE EXCEPTION 'allocations total % but the expense is %', amount_total, expense.amount
                    USING ERRCODE = '23514', CONSTRAINT = 'expense_allocations_consistent';
            END IF;
            IF expense.allocation_method = 'percentage' THEN
                IF bp_count <> row_count OR bp_total <> 10000 THEN
                    RAISE EXCEPTION 'percentage allocations must total exactly 10000 basis points'
                        USING ERRCODE = '23514', CONSTRAINT = 'expense_allocations_consistent';
                END IF;
            ELSIF expense.allocation_method = 'fixed' THEN
                IF bp_count <> 0 THEN
                    RAISE EXCEPTION 'fixed allocations carry amounts, not percentages'
                        USING ERRCODE = '23514', CONSTRAINT = 'expense_allocations_consistent';
                END IF;
            ELSE
                RAISE EXCEPTION 'allocations need an allocation method'
                    USING ERRCODE = '23514', CONSTRAINT = 'expense_allocations_consistent';
            END IF;
            RETURN NULL;
        END $$
        """
    )
    op.execute(
        "CREATE CONSTRAINT TRIGGER expense_allocations_consistent"
        " AFTER INSERT OR UPDATE OR DELETE ON expense_allocations"
        " DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION expense_allocations_consistent()"
    )
    op.execute(
        "CREATE CONSTRAINT TRIGGER expenses_allocations_consistent"
        " AFTER INSERT OR UPDATE OF amount, expense_type, allocation_method ON expenses"
        " DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION expense_allocations_consistent()"
    )

    # The header of a purchase is the exact sum of its lines, figure by figure.
    op.execute(
        """
        CREATE FUNCTION purchase_totals_match() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
            target_id bigint;
            header purchases%ROWTYPE;
            sums record;
        BEGIN
            IF TG_TABLE_NAME = 'purchase_lines' THEN
                target_id := COALESCE(NEW.purchase_id, OLD.purchase_id);
            ELSE
                target_id := NEW.id;
            END IF;
            SELECT * INTO header FROM purchases WHERE id = target_id;
            IF NOT FOUND THEN
                RETURN NULL;
            END IF;
            SELECT count(*) AS n, COALESCE(sum(subtotal), 0) AS subtotal, COALESCE(sum(sales_tax), 0) AS sales_tax,
                   COALESCE(sum(gross), 0) AS gross, COALESCE(sum(sales_tax_withheld), 0) AS sales_tax_withheld,
                   COALESCE(sum(income_tax_withheld), 0) AS income_tax_withheld, COALESCE(sum(payable), 0) AS payable
              INTO sums FROM purchase_lines WHERE purchase_id = target_id;
            IF sums.n = 0 THEN
                RETURN NULL;
            END IF;
            IF header.subtotal <> sums.subtotal OR header.sales_tax_total <> sums.sales_tax
               OR header.gross_total <> sums.gross OR header.sales_tax_withheld <> sums.sales_tax_withheld
               OR header.income_tax_withheld <> sums.income_tax_withheld OR header.payable <> sums.payable THEN
                RAISE EXCEPTION 'the purchase totals are not the sum of its lines'
                    USING ERRCODE = '23514', CONSTRAINT = 'purchase_totals_match';
            END IF;
            RETURN NULL;
        END $$
        """
    )
    op.execute(
        "CREATE CONSTRAINT TRIGGER purchase_totals_match AFTER INSERT OR UPDATE OR DELETE ON purchase_lines"
        " DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION purchase_totals_match()"
    )
    op.execute(
        "CREATE CONSTRAINT TRIGGER purchases_totals_match AFTER INSERT OR UPDATE ON purchases"
        " DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION purchase_totals_match()"
    )

    # Once a document leaves Draft nothing about it changes except its status: not its fields, not its lines.
    op.execute(
        """
        CREATE FUNCTION freeze_unless_draft() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF OLD.status <> 'draft'
               AND (to_jsonb(NEW) - 'status' - 'version' - 'updated_at')
                   IS DISTINCT FROM (to_jsonb(OLD) - 'status' - 'version' - 'updated_at') THEN
                RAISE EXCEPTION 'a % is not a draft and can no longer be changed', TG_TABLE_NAME
                    USING ERRCODE = '23514', CONSTRAINT = 'document_is_not_a_draft';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    for table in ("expenses", "purchases"):
        op.execute(
            f"CREATE TRIGGER {table}_freeze BEFORE UPDATE ON {table}"
            " FOR EACH ROW EXECUTE FUNCTION freeze_unless_draft()"
        )
    op.execute(
        """
        CREATE FUNCTION freeze_children_unless_draft() RETURNS trigger LANGUAGE plpgsql AS $$
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
    for table in ("expense_allocations", "purchase_lines"):
        op.execute(
            f"CREATE TRIGGER {table}_freeze BEFORE INSERT OR UPDATE OR DELETE ON {table}"
            " FOR EACH ROW EXECUTE FUNCTION freeze_children_unless_draft()"
        )


def downgrade() -> None:
    for table in ("attachments", "document_events", "purchase_lines", "purchases", "expense_allocations", "expenses"):
        op.drop_table(table)
    for function in (
        "freeze_children_unless_draft",
        "freeze_unless_draft",
        "purchase_totals_match",
        "expense_allocations_consistent",
    ):
        op.execute(f"DROP FUNCTION IF EXISTS {function}()")
    bind = op.get_bind()
    for old_enum in reversed(NEW_ENUMS):
        old_enum.drop(bind, checkfirst=True)
