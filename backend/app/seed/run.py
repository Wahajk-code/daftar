"""Build the demonstration data by using the real services, in date order, as the four demonstration people would.

Because it goes through the same code as the API, every rule applies to the seed too: balanced vouchers, gapless
numbers, the approval rules, the period lock. Periods are closed last, so the history can be posted first. The clock
is moved through the window so each row, event and audit record carries a believable time."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.core.allocation import largest_remainder
from app.core.clock import Clock
from app.core.enums import PaymentMethod, Role
from app.core.mail import Outbox
from app.core.principal import Principal
from app.core.rate_limit import RateLimiter, build_policies
from app.core.security import Passwords
from app.core.storage import Storage
from app.models.documents import Attachment, Expense, Purchase
from app.models.master import Account, Category, ClosedPeriod
from app.models.user import User
from app.models.vouchers import Voucher
from app.schemas.documents import ExpenseCreate, PurchaseCreate
from app.schemas.master import CostCenterCreate, ProjectCreate
from app.schemas.vendors import VendorCreate
from app.schemas.vouchers import VoucherCreate
from app.seed import data
from app.seed.receipts import receipt_image
from app.services.attachments import AttachmentService
from app.services.audit import AuditService
from app.services.expenses import ExpenseService
from app.services.lookups import CostCenterService, ProjectService
from app.services.periods import PeriodService
from app.services.purchases import PurchaseService
from app.services.vendors import VendorService
from app.services.vouchers import VoucherService

MORNING = 6  # hour in UTC; 11:00 in Karachi, so a moment never falls on the wrong side of midnight there
RANK = {"posted": 0, "rejected": 1, "approved": 2, "submitted": 3, "draft": 4}


class SeedClock(Clock):
    """The seed's own clock, moved from story to story. Services only ever ask it for the time."""

    def __init__(self, start: datetime) -> None:
        self._now = start

    def now(self) -> datetime:
        return self._now

    def set(self, day: date, hour: int = MORNING) -> None:
        self._now = datetime(day.year, day.month, day.day, hour, 0, tzinfo=UTC)

    def tick(self) -> None:
        self._now += timedelta(minutes=7)


@dataclass
class Story:
    """One document or voucher to create, with the day it is dated and how far the seed takes it."""

    day: date
    order: int
    kind: str  # "expense", "purchase" or "voucher"
    index: int  # its place in the table in data.py
    spec: Any


@dataclass
class Summary:
    users: int = 0
    expenses: dict[str, int] = field(default_factory=dict)
    purchases: dict[str, int] = field(default_factory=dict)
    vouchers: dict[str, int] = field(default_factory=dict)
    attachments: int = 0
    closed_periods: int = 0
    already_seeded: bool = False


def first_of_next_month(day: date) -> date:
    return (day.replace(day=1) + timedelta(days=31)).replace(day=1)


def spread(first: date, last: date, count: int) -> list[date]:
    """`count` dates running from `first` to `last`, evenly, with the rounding shared out by the allocation module."""
    days = (last - first).days
    if count <= 1 or days <= 0:
        return [first] * count
    steps = largest_remainder(days, [(index, 1) for index in range(count - 1)])
    result = [first]
    for share in steps:
        result.append(result[-1] + timedelta(days=share.paisa))
    return result


