Paste everything below the line into the Claude Code sidebar.

---

You are building Daftar, an expense, purchase and voucher manager, in this repository. Work autonomously.

Read first, in this order: CLAUDE.md, docs/workflow.md, docs/decisions.md. Then use docs/architecture.md, docs/domain-rules.md and docs/build-plan.md as each step needs them. Do not read other files unless a step requires it, and never open .env.

How to work:
- Follow docs/build-plan.md pass by pass, in order, starting with Pass 1. Tick each checkbox as the step is done.
- Run commands yourself, including Docker, tests, linters, type checks, builds, project dependency installs and migrations on the test database. Run lint, format and types before tests. If a gate fails twice, stop and show me the failure.
- Before any sensitive command, stop and ask me in the request format in docs/workflow.md, one command at a time, then run it yourself once I approve. The sensitive list is in CLAUDE.md. Never run git push.
- For any decision not already in docs/decisions.md, choose the best option, add a row with the reasoning and the strongest objection, and continue. If I disagree, argue your case once with evidence, then follow my call.
- Commit only after asking, in my name, with no trailer, one commit per coherent step. Messages use the pattern `add: <thing>`, `updated: <thing>` or `fixed: <thing>`, with the story ID in brackets when one applies. Show git diff --stat and the proposed message first.
- Append one row per significant prompt to Part B of PROMPTS.md (Part A already holds the planning prompts). Add to docs/MISTAKES.md only when you make a real mistake, and never invent one.
- Check the current Cloudinary and Expo documentation before using their APIs. Do not rely on memory for function names.

Stop only for a sensitive command, a gate that fails twice, a missing credential, an ambiguity that changes the result, the design checkpoint in Pass 6, or the end of a pass. At the end of each pass write the pass report in the format in docs/workflow.md and wait for me.

Begin Pass 1.
