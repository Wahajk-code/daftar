"""Who may see a document that is still a draft.

A draft is its author's work in hand. An approver decides on documents that have been sent, so a draft is not available
to an approver, in any list, report, count, search or by its address, until its author submits it. Admins and
accountants keep their view of drafts (an Admin oversees, an Accountant writes purchases and vouchers). Staff are
limited to their own expenses elsewhere."""

from app.core.enums import Role
from app.core.principal import Principal


def drafts_hidden_from(actor: Principal) -> bool:
    return actor.role is Role.APPROVER
