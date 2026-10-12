"""Withholding rates as dated configuration (docs/domain-rules.md section 5). The rate and the rule id found for a
document date are copied onto the purchase line, so editing a rule never changes a saved document.

Sales tax withholding depends on the supplier's registration, income tax withholding on the supplier's filer status. The
flag a rule does not depend on is stored as false, so the database's exclusion constraint can compare every rule."""

from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.enums import TaxCategory, TaxType
from app.core.errors import FieldError, NotFoundError, ValidationFailedError
from app.core.principal import Principal
from app.models.base import JsonDict
from app.models.tax import TaxRule
from app.repositories import tax_rules as rule_repository
from app.services.audit import AuditService
from app.services.master import changed, check_version, snapshot

FIELDS = (
    "tax_type",
    "supplier_registered",
    "supplier_filer",
    "category",
    "rate_bp",
    "effective_from",
    "effective_to",
    "source",
)


def relevant_flags(tax_type: TaxType, registered: bool, filer: bool) -> tuple[bool, bool]:
    """The (registered, filer) pair as stored and as looked up: only the flag the tax depends on is kept."""
    if tax_type is TaxType.SALES_TAX_WITHHOLDING:
        return registered, False
    return False, filer


class TaxRuleService:
    def __init__(self, session: Session, clock: Clock) -> None:
        self._session = session
        self._clock = clock
        self._audit = AuditService(session, clock)

    def list_rules(
        self,
        *,
        tax_type: TaxType | None,
        category: TaxCategory | None,
        active_on: date | None,
        sort: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[TaxRule], int]:
        return rule_repository.list_rules(
            self._session,
            tax_type=tax_type,
            category=category,
            active_on=active_on,
            sort=sort,
            limit=limit,
            offset=offset,
        )

    def get(self, rule_id: int) -> TaxRule:
        rule = rule_repository.get(self._session, rule_id)
        if rule is None:
            raise NotFoundError("There is no such tax rule.")
        return rule

    def resolve(
        self,
        *,
        tax_type: TaxType,
        supplier_registered: bool,
        supplier_filer: bool,
        category: TaxCategory,
        on: date,
    ) -> TaxRule:
        """The rule in force on a date. A rule for the exact category beats one for `any`."""
        registered, filer = relevant_flags(tax_type, supplier_registered, supplier_filer)
        rule = rule_repository.find(
            self._session,
            tax_type=tax_type,
            supplier_registered=registered,
            supplier_filer=filer,
            category=category,
            on=on,
        )
        if rule is None:
            raise NotFoundError("No tax rule applies to that supplier, payment and date.")
        return rule

    def create(self, actor: Principal, data: dict[str, Any]) -> TaxRule:
        registered, filer = relevant_flags(
            data["tax_type"], bool(data.pop("supplier_registered")), bool(data.pop("supplier_filer"))
        )
        rule = TaxRule(supplier_registered=registered, supplier_filer=filer, created_by=actor.id, **data)
        # Overlap with another rule is refused by the database (`no_overlapping_rules`) when this is flushed.
        rule_repository.add(self._session, rule)
        self._audit.record(
            actor_id=actor.id,
            action="tax_rule.created",
            entity_type="tax_rule",
            entity_id=rule.id,
            after=snapshot(rule, FIELDS),
        )
        self._session.commit()
        return rule

    def update(self, actor: Principal, rule_id: int, expected_version: int, changes: dict[str, Any]) -> TaxRule:
        """Rate, end date and source can change; which supplier and payment the rule is for cannot. Saved documents keep
        the rate they were given."""
        rule = rule_repository.get(self._session, rule_id, for_update=True)
        if rule is None:
            raise NotFoundError("There is no such tax rule.")
        check_version(rule, expected_version)
        if (
            "effective_to" in changes
            and changes["effective_to"] is not None
            and changes["effective_to"] < rule.effective_from
        ):
            raise ValidationFailedError(
                "A rule cannot end before it starts.",
                errors=[FieldError("effective_to", "Choose a date on or after the start.", "before_start")],
            )
        before = snapshot(rule, FIELDS)
        for name, value in changes.items():
            setattr(rule, name, value)
        rule.updated_at = self._clock.now()
        self._session.flush()
        old, new = changed(before, snapshot(rule, FIELDS))
        self._finish_audit(actor, rule, old, new)
        return rule

    def _finish_audit(self, actor: Principal, rule: TaxRule, old: JsonDict, new: JsonDict) -> None:
        self._audit.record(
            actor_id=actor.id,
            action="tax_rule.updated",
            entity_type="tax_rule",
            entity_id=rule.id,
            before=old,
            after=new,
        )
        self._session.commit()
