"""What the demonstration data contains, as plain tables. `docs/seed-data.md` is the specification.

Nothing here is a total or a count shown on a screen: those come from queries against the rows this creates.
Descriptions never name a month, because the dates are relative to the day the seed runs."""

from dataclasses import dataclass

DEMO_PASSWORD = "daftar-demo-2026"  # noqa: S105 - published on the demonstration login page on purpose

# (email, full name, role)
USERS = (
    ("admin@daftar.pk", "Nadia Qureshi", "admin"),
    ("accounts@daftar.pk", "Usman Tariq", "accountant"),
    ("approver@daftar.pk", "Ayesha Siddiqui", "approver"),
    ("staff@daftar.pk", "Bilal Ahmed", "staff"),
)

COST_CENTRES = (("HO", "Head Office"), ("OPS", "Operations"), ("SALES", "Sales"), ("IT", "IT"))
PROJECTS = (("PRJ-001", "Gulberg Fit-out"), ("PRJ-002", "NUST Campus Rollout"))


@dataclass(frozen=True)
class VendorSeed:
    key: str
    name: str
    registered: bool
    filer: bool
    ntn: str | None
    strn: str | None
    contact: str
    phone: str
    email: str
    address: str
    bank_name: str | None = None
    bank_account: str | None = None


VENDORS = (
    VendorSeed(
        "ravi",
        "Ravi Stationers",
        True,
        True,
        "1234567-8",
        "03-01-8700-123-45",
        "Imran Ravi",
        "0300-1234567",
        "sales@ravistationers.pk",
        "Shop 14, Bank Road, Rawalpindi",
        "Standard Chartered",
        "PK36SCBL0000001123456702",
    ),
    VendorSeed(
        "zarai",
        "Zarai Traders",
        True,
        False,
        "7654321-2",
        "03-01-8700-765-43",
        "Farhan Zarai",
        "0321-7654321",
        "accounts@zaraitraders.pk",
        "12 Mandi Road, Faisalabad",
    ),
    VendorSeed(
        "cables",
        "Karachi Cables (Pvt) Ltd",
        True,
        True,
        "2233445-6",
        "03-02-8700-223-34",
        "Sana Memon",
        "021-35871234",
        "orders@karachicables.pk",
        "Plot 21, SITE Area, Karachi",
        "Meezan Bank",
        "PK94MEZN0001234567890123",
    ),
    VendorSeed(
        "noor",
        "Haji Noor Transport",
        False,
        False,
        None,
        None,
        "Haji Noor Ahmed",
        "0333-5550142",
        "",
        "Transport Stand, Sargodha Road, Lahore",
    ),
    VendorSeed(
        "madina",
        "Al-Madina Printers",
        False,
        True,
        "9988776-1",
        None,
        "Zubair Madina",
        "0345-8881207",
        "",
        "Anarkali Bazaar, Lahore",
    ),
)


@dataclass(frozen=True)
class ExpenseSeed:
    description: str
    category: str
    amount: str
    status: str  # draft, submitted, approved, rejected, posted
    author: str  # "staff" or "accountant"
    method: str = "cash"
    tax: str = "0.00"
    centre: str | None = None  # direct: a cost centre code
    project: str | None = None  # direct: a project code
    split: tuple[tuple[str, int], ...] = ()  # indirect: (cost centre code, basis points)
    receipt: str | None = None  # which generated receipt to attach, by name
    voucher_draft: bool = False  # approved only: also generate its voucher, left in Draft
    comment: str = ""  # the reason, for a rejection


def direct(description: str, category: str, amount: str, status: str, author: str, **rest: object) -> ExpenseSeed:
    return ExpenseSeed(description, category, amount, status, author, **rest)  # type: ignore[arg-type]


def shared(
    description: str,
    category: str,
    amount: str,
    status: str,
    author: str,
    split: tuple[tuple[str, int], ...],
    **rest: object,
) -> ExpenseSeed:
    return ExpenseSeed(description, category, amount, status, author, split=split, **rest)  # type: ignore[arg-type]


