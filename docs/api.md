# API

Generated from `backend/openapi.json` by `python -m app.openapi_export api-list`. Do not edit by hand.
Every path is under `/api/v1` except the probes. Errors share one shape (`docs/architecture.md`, section 8).

## accounts

| Method | Path | Operation | Who | What it does |
|---|---|---|---|---|
| GET | `/api/v1/accounts` | `list_accounts` | accountant, admin, approver | List Accounts |
| POST | `/api/v1/accounts` | `create_account` | accountant, admin | Create Account |
| GET | `/api/v1/accounts/{account_id}` | `get_account` | accountant, admin, approver | Get Account |
| PATCH | `/api/v1/accounts/{account_id}` | `update_account` | accountant, admin | Update Account |
| POST | `/api/v1/accounts/{account_id}/activate` | `activate_account` | accountant, admin | Activate Account |
| POST | `/api/v1/accounts/{account_id}/deactivate` | `deactivate_account` | accountant, admin | Deactivate Account |

## attachments

| Method | Path | Operation | Who | What it does |
|---|---|---|---|---|
| GET | `/api/v1/attachments/{attachment_id}/content` | `get_attachment_content` | accountant, admin, approver, staff | The image itself, only for someone who may see the document it belongs to. It has no public address. |
| POST | `/api/v1/attachments/{attachment_id}/remove` | `remove_attachment` | accountant, admin, staff | Take an attachment off a draft. The record stays; the stored file is deleted. |

## audit

| Method | Path | Operation | Who | What it does |
|---|---|---|---|---|
| GET | `/api/v1/audit` | `list_audit_events` | admin | Newest first. Each entry says who did what to which record and, where it applies, the values before and after. |

## auth

| Method | Path | Operation | Who | What it does |
|---|---|---|---|---|
| POST | `/api/v1/auth/forgot-password` | `forgot_password` | anyone | Always the same reply, whether or not the email has an account. |
| POST | `/api/v1/auth/invites/accept` | `accept_invite` | anyone | Accept Invite |
| POST | `/api/v1/auth/invites/inspect` | `inspect_invite` | anyone | What the accept-invitation screen shows. A used, expired or cancelled link says which. |
| POST | `/api/v1/auth/login` | `login` | anyone | Login |
| POST | `/api/v1/auth/logout` | `logout` | anyone | Logout |
| POST | `/api/v1/auth/refresh` | `refresh_session` | anyone | Exchange a refresh token for a new pair. The old token stops working; presenting it again ends every session. |
| POST | `/api/v1/auth/reset-password` | `reset_password` | anyone | Reset Password |

## categories

| Method | Path | Operation | Who | What it does |
|---|---|---|---|---|
| GET | `/api/v1/categories` | `list_categories` | accountant, admin, approver, staff | List Categories |
| POST | `/api/v1/categories` | `create_category` | accountant, admin | Create Category |
| GET | `/api/v1/categories/{category_id}` | `get_category` | accountant, admin, approver, staff | Get Category |
| PATCH | `/api/v1/categories/{category_id}` | `update_category` | accountant, admin | Update Category |
| POST | `/api/v1/categories/{category_id}/activate` | `activate_category` | accountant, admin | Activate Category |
| POST | `/api/v1/categories/{category_id}/deactivate` | `deactivate_category` | accountant, admin | Deactivate Category |

## cost centres

| Method | Path | Operation | Who | What it does |
|---|---|---|---|---|
| GET | `/api/v1/cost-centers` | `list_cost_centers` | accountant, admin, approver, staff | List Cost Centers |
| POST | `/api/v1/cost-centers` | `create_cost_center` | accountant, admin | Create Cost Center |
| GET | `/api/v1/cost-centers/{cost_center_id}` | `get_cost_center` | accountant, admin, approver, staff | Get Cost Center |
| PATCH | `/api/v1/cost-centers/{cost_center_id}` | `update_cost_center` | accountant, admin | Update Cost Center |
| POST | `/api/v1/cost-centers/{cost_center_id}/activate` | `activate_cost_center` | accountant, admin | Activate Cost Center |
| POST | `/api/v1/cost-centers/{cost_center_id}/deactivate` | `deactivate_cost_center` | accountant, admin | Deactivate Cost Center |

## expenses

