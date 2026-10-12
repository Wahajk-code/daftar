"""starting withholding rates, each with its source and a note that it must be verified

Revision ID: 0003
Revises: 0002

These are configuration, not law. Published figures disagree and change with every Finance Act, so each row says where
the number came from and that it is unverified. An Admin edits or replaces a rule from the tax-rate screen; a saved
purchase keeps the rate it was given.
"""

import sqlalchemy as sa

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

FROM = "2025-07-01"

SALES_NOTE = (
    "UNVERIFIED starting value. Sales Tax Special Procedure (Withholding) Rules 2007, now in the Eleventh Schedule of "
    "the Sales Tax Act 1990 (ICAP withholding presentation, https://www.icap.org.pk/files/per/cpd/held/2020/"
    "AmnaBhatty-Withholding.pdf). {detail} Confirm against the current Eleventh Schedule and the latest Finance Act."
)
INCOME_NOTE = (
    "UNVERIFIED starting value. Income Tax Ordinance 2001, section 153, First Schedule Part III, indicative company "
    "rate for tax year 2025-26. Secondary guides disagree (https://ettc.pk/fbr-withholding-tax-rates-pakistan/ quotes "
    "goods 1% to 6% and contracts 7% for filers). Confirm against the First Schedule as amended by the latest Finance "
    "Act before relying on it."
)

SALES_RULES = [
    (True, "any", 2000, SALES_NOTE.format(detail="Registered supplier: one fifth (20%) of the sales tax shown on the invoice.")),
    (
        False,
        "any",
        1800,
        SALES_NOTE.format(
            detail="Unregistered supplier: the buyer withholds sales tax at the standard rate (18%) on the gross value."
        ),
    ),
]
# category -> (filer rate, non-filer rate) in basis points
INCOME_RATES = {"goods": (450, 900), "services": (900, 1800), "contracts": (700, 1400)}


def upgrade() -> None:
    rows: list[dict[str, object]] = []
    for registered, category, rate, source in SALES_RULES:
        rows.append(
            {
                "tax_type": "sales_tax_withholding",
                "supplier_registered": registered,
                "supplier_filer": False,
                "category": category,
                "rate_bp": rate,
                "effective_from": FROM,
                "source": source,
            }
        )
    for category, (filer_rate, non_filer_rate) in INCOME_RATES.items():
        for filer, rate in ((True, filer_rate), (False, non_filer_rate)):
            rows.append(
                {
                    "tax_type": "income_tax_withholding",
                    "supplier_registered": False,
                    "supplier_filer": filer,
                    "category": category,
                    "rate_bp": rate,
                    "effective_from": FROM,
                    "source": INCOME_NOTE,
                }
            )
    for row in rows:
        op.execute(
            sa.text(
                "INSERT INTO tax_rules (tax_type, supplier_registered, supplier_filer, category, rate_bp,"
                " effective_from, source) VALUES (CAST(:tax_type AS tax_type), :supplier_registered,"
                " :supplier_filer, CAST(:category AS tax_category), :rate_bp, CAST(:effective_from AS date), :source)"
            ).bindparams(**row)
        )


def downgrade() -> None:
    # The delete guard exists to protect history; removing the rows this migration seeded is the one legitimate delete.
    op.execute("ALTER TABLE tax_rules DISABLE TRIGGER tax_rules_no_delete")
    op.execute(
        sa.text("DELETE FROM tax_rules WHERE created_by IS NULL AND effective_from = CAST(:d AS date)").bindparams(
            d=FROM
        )
    )
    op.execute("ALTER TABLE tax_rules ENABLE TRIGGER tax_rules_no_delete")
