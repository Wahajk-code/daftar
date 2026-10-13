"""The wording of each email, one function per template: a plain-text body (the fallback) and a styled HTML
version made by app.core.mail_layout from the same words."""

from app.core.mail import EmailMessage
from app.core.mail_layout import render


def invite(*, to: str, role: str, link: str, expires: str, invited_by: str) -> EmailMessage:
    return EmailMessage(
        kind="invite",
        to=to,
        subject="You have been invited to Daftar",
        body=(
            f"{invited_by} has invited you to Daftar as {role}.\n\n"
            f"Set your name and password here:\n{link}\n\n"
            f"The link works once and expires on {expires}.\n"
            "If you were not expecting this, ignore this email."
        ),
        html=render(
            preheader=f"{invited_by} invited you to Daftar as {role}.",
            heading="You are invited to Daftar",
            paragraphs=[
                f"{invited_by} has invited you to Daftar as {role}. Set your name and password to get started."
            ],
            facts=[("Role", role), ("Invited by", invited_by), ("Link expires", expires)],
            button=("Set up your account", link),
            after=["The link works once. If you were not expecting this, you can ignore this email."],
        ),
    )


def password_reset(*, to: str, link: str, expires: str, started_by_admin: bool) -> EmailMessage:
    reason = (
        "An administrator started a password reset for your account."
        if started_by_admin
        else ("We received a request to reset your password.")
    )
    return EmailMessage(
        kind="password_reset",
        to=to,
        subject="Reset your Daftar password",
        body=(
            f"{reason}\n\n"
            f"Choose a new password here:\n{link}\n\n"
            f"The link works once and expires on {expires}. Using it signs you out everywhere.\n"
            "If you did not ask for this, ignore this email; your password has not changed."
        ),
        html=render(
            preheader="Choose a new password for your Daftar account.",
            heading="Reset your password",
            paragraphs=[reason, "Using the link signs you out everywhere."],
            facts=[("Link expires", expires)],
            button=("Choose a new password", link),
            after=["If you did not ask for this, ignore this email; your password has not changed."],
        ),
    )


def bank_account_changed(*, to: str, vendor: str, changed_by: str, when: str, masked_account: str) -> EmailMessage:
    return EmailMessage(
        kind="bank_account_changed",
        to=to,
        subject=f"Bank details changed for {vendor}",
        body=(
            f"{changed_by} changed the bank details of the vendor {vendor} on {when}.\n"
            f"The account now ends in {masked_account}.\n\n"
            "If you did not expect this change, tell an administrator at once: changed bank details are a common "
            "way to redirect a payment."
        ),
        html=render(
            preheader=f"Bank details changed for {vendor}.",
            heading="Bank details were changed",
            chip=("Check this", "caution"),
            paragraphs=[f"{changed_by} changed the bank details of the vendor {vendor}."],
            facts=[
                ("Vendor", vendor),
                ("Changed by", changed_by),
                ("When", when),
                ("Account now ends in", masked_account),
            ],
            after=[
                "If you did not expect this change, tell an administrator at once: changed bank details are "
                "a common way to redirect a payment."
            ],
        ),
    )


def needs_approval(*, to: str, name: str, label: str, summary: str, submitted_by: str, link: str) -> EmailMessage:
    return EmailMessage(
        kind="needs_approval",
        to=to,
        subject=f"Needs your approval: {label}",
        body=(
            f"Hello {name},\n\n{submitted_by} submitted {label} for approval.\n{summary}\n\nReview it here:\n{link}\n"
        ),
        html=render(
            preheader=f"{submitted_by} submitted {label} for approval.",
            heading="Needs your approval",
            chip=("Submitted", "caution"),
            paragraphs=[f"Hello {name}, {submitted_by} submitted {label} for approval."],
            facts=[("Document", label), ("Submitted by", submitted_by), ("Details", summary)],
            button=("Review it", link),
        ),
    )


def decided(
    *,
    to: str,
    name: str,
    label: str,
    summary: str,
    outcome: str,
    decided_by: str,
    when: str,
    comment: str | None,
    link: str,
) -> EmailMessage:
    note = f"\nTheir comment: {comment}\n" if comment else ""
    return EmailMessage(
        kind="decided",
        to=to,
        subject=f"{label} was {outcome}",
        body=(
            f"Hello {name},\n\n{decided_by} {outcome} {label} on {when}.\n{summary}\n{note}\nOpen it here:\n{link}\n"
        ),
        html=render(
            preheader=f"{label} was {outcome} by {decided_by}.",
            heading=f"{label} was {outcome}",
            chip=(outcome.capitalize(), "positive" if outcome == "approved" else "negative"),
            paragraphs=[f"Hello {name}, {decided_by} {outcome} {label} on {when}."],
            facts=[("Document", label), (outcome.capitalize() + " by", decided_by), ("Details", summary)],
            quote=(comment, "positive" if outcome == "approved" else "negative") if comment else None,
            button=("Open it", link),
        ),
    )