| Method | Path | Operation | Who | What it does |
|---|---|---|---|---|
| GET | `/api/v1/expenses` | `list_expenses` | accountant, admin, approver, staff | List Expenses |
| POST | `/api/v1/expenses` | `create_expense` | accountant, admin, staff | Create Expense |
| POST | `/api/v1/expenses/preview-allocation` | `preview_expense_allocation` | accountant, admin, staff | What a split comes to as typed. A split that does not add up reports how far short it is instead of failing. |
| GET | `/api/v1/expenses/{expense_id}` | `get_expense` | accountant, admin, approver, staff | Get Expense |
| PATCH | `/api/v1/expenses/{expense_id}` | `update_expense` | accountant, admin, staff | Update Expense |
| POST | `/api/v1/expenses/{expense_id}/approve` | `approve_expense` | admin, approver | Approve Expense |
| GET | `/api/v1/expenses/{expense_id}/attachments` | `list_expense_attachments` | accountant, admin, approver, staff | List Expense Attachments |
| POST | `/api/v1/expenses/{expense_id}/attachments` | `upload_expense_attachment` | accountant, admin, staff | Upload Expense Attachment |
| GET | `/api/v1/expenses/{expense_id}/duplicates` | `get_expense_duplicates` | accountant, admin, approver, staff | Documents this one resembles. A warning only: saving and approving are never blocked. |
| POST | `/api/v1/expenses/{expense_id}/generate-voucher` | `generate_voucher_from_expense` | accountant, admin | A Payment voucher in Draft: cash for a cash expense, the bank otherwise, tax on its own line. Once only. |
| GET | `/api/v1/expenses/{expense_id}/history` | `get_expense_history` | accountant, admin, approver, staff | Get Expense History |
| POST | `/api/v1/expenses/{expense_id}/reject` | `reject_expense` | admin, approver | A comment is required: the author sees it in the history. |
| POST | `/api/v1/expenses/{expense_id}/reopen` | `reopen_expense` | accountant, admin, staff | Return a rejected expense to Draft. Only its author can. |
| POST | `/api/v1/expenses/{expense_id}/submit` | `submit_expense` | accountant, admin, staff | Submit Expense |

## health

| Method | Path | Operation | Who | What it does |
|---|---|---|---|---|
| GET | `/health` | `get_health` |  | Liveness: the process is up. Touches nothing else. |
| GET | `/ready` | `get_ready` |  | Readiness: the database answers. |
| GET | `/version` | `get_version` |  | Get Version |

## invites

| Method | Path | Operation | Who | What it does |
|---|---|---|---|---|
| GET | `/api/v1/invites` | `list_invites` | admin | List Invites |
| POST | `/api/v1/invites` | `create_invite` | admin | Create Invite |
| POST | `/api/v1/invites/{invite_id}/resend` | `resend_invite` | admin | Resend Invite |
| POST | `/api/v1/invites/{invite_id}/revoke` | `revoke_invite` | admin | Revoke Invite |

## me

| Method | Path | Operation | Who | What it does |
|---|---|---|---|---|
| GET | `/api/v1/me` | `get_me` | accountant, admin, approver, staff | Who is signed in, and the zone both clients format times in. |
| POST | `/api/v1/me/password` | `change_my_password` | accountant, admin, approver, staff | Change your own password. It signs you out of every device, this one included. |
| POST | `/api/v1/me/tour/complete` | `complete_my_tour` | accountant, admin, approver, staff | Mark the onboarding tour finished or skipped. It is remembered on every device; repeating it is harmless. |
| POST | `/api/v1/me/tour/restart` | `restart_my_tour` | accountant, admin, approver, staff | Show the onboarding tour again the next time the app opens. |

## periods

| Method | Path | Operation | Who | What it does |
|---|---|---|---|---|
| GET | `/api/v1/periods` | `list_periods` | accountant, admin, approver | List Periods |
| POST | `/api/v1/periods/close` | `close_period` | admin | Close an inclusive range of dates. Nothing can be posted dated inside it until it is reopened. |
| POST | `/api/v1/periods/{period_id}/reopen` | `reopen_period` | admin | Reopen Period |

## posting accounts

| Method | Path | Operation | Who | What it does |
|---|---|---|---|---|
| GET | `/api/v1/posting-accounts` | `list_posting_accounts` | accountant, admin, approver | List Posting Accounts |
| PUT | `/api/v1/posting-accounts/{key}` | `set_posting_account` | accountant, admin | Set Posting Account |

## projects

