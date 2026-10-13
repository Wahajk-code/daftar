"""Send one test email with the configured settings and say plainly whether it worked.

    python -m app.mail_check someone@example.com

The API never shows an email failure (it logs it and moves on), so this is the way to see one. It uses the same
transport, server, login and sender as the running API and prints no password. A refusal prints the server's own
reason, for example that the login was not accepted (a Google app password is needed, not the account password) or
that the sender is not an address the account may send as."""

import sys

from app.config import get_settings
from app.core import mail_templates
from app.core.mail import build_mailer


def main(argv: list[str]) -> int:
    if len(argv) != 2 or "@" not in argv[1]:
        sys.stderr.write("Usage: python -m app.mail_check someone@example.com\n")
        return 2
    to = argv[1]
    settings = get_settings()
    web = settings.web_base_url.rstrip("/")
    message = mail_templates.invite(
        to=to,
        role="Accountant",
        link=f"{web}/accept-invite?token=this-is-only-a-test",
        expires="a week from now",
        invited_by="the email check",
    )
    sys.stdout.write(f"transport: {settings.mail_transport}\n")
    if settings.mail_transport == "smtp":
        sys.stdout.write(
            f"server:    {settings.smtp_host}:{settings.smtp_port} (login: {settings.smtp_user or 'none'})\n"
        )
    sys.stdout.write(f"from:      {settings.mail_from}\nto:        {to}\nlinks:     {web}/...\n")
    try:
        build_mailer(settings).send(message)
    except Exception as error:  # the point is to show the reason, whatever it is
        sys.stdout.write(f"FAILED: {type(error).__name__}: {error}\n")
        return 1
    note = (
        "" if settings.mail_transport == "smtp" else " (console transport: written to the log, nothing was delivered)"
    )
    sys.stdout.write(f"The server accepted it.{note}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