class Seeder:
    def __init__(self, session: Session, settings: Settings, storage: Storage, now: datetime) -> None:
        self.session = session
        self.settings = settings
        self.zone = ZoneInfo(settings.display_timezone)
        self.clock = SeedClock(now)
        self.today = now.astimezone(self.zone).date()
        outbox = Outbox()  # nothing is emailed while seeding: the messages are collected and dropped
        limiter = RateLimiter(self.clock, build_policies({}))
        passwords = Passwords(
            time_cost=settings.argon2_time_cost,
            memory_cost_kib=settings.argon2_memory_kib,
            parallelism=settings.argon2_parallelism,
        )
        self.passwords = passwords
        self.audit = AuditService(session, self.clock)
        self.expenses = ExpenseService(session, self.clock, settings, outbox)
        self.purchases = PurchaseService(session, self.clock, settings, outbox)
        self.vouchers = VoucherService(session, self.clock, settings, outbox)
        self.attachments = AttachmentService(session, self.clock, settings, storage, limiter)
        self.vendors = VendorService(session, self.clock, settings, passwords, limiter, outbox)
        self.cost_centre_service = CostCenterService(session, self.clock)
        self.project_service = ProjectService(session, self.clock)
        self.periods = PeriodService(session, self.clock)
        self.people: dict[str, Principal] = {}
        self.centres: dict[str, int] = {}
        self.project_ids: dict[str, int] = {}
        self.vendor_ids: dict[str, int] = {}
        self.categories: dict[str, int] = {}
        self.accounts: dict[str, int] = {}
        self.void_target: int | None = None
        self.window_start = self.today
        self.second_month_end = self.today
        self.receipt_bytes: dict[str, bytes] = {}

    # Set-up ----------------------------------------------------------------------------------------------------------

    def create_people(self) -> None:
        self.clock.set(self.today - timedelta(days=100))
        for email, name, role in data.USERS:
            user = User(
                email=email,
                full_name=name,
                password_hash=self.passwords.hash(data.DEMO_PASSWORD),
                role=Role(role),
            )
            self.session.add(user)
            self.session.flush()
            self.audit.record(
                actor_id=None, action="user.seeded", entity_type="user", entity_id=user.id, after={"role": role}
            )
            self.people[role] = Principal(id=user.id, email=email, full_name=name, role=Role(role))
        self.session.commit()

    def create_reference_data(self) -> None:
        bookkeeper = self.people["accountant"]
        for code, name in data.COST_CENTRES:
            centre = self.cost_centre_service.create(
                bookkeeper, CostCenterCreate.model_validate({"code": code, "name": name}).model_dump()
            )
            self.centres[code] = centre.id
        for code, name in data.PROJECTS:
            project = self.project_service.create(
                bookkeeper, ProjectCreate.model_validate({"code": code, "name": name, "kind": "project"}).model_dump()
            )
            self.project_ids[code] = project.id
        for vendor in data.VENDORS:
            body = {
                "name": vendor.name,
                "is_sales_tax_registered": vendor.registered,
                "is_filer": vendor.filer,
                "ntn": vendor.ntn,
                "strn": vendor.strn,
                "contact_name": vendor.contact,
                "phone": vendor.phone,
                "email": vendor.email or None,
                "address": vendor.address,
                "bank_name": vendor.bank_name,
                "bank_account_number": vendor.bank_account,
            }
            created = self.vendors.create(bookkeeper, VendorCreate.model_validate(body).model_dump())
            self.vendor_ids[vendor.key] = created.id
        self.categories = {name: row_id for row_id, name in self.session.execute(select(Category.id, Category.name))}
        self.accounts = {code: row_id for row_id, code in self.session.execute(select(Account.id, Account.code))}
        self.receipt_bytes = {name: receipt_image(name) for name in data.RECEIPTS}

    # Stories ---------------------------------------------------------------------------------------------------------

    def schedule(self) -> list[Story]:
        """Every story with its date, in the order they should happen. Finished work (it ends Posted) falls in the two
        months that will be closed; everything still in progress falls in the current month."""
        month_one = (self.today.replace(day=1) - timedelta(days=1)).replace(day=1)
        self.window_start = (month_one - timedelta(days=1)).replace(day=1)
        self.second_month_end = self.today.replace(day=1) - timedelta(days=1)

        stories = [Story(self.today, 0, "expense", i, spec) for i, spec in enumerate(data.EXPENSES)]
        stories += [Story(self.today, 0, "purchase", i, spec) for i, spec in enumerate(data.PURCHASES)]
        stories += [Story(self.today, 0, "voucher", i, spec) for i, spec in enumerate(data.MANUAL_VOUCHERS)]

        def ends_posted(story: Story) -> bool:
            return story.kind == "voucher" or story.spec.status == "posted"

        def rank(story: Story) -> tuple[int, int, str]:
            status = "posted" if story.kind == "voucher" else story.spec.status
            return RANK[status], story.index, story.kind

        stories.sort(key=rank)
        finished = [story for story in stories if ends_posted(story)]
        in_progress = [story for story in stories if not ends_posted(story)]
        history = spread(self.window_start, self.second_month_end, len(finished))
        recent = spread(self.today.replace(day=1), self.today, len(in_progress))
        for order, (story, day) in enumerate(zip(finished + in_progress, history + recent, strict=True)):
            story.day, story.order = day, order

        # A near-duplicate is entered a couple of days after the original.
        dated = {(story.kind, story.index): story.day for story in stories}
        for story in stories:
            if story.kind == "purchase" and story.spec.days_after:
                original = max(i for i in range(story.index) if data.PURCHASES[i].invoice == story.spec.invoice)
                story.day = min(self.today, dated[("purchase", original)] + timedelta(days=story.spec.days_after))
        return sorted(stories, key=lambda story: (story.day, story.order))

    def play(self, story: Story) -> None:
        self.clock.set(story.day)
        if story.kind == "expense":
            self._expense(story.spec, story.index, story.day)
        elif story.kind == "purchase":
            self._purchase(story.spec, story.index, story.day)
        else:
            self._manual_voucher(story.spec, story.index, story.day)

    def _move(self, service: Any, action: str, actor: Principal, document: Any, *extra: Any) -> Any:
        self.clock.tick()
        return getattr(service, action)(actor, document.id, document.version, *extra)

    def _voucher_day(self, day: date) -> date:
        """A generated voucher is dated the day after its source, never past the end of the history it falls in."""
        limit = self.second_month_end if day <= self.second_month_end else self.today
        return min(day + timedelta(days=1), limit)

    def _walk_voucher(self, voucher: Any, day: date, key: str) -> Any:
        self.clock.set(self._voucher_day(day))
        bookkeeper, approver = self.people["accountant"], self.people["approver"]
        voucher = self._move(self.vouchers, "submit", bookkeeper, voucher)
        voucher = self._move(self.vouchers, "approve", approver, voucher, None)
        self.clock.tick()
        return self.vouchers.post(bookkeeper, voucher.id, voucher.version, key)

    def _attach(self, actor: Principal, kind: str, document_id: int, receipt: str | None) -> None:
        if receipt is None:
            return
        self.clock.tick()
        self.attachments.upload(actor, kind, document_id, f"{receipt}.jpg", self.receipt_bytes[receipt])  # type: ignore[arg-type]

    def _expense(self, spec: data.ExpenseSeed, index: int, day: date) -> None:
        author = self.people[spec.author]
        body: dict[str, Any] = {
            "expense_type": "indirect" if spec.split else "direct",
            "document_date": day,
            "category_id": self.categories[spec.category],
            "amount": spec.amount,
            "tax_amount": spec.tax,
            "payment_method": spec.method,
            "description": spec.description,
        }
        if spec.split:
            lines = [{"cost_center_id": self.centres[code], "basis_points": bp} for code, bp in spec.split]
            body["allocation"] = {"method": "percentage", "lines": lines}
        elif spec.project:
            body["project_id"] = self.project_ids[spec.project]
        else:
            body["cost_center_id"] = self.centres[spec.centre or "HO"]
        expense = self.expenses.create(author, ExpenseCreate.model_validate(body).model_dump())
        self._attach(author, "expense", expense.id, spec.receipt)
        if spec.status == "draft":
            return
        approver = self.people["approver"]
        expense = self._move(self.expenses, "submit", author, expense)
        if spec.status == "rejected":
            self._move(self.expenses, "reject", approver, expense, spec.comment)
        elif spec.status in {"approved", "posted"}:
            expense = self._move(self.expenses, "approve", approver, expense, None)
            if spec.status == "posted" or spec.voucher_draft:
                self.clock.set(self._voucher_day(day))
                voucher = self.vouchers.generate_from_expense(self.people["accountant"], expense.id)
                if spec.status == "posted":
                    self._walk_voucher(voucher, day, f"seed-expense-{index}-post")

    def _purchase(self, spec: data.PurchaseSeed, index: int, day: date) -> None:
        author = self.people["accountant"]
        body: dict[str, Any] = {
            "vendor_id": self.vendor_ids[spec.vendor],
            "document_date": day,
            "invoice_number": spec.invoice,
            "description": spec.description,
            "lines": [
                {"item": item, "category": category, "quantity": quantity, "rate": rate, "sales_tax_bp": tax}
                for item, category, quantity, rate, tax in spec.lines
            ],
        }
        purchase = self.purchases.create(author, PurchaseCreate.model_validate(body).model_dump())
        self._attach(author, "purchase", purchase.id, spec.receipt)
        if spec.status == "draft":
            return
        approver = self.people["approver"]
        purchase = self._move(self.purchases, "submit", author, purchase)
        if spec.status == "rejected":
            self._move(self.purchases, "reject", approver, purchase, spec.comment)
        elif spec.status in {"approved", "posted"}:
            purchase = self._move(self.purchases, "approve", approver, purchase, None)
            if spec.status == "posted":
                self.clock.set(self._voucher_day(day))
                voucher = self.vouchers.generate_from_purchase(
                    author, purchase.id, self.categories[spec.category], PaymentMethod(spec.method)
                )
                posted = self._walk_voucher(voucher, day, f"seed-purchase-{index}-post")
                if spec.void:
                    self.void_target = posted.id

    def _manual_voucher(self, spec: data.ManualVoucherSeed, index: int, day: date) -> None:
        author = self.people["accountant"]
        body = {
            "voucher_type": spec.voucher_type,
            "document_date": day,
            "description": spec.description,
            "lines": [{"account_id": self.accounts[code], side: amount} for code, side, amount in spec.lines],
        }
        voucher = self.vouchers.create(author, VoucherCreate.model_validate(body).model_dump())
        self._walk_voucher(voucher, day, f"seed-manual-{index}-post")

    # Last steps ------------------------------------------------------------------------------------------------------

    def void_one(self) -> None:
        if self.void_target is None:
            return
        self.clock.set(self.today.replace(day=1), hour=MORNING + 3)
        voucher = self.vouchers.get(self.void_target)
        self.vouchers.void(self.people["admin"], voucher.id, voucher.version, data.VOID_REASON, "seed-void-1")

    def close_history(self) -> None:
        """The two months before this one are over: close them, so a change dated in them is refused."""
        self.clock.set(self.today, hour=MORNING + 2)
        first_end = first_of_next_month(self.window_start) - timedelta(days=1)
        self.periods.close(self.people["admin"], self.window_start, first_end)
        self.periods.close(self.people["admin"], first_end + timedelta(days=1), self.second_month_end)

    def summary(self) -> Summary:
        def counts(model: Any) -> dict[str, int]:
            rows = self.session.execute(select(model.status, func.count()).group_by(model.status))
            return {status.value: count for status, count in rows}

        return Summary(
            users=int(self.session.scalar(select(func.count()).select_from(User)) or 0),
            expenses=counts(Expense),
            purchases=counts(Purchase),
            vouchers=counts(Voucher),
            attachments=int(self.session.scalar(select(func.count()).select_from(Attachment)) or 0),
            closed_periods=int(self.session.scalar(select(func.count()).select_from(ClosedPeriod)) or 0),
        )


def seed(session: Session, settings: Settings, storage: Storage, now: datetime) -> Summary:
    """Create the demonstration data, once. If the demonstration administrator already exists, change nothing."""
    exists = session.scalar(select(User.id).where(User.email == data.USERS[0][0]))
    if exists is not None:
        summary = Seeder(session, settings, storage, now).summary()
        summary.already_seeded = True
        return summary
    seeder = Seeder(session, settings, storage, now)
    seeder.create_people()
    seeder.create_reference_data()
    for story in seeder.schedule():
        seeder.play(story)
    seeder.void_one()
    seeder.close_history()
    return seeder.summary()


def describe(summary: Summary) -> Sequence[str]:
    def line(label: str, counts: dict[str, int]) -> str:
        parts = ", ".join(f"{count} {status}" for status, count in sorted(counts.items()))
        return f"  {label}: {sum(counts.values())} ({parts})"

    return [
        f"  users: {summary.users}",
        line("expenses", summary.expenses),
        line("purchases", summary.purchases),
        line("vouchers", summary.vouchers),
        f"  receipts: {summary.attachments}",
        f"  closed periods: {summary.closed_periods}",
    ]
