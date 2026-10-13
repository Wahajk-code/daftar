# Process flow

How a document moves, and the sequences behind the important actions.

## Status flow

One transition table (`core/transitions.py`) drives expenses, purchases and vouchers. Each row names the roles allowed and the
guards. Nobody approves a document they wrote.

```mermaid
stateDiagram-v2
    [*] --> Draft
    Draft --> Submitted: author sends
    Submitted --> Approved: approver or admin
    Submitted --> Rejected: comment required
    Rejected --> Draft: author reopens
    Approved --> Posted: voucher posted
    Posted --> Void: vouchers only, reason required
```

| Situation | Status | Code |
|---|---|---|
| Pair not in the table | 409 | `INVALID_TRANSITION` |
| Role not allowed, or approving your own document | 403 | `FORBIDDEN`, `SELF_APPROVAL_FORBIDDEN` |
| A guard failed (incomplete, unbalanced, comment missing) | 422 | the guard's name |
| Accounting period closed | 409 | `PERIOD_CLOSED` |
| Stale `version` | 409 | `VERSION_CONFLICT` |
| Someone else's record, seen by Staff; a draft, seen by an Approver | 404 | `NOT_FOUND` |

## From receipt to ledger

```mermaid
flowchart LR
    S[Staff writes an expense<br/>with a receipt photo] --> SU[Sends for approval]
    SU --> AP[Approver reads it<br/>and the receipt]
    AP -->|approves| G[Accountant generates<br/>the payment voucher]
    AP -->|rejects with a comment| S
    G --> RV[Voucher checked<br/>and sent]
    RV --> AV[Approver approves it]
    AV --> PO[Accountant posts it<br/>numbered PV-2026-0001]
    PO -->|if wrong| VD[Void: a reversing voucher<br/>is posted, nothing is deleted]
```

A purchase follows the same path: the accountant enters the vendor invoice, the server prices every line and computes the
taxes, and the paying voucher is generated from it once approved.

## Signing in (BFF)

```mermaid
sequenceDiagram
    participant B as Browser
    participant N as Next.js
    participant A as FastAPI
    B->>N: POST /api/auth/login
    N->>A: POST /auth/login
    A-->>N: access and refresh tokens
    N-->>B: HttpOnly, SameSite=Strict cookies
    B->>N: GET /api/expenses (cookie)
    N->>A: GET /expenses with Authorization
    A-->>N: JSON
    N-->>B: JSON
    Note over N,A: On a 401 the handler refreshes once and retries
```

## Posting a voucher

```mermaid
sequenceDiagram
    participant C as Client
    participant S as VoucherService
    participant DB as PostgreSQL
    C->>S: post(id, Idempotency-Key)
    S->>DB: BEGIN
    S->>DB: replay? find voucher by post_key
    S->>DB: period open? transition allowed?
    S->>DB: UPDATE number_counters ... RETURNING last_seq
    S->>DB: set status, number, post_key
    S->>DB: post the source expense or purchase
    S->>DB: history row and audit row
    DB-->>S: COMMIT (the balance trigger runs here)
    S-->>C: the voucher, or the original answer on a replay
```

The counter row is locked until commit, so posts of one type and year run one at a time, and a failed post leaves no gap.

## Void

A void needs a reason and an open period. In one transaction it posts a reversing voucher (every debit and credit swapped,
numbered from the same counter), marks the original void, and leaves the source document posted. A voucher can have only one
reversal, and a reversal cannot be voided. The correction is a new document.

## Receipt upload

The browser sends the file to the web app, which forwards it to the API. The API checks the file signature and size, re-encodes
the image (removing EXIF and location data), records its SHA-256, and stores it in Cloudinary as an authenticated asset. A
receipt is read only through the API, after an ownership check. A phone's photo is turned upright and shrunk in the browser
before it is sent.

## Email

Services add messages to an outbox; the router sends them in the background after the commit, so a slow or failing mail server
never fails a request. A failure is logged (`email failed`) and not shown. Emails: invitation, password reset (by the user or
an admin), bank account changed, needs approval, approved, rejected.

## Invitation

An admin invites an address with a role. The API stores only a hash of a one-time token, valid for 7 days, and emails a link
`<WEB_BASE_URL>/accept-invite?token=...`. Opening it asks for a name and password and creates the account. Sending again cancels
the earlier link.