EXPENSES = (
    # Direct, posted ------------------------------------------------------------------------------------------------
    direct("Courier charges for tender documents", "Office Supplies", "1850.00", "posted", "staff", centre="HO"),
    direct(
        "Fuel for the Gulberg site visit", "Travel", "6400.00", "posted", "staff", project="PRJ-001", receipt="fuel"
    ),
    direct(
        "Printer toner cartridges",
        "Office Supplies",
        "14160.00",
        "posted",
        "accountant",
        tax="2160.00",
        method="bank_transfer",
        centre="IT",
    ),
    direct(
        "Monthly rent, Karachi office", "Rent", "185000.00", "posted", "accountant", method="bank_transfer", centre="HO"
    ),
    direct(
        "Electricity bill, head office",
        "Utilities",
        "38940.00",
        "posted",
        "accountant",
        tax="5940.00",
        method="bank_transfer",
        centre="HO",
    ),
    direct("Staff lunch for the client visit", "Office Supplies", "7250.00", "posted", "staff", centre="SALES"),
    direct(
        "Taxi fares for the NUST site survey", "Travel", "3900.00", "posted", "staff", project="PRJ-002", receipt="taxi"
    ),
    direct(
        "Cable trays and clips",
        "Materials",
        "52500.00",
        "posted",
        "accountant",
        method="bank_transfer",
        project="PRJ-001",
    ),
    direct("Courier to the NUST campus", "Office Supplies", "980.00", "posted", "staff", project="PRJ-002"),
    # Direct, approved ----------------------------------------------------------------------------------------------
    direct(
        "Domain renewal and hosting",
        "Office Supplies",
        "11800.00",
        "approved",
        "staff",
        tax="1800.00",
        method="card",
        centre="IT",
    ),
    direct(
        "Monthly rent, second office",
        "Rent",
        "185000.00",
        "approved",
        "accountant",
        method="bank_transfer",
        centre="HO",
        voucher_draft=True,
    ),
    direct("Fuel for site visits", "Travel", "5100.00", "approved", "staff", project="PRJ-001"),
    direct(
        "Safety gloves and helmets",
        "Materials",
        "23600.00",
        "approved",
        "staff",
        tax="3600.00",
        method="card",
        project="PRJ-001",
    ),
    direct(
        "Broadband for the Lahore branch",
        "Utilities",
        "9440.00",
        "approved",
        "accountant",
        tax="1440.00",
        method="bank_transfer",
        centre="OPS",
    ),
    direct(
        "Dinner with the client delegation", "Travel", "8800.00", "approved", "staff", method="card", centre="SALES"
    ),
    direct(
        "Stationery restock",
        "Office Supplies",
        "4720.00",
        "approved",
        "staff",
        tax="720.00",
        centre="HO",
        voucher_draft=True,
    ),
    # Direct, rejected, submitted, draft ----------------------------------------------------------------------------
    direct(
        "Taxi claim for a weekend trip",
        "Travel",
        "1200.00",
        "rejected",
        "staff",
        centre="HO",
        comment="This was not a business trip. Please remove it.",
    ),
    direct(
        "Gift basket for a supplier",
        "Office Supplies",
        "6000.00",
        "rejected",
        "staff",
        method="card",
        centre="SALES",
        comment="There is no receipt attached. Add it and send it again.",
    ),
    direct(
        "Laptop bag",
        "Office Supplies",
        "7500.00",
        "rejected",
        "staff",
        centre="IT",
        comment="Please buy from the approved supplier list.",
    ),
    direct(
        "Generator service contract",
        "Utilities",
        "49750.00",
        "submitted",
        "accountant",
        method="bank_transfer",
        centre="OPS",
    ),
    direct("Team lunch", "Office Supplies", "5600.00", "draft", "staff", centre="OPS"),
    direct("Parking fees", "Travel", "700.00", "draft", "staff", centre="HO", receipt="parking"),
    direct("Meter reading deposit", "Utilities", "2500.00", "draft", "staff", centre="HO"),
    direct("Cable ties", "Materials", "1900.00", "draft", "staff", centre="IT", receipt="parking"),
    # Indirect, posted: two of them whole splits, the rest leave a remainder to share out -----------------------------
    shared(
        "Shared electricity bill",
        "Utilities",
        "10000.00",
        "posted",
        "accountant",
        (("HO", 3333), ("OPS", 3333), ("IT", 3334)),
        method="bank_transfer",
    ),
    shared(
        "Office cleaning contract",
        "Office Supplies",
        "7500.00",
        "posted",
        "accountant",
        (("HO", 3300), ("OPS", 3300), ("SALES", 3400)),
        method="bank_transfer",
    ),
    shared(
        "Water and sanitation charges",
        "Utilities",
        "1234.56",
        "posted",
        "accountant",
        (("HO", 3333), ("OPS", 3333), ("IT", 3334)),
    ),
    shared(
        "Shared broadband",
        "Utilities",
        "9999.99",
        "posted",
        "accountant",
        (("HO", 3333), ("OPS", 3333), ("SALES", 3334)),
        method="bank_transfer",
    ),
    shared(
        "Annual pest control",
        "Office Supplies",
        "2500.50",
        "posted",
        "accountant",
        (("HO", 3333), ("IT", 3333), ("SALES", 3334)),
    ),
    # Indirect, approved --------------------------------------------------------------------------------------------
    shared(
        "Building maintenance",
        "Office Supplies",
        "18000.00",
        "approved",
        "accountant",
        (("HO", 2500), ("OPS", 2500), ("SALES", 2500), ("IT", 2500)),
        method="bank_transfer",
    ),
    shared(
        "Common area insurance",
        "Rent",
        "42000.00",
        "approved",
        "accountant",
        (("HO", 5000), ("OPS", 5000)),
        method="bank_transfer",
    ),
    shared(
        "Tea and pantry supplies",
        "Office Supplies",
        "6725.25",
        "approved",
        "accountant",
        (("HO", 2500), ("OPS", 2500), ("SALES", 2500), ("IT", 2500)),
    ),
    shared("Courier account", "Office Supplies", "4333.33", "approved", "accountant", (("HO", 4000), ("SALES", 6000))),
    shared(
        "Security guards",
        "Salaries",
        "120000.00",
        "approved",
        "accountant",
        (("HO", 4000), ("OPS", 3000), ("SALES", 3000)),
        method="bank_transfer",
    ),
    # Indirect, rejected and draft ----------------------------------------------------------------------------------
    shared(
        "Team outing",
        "Travel",
        "30000.00",
        "rejected",
        "staff",
        (("HO", 2500), ("OPS", 2500), ("SALES", 2500), ("IT", 2500)),
        comment="This needs the director's approval before it is booked.",
    ),
    shared("Generator fuel", "Utilities", "15000.00", "draft", "accountant", (("HO", 5000), ("OPS", 5000))),
    shared(
        "Software subscriptions",
        "Office Supplies",
        "23600.00",
        "draft",
        "accountant",
        (("IT", 6000), ("HO", 4000)),
        tax="3600.00",
        method="card",
    ),
    shared(
        "Shared printing paper", "Office Supplies", "3450.75", "draft", "accountant", (("HO", 5000), ("SALES", 5000))
    ),
    shared(
        "Staff training",
        "Salaries",
        "45000.00",
        "draft",
        "accountant",
        (("OPS", 5000), ("SALES", 5000)),
        method="bank_transfer",
    ),
    shared("Janitorial supplies", "Office Supplies", "2200.00", "draft", "accountant", (("HO", 5000), ("OPS", 5000))),
)