| Method | Path | Operation | Who | What it does |
|---|---|---|---|---|
| GET | `/api/v1/projects` | `list_projects` | accountant, admin, approver, staff | List Projects |
| POST | `/api/v1/projects` | `create_project` | accountant, admin | Create Project |
| GET | `/api/v1/projects/{project_id}` | `get_project` | accountant, admin, approver, staff | Get Project |
| PATCH | `/api/v1/projects/{project_id}` | `update_project` | accountant, admin | Update Project |
| POST | `/api/v1/projects/{project_id}/activate` | `activate_project` | accountant, admin | Activate Project |
| POST | `/api/v1/projects/{project_id}/deactivate` | `deactivate_project` | accountant, admin | Deactivate Project |

## purchases

| Method | Path | Operation | Who | What it does |
|---|---|---|---|---|
| GET | `/api/v1/purchases` | `list_purchases` | accountant, admin, approver | List Purchases |
| POST | `/api/v1/purchases` | `create_purchase` | accountant, admin | Create Purchase |
| POST | `/api/v1/purchases/preview` | `preview_purchase` | accountant, admin | Price the lines as they would be saved, with nothing stored. The client's figures are never trusted. |
| GET | `/api/v1/purchases/{purchase_id}` | `get_purchase` | accountant, admin, approver | Get Purchase |
| PATCH | `/api/v1/purchases/{purchase_id}` | `update_purchase` | accountant, admin | Update Purchase |
| POST | `/api/v1/purchases/{purchase_id}/approve` | `approve_purchase` | admin, approver | Approve Purchase |
| GET | `/api/v1/purchases/{purchase_id}/attachments` | `list_purchase_attachments` | accountant, admin, approver | List Purchase Attachments |
| POST | `/api/v1/purchases/{purchase_id}/attachments` | `upload_purchase_attachment` | accountant, admin | Upload Purchase Attachment |
| GET | `/api/v1/purchases/{purchase_id}/duplicates` | `get_purchase_duplicates` | accountant, admin, approver | Documents this one resembles. A warning only: saving and approving are never blocked. |
| POST | `/api/v1/purchases/{purchase_id}/generate-voucher` | `generate_voucher_from_purchase` | accountant, admin | A Payment voucher in Draft: the purchase and its sales tax debited, the vendor paid and each withholding credited |
| GET | `/api/v1/purchases/{purchase_id}/history` | `get_purchase_history` | accountant, admin, approver | Get Purchase History |
| POST | `/api/v1/purchases/{purchase_id}/reject` | `reject_purchase` | admin, approver | Reject Purchase |
| POST | `/api/v1/purchases/{purchase_id}/reopen` | `reopen_purchase` | accountant, admin | Reopen Purchase |
| POST | `/api/v1/purchases/{purchase_id}/submit` | `submit_purchase` | accountant, admin | Submit Purchase |

## reports

| Method | Path | Operation | Who | What it does |
|---|---|---|---|---|
| GET | `/api/v1/reports/activity` | `report_activity` | accountant, admin, approver | What each person did in the period: documents made, sent for approval, sent back, decided, posted and voided. |
| GET | `/api/v1/reports/activity/csv` | `export_report_activity` | accountant, admin, approver | Export Activity |
| GET | `/api/v1/reports/expenses` | `report_expenses` | accountant, admin, approver | Expenses by type and cost centre. |
| GET | `/api/v1/reports/expenses/csv` | `export_report_expenses` | accountant, admin, approver | The same report as a CSV file. Limited per user and recorded in the audit log. |
| GET | `/api/v1/reports/export/expenses` | `export_expense_list` | accountant, admin, approver | Every expense the list filters match, as a CSV file. Limited per user and recorded in the audit log. |
| GET | `/api/v1/reports/export/purchases` | `export_purchase_list` | accountant, admin, approver | Every purchase the list filters match, as a CSV file. Limited per user and recorded in the audit log. |
| GET | `/api/v1/reports/overview` | `report_overview` | accountant, admin, approver | Month by month spend and the spread of documents over statuses: the figures behind the home screen's charts. |
| GET | `/api/v1/reports/purchases` | `report_purchases` | accountant, admin, approver | Purchases by vendor, split into registered and unregistered vendors. |
| GET | `/api/v1/reports/purchases/csv` | `export_report_purchases` | accountant, admin, approver | Export Purchases |
| GET | `/api/v1/reports/vouchers` | `report_voucher_register` | accountant, admin, approver | The voucher register in number order, one page at a time. |
| GET | `/api/v1/reports/vouchers/csv` | `export_report_voucher_register` | accountant, admin, approver | Export Voucher Register |

## settings

| Method | Path | Operation | Who | What it does |
|---|---|---|---|---|
| GET | `/api/v1/settings/accounting` | `get_accounting_settings` | accountant, admin, approver | Get Accounting Settings |
| PUT | `/api/v1/settings/accounting` | `set_accounting_settings` | accountant, admin | Choose the month the voucher numbering year starts in. It applies to vouchers posted from now on; numbers already |

