"""A brand new install, migrated from nothing, can generate a voucher with no set-up beyond a cost centre.

The fast tests empty the starting chart so they can build their own; this one keeps it, in a scratch database."""

from typing import Any

import httpx2
import pytest
from sqlalchemy import text

from app.config import Settings
from app.core.enums import Role
from tests.support.parallel import Parallel, parallel_app

pytestmark = pytest.mark.concurrency


def send(world: Parallel, user: Any, method: str, path: str, body: dict[str, Any] | None = None, **extra: str) -> Any:
    """One request as `user`, which must succeed; returns the JSON."""

    async def request(client: httpx2.AsyncClient) -> httpx2.Response:
        return await client.request(method, path, json=body, headers={**world.headers(user), **extra})

    response = world.run([request])[0]
    assert response.status_code < 300, (method, path, response.status_code, response.text)
    return response.json()


def test_e4_a_fresh_install_ships_a_chart_where_tax_and_payments_post(settings: Settings) -> None:
    with parallel_app(settings) as world:
        with world.factory() as session:
            accounts = session.execute(text("SELECT code, is_postable, parent_id IS NULL FROM accounts")).all()
            keys: dict[str, str] = dict(
                session.execute(
                    text("SELECT key, a.code FROM posting_accounts p JOIN accounts a ON a.id = p.account_id")
                ).all()
            )
            categories = session.execute(
                text("SELECT c.name, a.code, a.type FROM categories c JOIN accounts a ON a.id = c.account_id")
            ).all()
        assert len(accounts) == 19
        assert {code for code, postable, is_root in accounts if is_root} == {"1000", "2000", "3000", "4000", "5000"}
        assert all(not postable for _, postable, is_root in accounts if is_root)  # parents are never posted to
        assert all(postable for _, postable, is_root in accounts if not is_root)
        assert keys == {
            "cash": "1100",
            "bank": "1200",
            "input_sales_tax": "1300",
            "sales_tax_withheld": "2200",
            "income_tax_withheld": "2300",
        }
        assert len(categories) == 6
        assert {kind for *_, kind in categories} == {"expense"}


def test_e4_a_fresh_install_runs_the_whole_flow_from_expense_to_void(settings: Settings) -> None:
    with parallel_app(settings) as world:
        bookkeeper, approver = world.make(Role.ACCOUNTANT), world.make(Role.APPROVER)
        staff = world.make(Role.STAFF)

        centre = send(world, bookkeeper, "POST", "/api/v1/cost-centers", {"code": "HO", "name": "Head Office"})
        category = world.scalar("SELECT id FROM categories WHERE name = 'Office Supplies'")
        expense = send(
            world,
            staff,
            "POST",
            "/api/v1/expenses",
            {
                "expense_type": "direct",
                "category_id": category,
                "amount": "2360.00",
                "tax_amount": "360.00",
                "payment_method": "bank_transfer",
                "description": "Toner",
                "cost_center_id": centre["id"],
            },
        )
        expense = send(
            world,
            staff,
            "POST",
            f"/api/v1/expenses/{expense['id']}/submit",
            None,
            **{"If-Match": str(expense["version"])},
        )
        send(
            world,
            approver,
            "POST",
            f"/api/v1/expenses/{expense['id']}/approve",
            None,
            **{"If-Match": str(expense["version"])},
        )
        voucher = send(world, bookkeeper, "POST", f"/api/v1/expenses/{expense['id']}/generate-voucher")
        assert [(ln["account_code"], ln["debit"], ln["credit"]) for ln in voucher["lines"]] == [
            ("5600", "2000.00", "0.00"),
            ("1300", "360.00", "0.00"),
            ("1200", "0.00", "2360.00"),
        ]
        voucher = send(
            world,
            bookkeeper,
            "POST",
            f"/api/v1/vouchers/{voucher['id']}/submit",
            None,
            **{"If-Match": str(voucher["version"])},
        )
        voucher = send(
            world,
            approver,
            "POST",
            f"/api/v1/vouchers/{voucher['id']}/approve",
            None,
            **{"If-Match": str(voucher["version"])},
        )
        posted = send(
            world,
            bookkeeper,
            "POST",
            f"/api/v1/vouchers/{voucher['id']}/post",
            None,
            **{"If-Match": str(voucher["version"]), "Idempotency-Key": "fresh-install-first-post"},
        )
        assert posted["status"] == "posted"
        assert posted["number"].startswith("PV-")
        assert posted["number"].endswith("-0001")
        assert world.scalar("SELECT status FROM expenses WHERE id = :i", i=expense["id"]) == "posted"

        # The last step of the whole flow: an Admin voids it, which posts the mirror image and links the two.
        admin = world.make(Role.ADMIN)
        voided = send(
            world,
            admin,
            "POST",
            f"/api/v1/vouchers/{posted['id']}/void",
            {"reason": "Paid twice"},
            **{"If-Match": str(posted["version"]), "Idempotency-Key": "fresh-install-first-void"},
        )
        assert voided["voucher"]["status"] == "void"
        assert voided["reversal"]["status"] == "posted"
        assert voided["reversal"]["reversal_of_number"] == posted["number"]
        assert voided["reversal"]["number"].endswith("-0002")
        assert world.scalar("SELECT count(*) FROM vouchers WHERE number IS NOT NULL") == 2
        assert world.scalar("SELECT status FROM expenses WHERE id = :i", i=expense["id"]) == "posted"
