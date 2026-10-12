from enum import StrEnum


class Role(StrEnum):
    ADMIN = "admin"
    ACCOUNTANT = "accountant"
    APPROVER = "approver"
    STAFF = "staff"


class DocumentStatus(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"
    POSTED = "posted"
    VOID = "void"


class DocumentType(StrEnum):
    """The three document types that share one status machine."""

    EXPENSE = "expense"
    PURCHASE = "purchase"
    VOUCHER = "voucher"
