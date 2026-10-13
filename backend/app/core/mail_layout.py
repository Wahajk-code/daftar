# ruff: noqa: E501  (inline-styled HTML strings are long by nature)
"""The HTML wrapper for every email, in the same soft monochrome look as the app: a white card on a light grey page, a near-black
pill button, large radii, and colour only where it means something (a status). Email programs ignore most CSS, so the layout is
a table with inline styles, a system font stack and no images: the logo is a placeholder tile made of text, to be swapped for
the real mark later by changing LOGO_HTML in one place."""

from collections.abc import Sequence
from html import escape

INK = "#0B0B0C"
PAGE = "#EBEBEB"
CARD = "#FEFEFE"
SOFT = "#F7F7F7"
RULE = "#E2E2E2"
TEXT_2 = "#525252"
TEXT_3 = "#767676"
GREEN = "#0A7F57"
RED = "#B3261E"
AMBER = "#96610A"
FONT = "'Inter Tight','Inter',-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"

# The placeholder mark: a rounded dark tile with a D. Replace this one value with an <img> when there is a real logo.
LOGO_HTML = (
    f'<table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>'
    f'<td width="40" height="40" align="center" valign="middle" style="width:40px;height:40px;background:{INK};'
    f'border-radius:12px;color:{CARD};font:800 20px/40px {FONT};">D</td>'
    f'<td style="padding-left:12px;font:800 22px/1 {FONT};letter-spacing:-0.03em;color:{INK};">Daftar</td>'
    f"</tr></table>"
)

TONES = {"neutral": TEXT_2, "positive": GREEN, "negative": RED, "caution": AMBER}


def _paragraph(text: str) -> str:
    return f'<p style="margin:0 0 16px;font:400 15px/1.6 {FONT};color:{TEXT_2};">{escape(text)}</p>'


def _facts(facts: Sequence[tuple[str, str]]) -> str:
    rows = "".join(
        f'<tr><td style="padding:10px 0;border-top:1px solid {RULE};font:400 13px/1.4 {FONT};color:{TEXT_3};width:38%;">'
        f"{escape(label)}</td>"
        f'<td style="padding:10px 0;border-top:1px solid {RULE};font:700 14px/1.4 {FONT};color:{INK};">{escape(value)}</td></tr>'
        for label, value in facts
    )
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="margin:8px 0 20px;background:{SOFT};border-radius:14px;"><tr><td style="padding:6px 18px;">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">{rows}</table></td></tr></table>'
    )


def _quote(text: str, tone: str) -> str:
    colour = TONES.get(tone, TEXT_2)
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:4px 0 20px;">'
        f'<tr><td style="padding:14px 18px;border-left:4px solid {colour};background:{SOFT};border-radius:10px;'
        f'font:600 15px/1.55 {FONT};color:{INK};">{escape(text)}</td></tr></table>'
    )


def _button(label: str, link: str) -> str:
    return (
        f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:8px 0 20px;"><tr>'
        f'<td align="center" style="background:{INK};border-radius:999px;">'
        f'<a href="{escape(link, quote=True)}" style="display:inline-block;padding:14px 28px;font:700 15px/1 {FONT};'
        f'color:{CARD};text-decoration:none;border-radius:999px;">{escape(label)}</a></td></tr></table>'
    )


def _chip(text: str, tone: str) -> str:
    colour = TONES.get(tone, TEXT_2)
    return (
        f'<span style="display:inline-block;padding:3px 12px;border:1.5px solid {colour};border-radius:999px;'
        f'font:700 12px/1.4 {FONT};color:{colour};">{escape(text)}</span>'
    )


def render(
    *,
    preheader: str,
    heading: str,
    paragraphs: Sequence[str] = (),
    chip: tuple[str, str] | None = None,
    facts: Sequence[tuple[str, str]] = (),
    quote: tuple[str, str] | None = None,
    button: tuple[str, str] | None = None,
    after: Sequence[str] = (),
    footer: str = "You received this because of your Daftar account.",
) -> str:
    body = (
        (f'<p style="margin:0 0 14px;">{_chip(*chip)}</p>' if chip else "")
        + f'<h1 style="margin:0 0 14px;font:800 26px/1.2 {FONT};letter-spacing:-0.03em;color:{INK};">{escape(heading)}</h1>'
        + "".join(_paragraph(text) for text in paragraphs)
        + (_facts(facts) if facts else "")
        + (_quote(*quote) if quote else "")
        + (_button(*button) if button else "")
        + "".join(_paragraph(text) for text in after)
    )
    link_note = ""
    if button:
        link_note = (
            f'<p style="margin:0;font:400 12px/1.5 {FONT};color:{TEXT_3};word-break:break-all;">'
            f"If the button does not work, copy this address into your browser:<br>{escape(button[1])}</p>"
        )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="color-scheme" content="light"><meta name="supported-color-schemes" content="light">'
        f"<title>{escape(heading)}</title></head>"
        f'<body style="margin:0;padding:0;background:{PAGE};">'
        f'<div style="display:none;max-height:0;overflow:hidden;opacity:0;">{escape(preheader)}</div>'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:{PAGE};">'
        '<tr><td align="center" style="padding:32px 16px;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width:560px;">'
        f'<tr><td style="padding:0 8px 20px;">{LOGO_HTML}</td></tr>'
        f'<tr><td style="background:{CARD};border-radius:24px;padding:32px 32px 20px;'
        f'box-shadow:0 1px 2px rgba(11,11,12,0.04),0 8px 24px rgba(11,11,12,0.06);">{body}{link_note}</td></tr>'
        f'<tr><td style="padding:20px 12px 0;font:400 12px/1.5 {FONT};color:{TEXT_3};text-align:center;">'
        f"{escape(footer)}<br>Daftar: expenses, purchases and vouchers.</td></tr>"
        "</table></td></tr></table></body></html>"
    )
