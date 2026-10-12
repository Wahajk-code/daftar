"""Vendors. The bank account is encrypted at rest and never returned; changing it needs the password again, notifies the
people who should hear of it, and is audited with the old and new last four digits only."""

import re
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.config import Settings
from app.core import mail_templates
from app.core.clock import Clock, format_display_instant
from app.core.crypto import FieldCipher
from app.core.enums import Role
from app.core.errors import FieldError, NotFoundError, ValidationFailedError
from app.core.mail import Outbox
from app.core.principal import Principal
from app.core.rate_limit import RateLimiter
from app.core.security import Passwords
from app.models.base import JsonDict
from app.models.vendor import Vendor
from app.repositories import users as user_repository
from app.repositories import vendors as vendor_repository
from app.services.audit import AuditService
from app.services.master import changed, check_version, reauthenticate, snapshot

FIELDS = (
    "name",
    "is_sales_tax_registered",
    "is_filer",
    "ntn",
    "strn",
    "contact_name",
    "phone",
    "email",
    "address",
    "bank_name",
    "is_active",
)
ACCOUNT_NUMBER = re.compile(r"^[A-Z0-9]{8,34}$")


def normalise_account_number(raw: str) -> str:
    cleaned = re.sub(r"[\s-]", "", raw).upper()
    if not ACCOUNT_NUMBER.match(cleaned):
        raise ValidationFailedError(
            "Enter the account number or IBAN without punctuation.",
            errors=[FieldError("account_number", "Use 8 to 34 letters and digits.", "invalid_account_number")],
        )
    return cleaned


def require_registration_details(registered: bool, ntn: str | None, strn: str | None) -> None:
    """A registered vendor needs both numbers. The database checks this too; this gives the person a field to fix."""
    if not registered:
        return
    errors = [
        FieldError(name, f"A registered vendor needs an {name.upper()}.", "required")
        for name, value in (("ntn", ntn), ("strn", strn))
        if not (value and value.strip())
    ]
    if errors:
        raise ValidationFailedError("A sales-tax-registered vendor needs an NTN and an STRN.", errors=errors)


class VendorService:
    def __init__(
        self,
        session: Session,
        clock: Clock,
        settings: Settings,
        passwords: Passwords,
        limiter: RateLimiter,
        outbox: Outbox,
    ) -> None:
        self._session = session
        self._clock = clock
        self._settings = settings
        self._passwords = passwords
        self._limiter = limiter
        self._outbox = outbox
        self._cipher = FieldCipher(settings.secret_key.get_secret_value())
        self._audit = AuditService(session, clock)

    def list_vendors(
        self,
        *,
        q: str | None,
        is_active: bool | None,
        registered: bool | None,
        filer: bool | None,
        sort: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Vendor], int]:
        return vendor_repository.list_vendors(
            self._session,
            q=q,
            is_active=is_active,
            registered=registered,
            filer=filer,
            sort=sort,
            limit=limit,
            offset=offset,
        )

    def get(self, vendor_id: int) -> Vendor:
        vendor = vendor_repository.get(self._session, vendor_id)
        if vendor is None:
            raise NotFoundError("There is no such vendor.")
        return vendor

    def create(self, actor: Principal, data: dict[str, Any]) -> Vendor:
        require_registration_details(bool(data.get("is_sales_tax_registered")), data.get("ntn"), data.get("strn"))
        account_number = data.pop("bank_account_number", None)
        vendor = Vendor(created_by=actor.id, **data)
        if account_number:
            self._store_account(vendor, normalise_account_number(account_number))
        vendor_repository.add(self._session, vendor)
        self._audit.record(
            actor_id=actor.id,
            action="vendor.created",
            entity_type="vendor",
            entity_id=vendor.id,
            after=self._snapshot(vendor),
        )
        self._session.commit()
        return vendor

    def update(self, actor: Principal, vendor_id: int, expected_version: int, changes: dict[str, Any]) -> Vendor:
        vendor = vendor_repository.get(self._session, vendor_id, for_update=True)
        if vendor is None:
            raise NotFoundError("There is no such vendor.")
        check_version(vendor, expected_version)
        before = self._snapshot(vendor)
        for name, value in changes.items():
            setattr(vendor, name, value)
        require_registration_details(vendor.is_sales_tax_registered, vendor.ntn, vendor.strn)
        vendor.updated_at = self._clock.now()
        self._session.flush()
        self._finish(actor, vendor, "vendor.updated", before)
        return vendor

    def set_active(self, actor: Principal, vendor_id: int, *, active: bool) -> Vendor:
        vendor = vendor_repository.get(self._session, vendor_id, for_update=True)
        if vendor is None:
            raise NotFoundError("There is no such vendor.")
        if vendor.is_active is active:
            return vendor
        before = self._snapshot(vendor)
        vendor.is_active = active
        vendor.updated_at = self._clock.now()
        self._session.flush()
        self._finish(actor, vendor, "vendor.activated" if active else "vendor.deactivated", before)
        return vendor

    def change_bank_account(
        self,
        actor: Principal,
        vendor_id: int,
        expected_version: int,
        *,
        account_number: str,
        bank_name: str | None,
        current_password: str,
    ) -> Vendor:
        """Needs the password again. Tells the vendor's creator and every active Admin. A change to the same number and
        bank is not a change: nothing is written and nobody is told."""
        reauthenticate(self._session, self._passwords, self._limiter, actor, current_password)
        vendor = vendor_repository.get(self._session, vendor_id, for_update=True)
        if vendor is None:
            raise NotFoundError("There is no such vendor.")
        check_version(vendor, expected_version)
        new_number = normalise_account_number(account_number)
        new_bank = bank_name if bank_name is not None else vendor.bank_name  # no bank given: keep the one on file
        if (
            vendor.bank_account_encrypted
            and self._cipher.decrypt(vendor.bank_account_encrypted) == new_number
            and vendor.bank_name == new_bank
        ):
            return vendor
        before = self._snapshot(vendor)
        self._store_account(vendor, new_number)
        vendor.bank_name = new_bank
        vendor.updated_at = self._clock.now()
        self._session.flush()
        self._notify_bank_change(actor, vendor)
        self._finish(actor, vendor, "vendor.bank_account_changed", before)
        return vendor

    # -----------------------------------------------------------------------------------------------------------------

    def _store_account(self, vendor: Vendor, account_number: str) -> None:
        vendor.bank_account_encrypted = self._cipher.encrypt(account_number)
        vendor.bank_account_last4 = account_number[-4:]

    def _snapshot(self, vendor: Vendor) -> JsonDict:
        return {**snapshot(vendor, FIELDS), "bank_account": vendor.bank_account_masked}

    def _finish(self, actor: Principal, vendor: Vendor, action: str, before: JsonDict) -> None:
        old, new = changed(before, self._snapshot(vendor))
        self._audit.record(
            actor_id=actor.id, action=action, entity_type="vendor", entity_id=vendor.id, before=old, after=new
        )
        self._session.commit()

    def _notify_bank_change(self, actor: Principal, vendor: Vendor) -> None:
        owner = user_repository.get(self._session, vendor.created_by)
        people = [*user_repository.active_by_role(self._session, Role.ADMIN)]
        if owner is not None and owner.is_active:
            people.append(owner)
        when = format_display_instant(self._clock.now(), ZoneInfo(self._settings.display_timezone))
        for email in sorted({person.email for person in people}):
            self._outbox.add(
                mail_templates.bank_account_changed(
                    to=email,
                    vendor=vendor.name,
                    changed_by=actor.full_name,
                    when=when,
                    masked_account=vendor.bank_account_masked or "",
                )
            )
