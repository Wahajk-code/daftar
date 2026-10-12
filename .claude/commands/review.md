---
description: Cold review of the uncommitted work. Report only
---

Review the uncommitted changes as an engineer who will inherit this repo and did not write it. Do not edit, fix or commit.

Check: a float in a money path; a rule held only by Python that the database should hold; a trigger that needs deferring
and is not; naive rounding in an allocation; a sequence or `MAX+1` for numbering; a delete or in-place edit where a
reversal belongs; `.status` assigned directly; a route with a role check but no ownership check in the service; error
text that reveals whether a record exists; email sent before commit; a list endpoint without pagination; an N+1 query;
a lock or idempotency feature with no parallel test; a test that asserts mock calls, asserts nothing, or would pass if the
function returned a constant; a TODO, stub, dead code or unrequested dependency; a secret in a file or log; work outside
the current pass.

Output a table: severity (blocker, should-fix, nit), file and line, what is wrong, why it matters. Then one line: would
you approve this as it stands, yes or no, and the one thing that must change first. If you find nothing, say so.
