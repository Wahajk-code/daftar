# Skills and plugins

Keep this set small. Skills load only when relevant; plugins that add commands or servers cost context on every turn.
Review what a plugin does before enabling it, and add them during setup, not in the middle of a pass.

| Item | Use | When |
|---|---|---|
| `frontend-design` (built in) | A two-pass process for UI: write a design plan, critique it against the brief, then build. Lists the looks that mark an interface as generated | Passes 6, 7 and 9 |
| `daftar-ui` (this repo, `.claude/skills/daftar-ui/`) | The project's UI rules in one place: process, direction, tokens, themes, key screens, copy | Passes 6, 7 and 9 |
| A11y Enforcer (plugin) | WCAG 2.2 checks for HTML and React: labels, focus, keyboard traps, contrast | Pass 7 and Pass 9 |
| Playwright (plugin) | Browser automation: screenshots in light and dark at each breakpoint, and the end-to-end test | Pass 7 |
| Design (plugin) | Critique, UX writing and accessibility audits for screens and error copy | Passes 6 and 7 |

No skill is needed for the backend; `CLAUDE.md` carries those rules. Where a skill and `CLAUDE.md` disagree,
`CLAUDE.md` wins. Name the skill to apply in the prompt, for example: "Apply the daftar-ui skill. Write the design
plan first."
