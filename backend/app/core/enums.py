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


class AuthPurpose(StrEnum):
    INVITE = "invite"
    PASSWORD_RESET = "password_reset"


class AccountType(StrEnum):
    ASSET = "asset"
    LIABILITY = "liability"
    INCOME = "income"
    EXPENSE = "expense"
    EQUITY = "equity"


class ProjectKind(StrEnum):
    PROJECT = "project"
    PRODUCT = "product"


class TaxType(StrEnum):
    SALES_TAX_WITHHOLDING = "sales_tax_withholding"
    INCOME_TAX_WITHHOLDING = "income_tax_withholding"


class TaxCategory(StrEnum):
    GOODS = "goods"
    SERVICES = "services"
    CONTRACTS = "contracts"
    ANY = "any"


class PostingKey(StrEnum):
    """The accounts a generated voucher posts to. Editable by an Admin; see decision 34."""

    CASH = "cash"
    BANK = "bank"
    INPUT_SALES_TAX = "input_sales_tax"
    SALES_TAX_WITHHELD = "sales_tax_withheld"
    INCOME_TAX_WITHHELD = "income_tax_withheld"


class ExpenseType(StrEnum):
    DIRECT = "direct"
    INDIRECT = "indirect"


class AllocationMethod(StrEnum):
    PERCENTAGE = "percentage"
    FIXED = "fixed"


class PaymentMethod(StrEnum):
    CASH = "cash"
    BANK_TRANSFER = "bank_transfer"
    CARD = "card"
    CHEQUE = "cheque"


class PurchaseKind(StrEnum):
    TAX_INVOICE = "tax_invoice"
    PURCHASE_MEMO = "purchase_memo"


class VoucherType(StrEnum):
    PAYMENT = "PV"
    RECEIPT = "RV"
    JOURNAL = "JV"


class YearMode(StrEnum):
    """Which year a voucher number carries: the calendar year, or the fiscal year (July to June) named by its end."""

    CALENDAR = "calendar"
    FISCAL = "fiscal"
