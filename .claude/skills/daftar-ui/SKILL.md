---
name: daftar-ui
description: Use when building or changing any screen, component, theme or copy in the Daftar web or mobile app. Covers the design process, the Ledger direction, tokens, themes, tables and forms for dense accounting screens, and the checks that stop it looking generated.
---

# Daftar UI

Daftar is dense accounting software used all day by accountants. Design for the 200th use, not the first
impression. Read the built-in frontend-design skill first if it is available, then apply this.

## Process (do not skip)
1. Write a short design plan before any code: 4 to 6 named colours with hex values, the typefaces and
   their roles, one layout idea, and what makes this product distinct. Show it and wait for approval.
2. Critique the plan against the brief. If a part is what you would produce for any finance app, change it
   and say what you changed.
3. Build one screen. Screenshot it in light and dark at 360 and 1440 px. Critique. Then continue.

## Direction: Ledger
Dense tables, not cards. Tabular figures on every amount, right-aligned. Rules (1px lines) carry
structure instead of shadows. One accent colour plus debit and credit meanings. Do **not** default to a
cream background with a serif display face and a terracotta accent, or to a near-black background with one
acid accent: those are the most common generated looks. Choose the palette and fonts for this product.

## Tokens
Three tiers: primitives, semantic (the only tier that changes per theme), component. Components never
use a primitive or a hex value. No `#fff` or `#000`. Dark mode re-picks semantic colours (lighter,
less saturated) and expresses elevation with lighter surfaces, never shadows. Receipt images are never
inverted. Declare `color-scheme`. Theme is System, Light or Dark, set before first paint. Theming is CSS
only; no component checks the colour scheme.

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
Use stock illustration, a stat-card dashboard with invented trends, identical rounded cards, gradient
washes, an all-caps eyebrow above every heading, or motion that is not a response to an action.

## Public screens (login, forgot password, reset password, accept invite)
One 50/50 split: a brand panel and the form, equal width from the tablet breakpoint up. Below it the panel collapses to a
compact header above the form. The panel is restrained and made from the product's own tokens (a ledger motif, the name,
one line of copy); no stock illustration, no gradient wash. The form is one column with a comfortable maximum width, clear
errors that do not reveal whether an email exists, and a visible focus ring. A demo-accounts helper appears under the form
only when `DEMO_MODE` is on. All four screens look identical in structure, in both themes.

## Onboarding tour
4 to 6 steps chosen for the user's role, one sentence and one pointer each, with "step 2 of 5" shown. Skip is always visible
and Escape closes it. Next and Back work by keyboard; focus stays inside the popover and returns to the page afterwards.
The tour never blocks the app, respects reduced motion, and is correct at 360 px and in both themes. Finishing or skipping
is saved on the server; "Take the tour" in the profile menu relaunches it. Mobile uses a three-card intro with the same flag.
