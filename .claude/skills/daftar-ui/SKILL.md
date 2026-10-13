---
name: daftar-ui
description: Use when building or changing any screen, component, theme or copy in the Daftar web app. Covers the design process, the soft monochrome direction, tokens, themes, tables and forms for dense accounting screens, and the checks that stop it looking generated.
---

# Daftar UI

Daftar is accounting software used all day by accountants. Design for the 200th use, not the first
impression. Read the built-in frontend-design skill first if it is available, then apply this.

## Process (do not skip)
1. Write a short design plan before any code: 4 to 6 named colours with hex values, the typefaces and
   their roles, one layout idea, and what makes this product distinct. Show it and wait for approval.
2. Critique the plan against the brief. If a part is what you would produce for any finance app, change it
   and say what you changed.
3. Build one screen. Screenshot it in light and dark at 360 and 1440 px. Critique. Then continue.

## Direction: soft monochrome (decisions 130 to 139)
White cards with a soft shadow on a light grey page. Near-black ink for text, the primary pill button and the current place
in the sidebar; large radii (8, 12, 18, 24 px, pills for buttons, chips and tabs). Colour only where it means something:
status chips (draft grey, submitted amber, approved blue, rejected red, posted green, void struck), type chips, debit and
credit, charts. Inter Tight for the interface and headings, Inter for tables and figures (tabular, right-aligned amounts).
One roomy row height (56 px); there is no density option. Hierarchy: the main thing in a row is dark and heavy (a two-line
cell: what it is, and a quiet line under it), figures are strong, everything else is quiet. Long text is cut with an ellipsis
and the whole text is on the element's title. Rows that lead somewhere are pressable and end in an arrow; links are underlined.
Do **not** add a brand accent colour, gradients, an all-caps eyebrow over every heading, or a monospace face.

## Tokens
Three tiers: primitives, semantic (the only tier that changes per theme), component. Components never
use a primitive or a hex value. No `#fff` or `#000`. Dark mode re-picks semantic colours (lighter,
less saturated) and lifts surfaces by lightness; shadows are only deeper. Receipt images are never
inverted. Declare `color-scheme`. Theme is System, Light or Dark, set before first paint; the header toggle switches light
and dark. Theming is CSS only; no component checks the colour scheme. A semantic value written `raw:` (shadows) is copied
as it is. Chart colours (`chart-1`, `chart-2`) are checked with the dataviz skill's validator in both themes.

## Screens
- Voucher editor: spreadsheet-like lines, a persistent strip showing debit, credit and difference, one
  button inserts the exact balancing line, Submit explains why it is disabled.
- Allocation editor: live remainder and a preview of exact per-centre amounts.
- Approval detail: document, receipt and timeline together; approve and reject always reachable.

## Always
Pending state and disabled button on every mutation; toast on success and failure; never optimistic UI
for post, void or approve; empty, loading and error states on every data surface; visible focus; pointer
cursor on clickable things; 44 px mobile targets; labels bound to inputs; `inputmode="decimal"` on amounts;
filters, sort and page in the URL; one money format and one date format everywhere.

## Copy
Plain verbs, sentence case, active voice. A button names what happens ("Post voucher"), and the toast
repeats it ("Voucher posted"). Errors say what happened and what to do, and do not apologise. No
exclamation marks, no emoji, no "seamlessly" or "powerful". Empty screens say what to do next.

## Do not
Use stock illustration, stat cards with invented trends (every figure comes from a real query), gradient
washes, an all-caps eyebrow above every heading, or motion that is not a response to an action (the logo drawing in, the
drift of the login art and the shimmer of a skeleton are the exceptions, and all stop under reduced motion).

## Public screens (login, forgot password, reset password, accept invite)
One 50/50 split on the grey page: an illustrated card and the form card, equal width from the tablet breakpoint up. Below it the
illustration goes and the panel collapses to a compact header above the form. The left card holds the logo, an original flat
illustration (two people at a giant open ledger, in the app's own colours) and one line of copy. The form is one column with a
comfortable maximum width, clear errors that do not reveal whether an email exists, and a visible focus ring. A demo-accounts
helper appears under the form only when `DEMO_MODE` is on. All four screens look identical in structure, in both themes.

## Onboarding tour
Written for the person: their name, their role, what is waiting for them now, and only the steps their role has (4 to 7).
"Step 2 of 5" is shown. Skip is always visible and Escape closes it. Next and Back work by keyboard; focus stays inside the card
and returns to the page afterwards. The card is our own (white, dark text, dark buttons), so it is legible in both themes. The
tour never blocks the app, respects reduced motion, and is correct at 360 px. It starts by itself on first sign-in; finishing
or skipping is saved on the server; it can be started again only from the Help center.

## Always (screen frame)
Header: fold, New (modal forms), bell, theme toggle, Help, account. New documents open in a modal over the page with a blurred
backdrop. Lists: search, status pills, Filters panel, chips, pressable rows. Every data surface has a shaped skeleton.