@dataclass(frozen=True)
class PurchaseSeed:
    vendor: str
    status: str
    lines: tuple[tuple[str, str, str, str, int], ...]  # item, tax category, quantity, rate, sales tax in basis points
    invoice: str | None
    description: str
    category: str  # the expense category its voucher is generated with
    method: str = "bank_transfer"
    receipt: str | None = None
    comment: str = ""
    void: bool = False  # posted, then voided with a linked reversal
    days_after: int = 0  # for the second of a near-duplicate pair: how many days after the first


PURCHASES = (
    PurchaseSeed(
        "ravi",
        "posted",
        (("A4 paper, 500 sheets", "goods", "40", "1250.00", 1800), ("Toner cartridge", "goods", "6", "7800.00", 1800)),
        "RS-2041",
        "Paper and toner for the head office",
        "Office Supplies",
    ),
    PurchaseSeed(
        "ravi",
        "posted",
        (("Files and folders", "goods", "120", "85.00", 1800),),
        "RS-2057",
        "Filing supplies",
        "Office Supplies",
    ),
    PurchaseSeed(
        "ravi",
        "posted",
        (("Whiteboard markers", "goods", "50", "140.00", 1800),),
        "RS-2090",
        "Markers for the meeting rooms",
        "Office Supplies",
        method="cash",
    ),
    PurchaseSeed(
        "zarai",
        "posted",
        (("Pantry supplies", "goods", "1", "18500.00", 1800),),
        "ZT-771",
        "Pantry supplies for the quarter",
        "Office Supplies",
    ),
    PurchaseSeed(
        "cables",
        "posted",
        (
            ("Cat6 cable, 305 m box", "goods", "12", "14500.00", 1800),
            ("Pulling and termination", "contracts", "1", "65000.00", 1800),
        ),
        "KC-9013",
        "Cabling for the Gulberg fit-out",
        "Materials",
    ),
    PurchaseSeed(
        "cables",
        "posted",
        (("Fibre patch panels", "goods", "8", "9200.00", 1800),),
        "KC-9044",
        "Patch panels for the server room",
        "Materials",
        void=True,
    ),
    PurchaseSeed(
        "noor",
        "posted",
        (("Transport of site materials", "services", "1", "24000.00", 0),),
        None,
        "Hauling to the Gulberg site",
        "Materials",
        method="cash",
        receipt="memo",
    ),
    PurchaseSeed(
        "madina",
        "posted",
        (("Printing of tender documents", "services", "1", "16500.00", 0),),
        None,
        "Tender documents",
        "Office Supplies",
    ),
    PurchaseSeed(
        "noor",
        "approved",
        (("Local cartage", "services", "1", "8500.00", 0),),
        None,
        "Cartage for the move",
        "Materials",
        method="cash",
    ),
    PurchaseSeed(
        "madina",
        "approved",
        (("Business cards", "goods", "10", "1200.00", 0),),
        None,
        "Business cards for the sales team",
        "Office Supplies",
    ),
    PurchaseSeed(
        "ravi",
        "approved",
        (("Printer paper", "goods", "30", "1300.00", 1800),),
        "RS-2102",
        "Printer paper",
        "Office Supplies",
    ),
    PurchaseSeed(
        "zarai",
        "rejected",
        (("Cleaning supplies", "goods", "20", "650.00", 1800),),
        "ZT-780",
        "Cleaning supplies",
        "Office Supplies",
        comment="The invoice shows a different NTN. Ask the vendor for a corrected invoice.",
    ),
    PurchaseSeed(
        "cables",
        "submitted",
        (("24-port switch", "goods", "2", "41000.00", 1800),),
        "KC-9101",
        "Switches for the new floor",
        "Materials",
    ),
    PurchaseSeed(
        "ravi",
        "draft",
        (("Printer paper", "goods", "30", "1300.00", 1800),),
        "RS-2102",
        "Printer paper (entered again)",
        "Office Supplies",
        days_after=2,
    ),
    PurchaseSeed(
        "noor",
        "draft",
        (("Hired labour", "services", "1", "12000.00", 0),),
        None,
        "Labour for unloading",
        "Materials",
        method="cash",
    ),
)


