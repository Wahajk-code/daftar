"""The wording of each email. Plain text, one function per template."""

from app.core.mail import EmailMessage


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
    )