## tax rules

| Method | Path | Operation | Who | What it does |
|---|---|---|---|---|
| GET | `/api/v1/tax-rules` | `list_tax_rules` | accountant, admin, approver | List Tax Rules |
| POST | `/api/v1/tax-rules` | `create_tax_rule` | accountant, admin | Create Tax Rule |
| GET | `/api/v1/tax-rules/resolve` | `resolve_tax_rule` | accountant, admin | The rule in force on a date for a kind of supplier and payment. A specific category beats `any`. |
| GET | `/api/v1/tax-rules/{rule_id}` | `get_tax_rule` | accountant, admin, approver | Get Tax Rule |
| PATCH | `/api/v1/tax-rules/{rule_id}` | `update_tax_rule` | accountant, admin | Update Tax Rule |

## users

| Method | Path | Operation | Who | What it does |
|---|---|---|---|---|
| GET | `/api/v1/users` | `list_users` | admin | List Users |
| GET | `/api/v1/users/{user_id}` | `get_user` | admin | Get User |
| POST | `/api/v1/users/{user_id}/deactivate` | `deactivate_user` | admin | Deactivate User |
| POST | `/api/v1/users/{user_id}/reactivate` | `reactivate_user` | admin | Reactivate User |
| POST | `/api/v1/users/{user_id}/reset-password` | `trigger_password_reset` | admin | Email the user a reset link. The Admin never sees or sets the password. |
| POST | `/api/v1/users/{user_id}/role` | `change_user_role` | admin | Change User Role |

## vendors

| Method | Path | Operation | Who | What it does |
|---|---|---|---|---|
| GET | `/api/v1/vendors` | `list_vendors` | accountant, admin, approver | List Vendors |
| POST | `/api/v1/vendors` | `create_vendor` | accountant, admin | Create Vendor |
| GET | `/api/v1/vendors/{vendor_id}` | `get_vendor` | accountant, admin, approver | Get Vendor |
| PATCH | `/api/v1/vendors/{vendor_id}` | `update_vendor` | accountant, admin | Update Vendor |
| POST | `/api/v1/vendors/{vendor_id}/activate` | `activate_vendor` | accountant, admin | Activate Vendor |
| POST | `/api/v1/vendors/{vendor_id}/bank-account` | `change_vendor_bank_account` | accountant, admin | Needs your password again. The vendor's creator and every Admin are emailed. The number is never returned. |
| POST | `/api/v1/vendors/{vendor_id}/deactivate` | `deactivate_vendor` | accountant, admin | Deactivate Vendor |

## vouchers

| Method | Path | Operation | Who | What it does |
|---|---|---|---|---|
| GET | `/api/v1/vouchers` | `list_vouchers` | accountant, admin, approver | List Vouchers |
| POST | `/api/v1/vouchers` | `create_voucher` | accountant, admin | Create Voucher |
| POST | `/api/v1/vouchers/check-balance` | `check_voucher_balance` | accountant, admin | Where lines stand and the one line that would balance them. Saves nothing: a draft cannot be saved unbalanced. |
| GET | `/api/v1/vouchers/{voucher_id}` | `get_voucher` | accountant, admin, approver | Get Voucher |
| PATCH | `/api/v1/vouchers/{voucher_id}` | `update_voucher` | accountant, admin | Update Voucher |
| POST | `/api/v1/vouchers/{voucher_id}/approve` | `approve_voucher` | admin, approver | Approve Voucher |
| GET | `/api/v1/vouchers/{voucher_id}/history` | `get_voucher_history` | accountant, admin, approver | Get Voucher History |
| POST | `/api/v1/vouchers/{voucher_id}/post` | `post_voucher` | accountant, admin | Number the voucher and post it, and post the expense or purchase it came from. Sending the same |
| POST | `/api/v1/vouchers/{voucher_id}/reject` | `reject_voucher` | admin, approver | Reject Voucher |
| POST | `/api/v1/vouchers/{voucher_id}/reopen` | `reopen_voucher` | accountant, admin | Reopen Voucher |
| POST | `/api/v1/vouchers/{voucher_id}/submit` | `submit_voucher` | accountant, admin | Refused with the reason when the voucher is not balanced, has fewer than two lines or has no narration. |
| POST | `/api/v1/vouchers/{voucher_id}/void` | `void_voucher` | accountant, admin | Cancel a posted voucher with a reason. Creates the linked reversing voucher in the same transaction. |