@dataclass(frozen=True)
class ManualVoucherSeed:
    voucher_type: str  # PV, RV or JV
    description: str
    lines: tuple[tuple[str, str, str], ...]  # account code, "debit" or "credit", amount


MANUAL_VOUCHERS = (
    ManualVoucherSeed(
        "RV", "Consulting fee received from NUST", (("1200", "debit", "450000.00"), ("4100", "credit", "450000.00"))
    ),
    ManualVoucherSeed(
        "JV", "Accrual of rent not yet invoiced", (("5100", "debit", "92500.00"), ("2100", "credit", "92500.00"))
    ),
    ManualVoucherSeed(
        "JV", "Capital introduced by the owner", (("1200", "debit", "1000000.00"), ("3100", "credit", "1000000.00"))
    ),
)

VOID_REASON = "Entered twice; the supplier was paid from the first voucher."

# Receipts to generate: name -> (shop, number, amount shown, lines)
RECEIPTS = {
    "fuel": ("Shell Gulberg Service Station", "0042-7716", "6,400.00", ("Super petrol 28.4 L", "Pump 3")),
    "taxi": ("City Cabs Rawalpindi", "C-2291", "3,900.00", ("Three journeys", "Cash fare")),
    "parking": ("Packages Mall Parking", "P-80345", "700.00", ("Day parking", "Cash")),
    "memo": ("Haji Noor Transport", "M-117", "24,000.00", ("Hauling, 2 trips", "Cash on delivery")),
}
