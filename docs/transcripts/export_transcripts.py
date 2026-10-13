"""Turn the Claude Code session logs into readable, scrubbed Markdown and total the token usage.

Usage: python make_transcripts.py <projects-dir> <out-dir>
Writes <out-dir>/NN-<phase>.md files, <out-dir>/_usage.json and <out-dir>/_parts.json (for the index)."""

import json
import pathlib
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

src = pathlib.Path(sys.argv[1])
out = pathlib.Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)

FILES = [
    "8af30a7c-f939-4b20-8464-cf7dda41e51a.jsonl",
    "dfbd9464-2a54-4afd-b440-c849197a1f6f.jsonl",
    "94516ed0-d263-4f22-adb3-b204c7e6b495.jsonl",
    "9afa14c8-111a-4eab-a708-661dccfa5cd5.jsonl",
]

# Phases by UTC time, from the commit history (commits are made when the owner approves each pass).
PHASES = [
    ("2026-10-12T16:59:00Z", "pass-01-foundation", "Pass 1: backend foundation, Docker stack, tests, Next.js scaffold"),
    ("2026-10-12T18:26:00Z", "pass-02-access-master-data", "Pass 2: access control and master data"),
    ("2026-10-12T19:48:00Z", "pass-03-documents", "Pass 3: expenses, purchases, attachments, approval workflow"),
    ("2026-10-12T20:55:00Z", "pass-04-ledger", "Pass 4: vouchers, ledger rules, numbering, posting, void, generation"),
    ("2026-10-12T22:45:00Z", "pass-05-email-reports", "Pass 5: email, reports, CSV, duplicates, seed, OpenAPI"),
    ("2026-10-13T06:59:00Z", "pass-06-web-app", "Pass 6: the web app for all four roles"),
    ("2026-10-13T08:31:00Z", "pass-06-design-pass-two", "Pass 6 (second design pass): redesign and owner QA fixes"),
    ("2026-10-13T11:35:00Z", "pass-06-hardening-pwa", "Pass 6 (hardening): draft visibility, redirects, forms, search, print, exports, PWA camera"),
    ("2026-10-13T13:23:00Z", "pass-08-deploy-and-live-fixes", "Deploy: Neon, Render, Vercel, live-site fixes, email (SMTP), submission prep"),
]
PLANNING = ("2026-10-10T00:00:00Z", "planning-and-docs", "Planning: brief, specification, architecture, workflow and decisions (before Pass 1)")


def parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def phase_of(ts: str):
    moment = parse_ts(ts)
    chosen = PLANNING
    for phase in PHASES:
        if moment >= parse_ts(phase[0]):
            chosen = phase
    return chosen


# ----------------------------------------------------------------------------------------------------- scrubbing
SECRET_NAMES = r"(?:SECRET_KEY|BFF_SHARED_SECRET|SMTP_PASS|RESEND_API_KEY|CLOUDINARY_URL|DATABASE_URL|MIGRATION_DATABASE_URL|APP_DB_PASSWORD|POSTGRES_PASSWORD)"
RULES = [
    (re.compile(r"cloudinary://[^\s\"'`<>)]+"), "cloudinary://<redacted>"),
    (re.compile(r"\bre_[A-Za-z0-9_]{16,}"), "re_<redacted>"),
    (re.compile(r"\bnpg_[A-Za-z0-9]+"), "<redacted>"),
    (re.compile(r"(postgres(?:ql)?(?:\+\w+)?://[^:/\s@]+):[^@\s]+@"), r"\1:<redacted>@"),
    (re.compile(r"\bep-[a-z0-9-]+\.[a-z0-9.-]*neon\.tech"), "<neon-host>"),
    (re.compile(rf"({SECRET_NAMES})\s*=\s*[^\s\"'`]+"), r"\1=<redacted>"),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,}"), "<jwt-redacted>"),
    (re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{12,}"), "Bearer <redacted>"),
    (re.compile(r"(?<![A-Za-z0-9+/])[A-Za-z0-9+/]{40,}={1,2}(?![A-Za-z0-9+/=])"), "<secret-redacted>"),
    (re.compile(r"\b\d{15}\b"), "<id-redacted>"),
    (re.compile(r"[A-Za-z]:[\\/]+(?:Users|users)[\\/]+[^\s\"'`<>|]+"), "<local-path>"),
    (re.compile(r"[A-Za-z]:[\\/]+Freelancing[\\/]+saliklabs[^\s\"'`<>|]*"), "<workspace>"),
    (re.compile(r"/(?:c|d)/(?:Users|Freelancing)/[^\s\"'`<>|]+"), "<workspace>"),
    (re.compile(r"\bMYPC~1\b"), "<user>"),
    (re.compile(r"[A-Za-z0-9._%+-]+@(?!daftar\.pk\b)(?!visionpme\.ca\b)[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "<email>"),
]


def scrub(text: str) -> str:
    for pattern, replacement in RULES:
        text = pattern.sub(replacement, text)
    return text


STRIP = [
    re.compile(r"<system-reminder>.*?</system-reminder>", re.S),
    re.compile(r"<ide_opened_file>.*?</ide_opened_file>", re.S),
    re.compile(r"<ide_selection>.*?</ide_selection>", re.S),
    re.compile(r"<local-command-caveat>.*?</local-command-caveat>", re.S),
    re.compile(r"<command-(?:name|message|args)>.*?</command-(?:name|message|args)>", re.S),
    re.compile(r"<local-command-stdout>.*?</local-command-stdout>", re.S),
    re.compile(r"<task-notification>.*?</task-notification>", re.S),
    re.compile(r"\[SYSTEM NOTIFICATION - NOT USER INPUT\].*?(?=\n\n|\Z)", re.S),
]


def clean(text: str) -> str:
    for pattern in STRIP:
        text = pattern.sub("", text)
    text = re.sub(r"<pasted_content[^>]*>(.*?)</pasted_content[^>]*>", lambda m: "[pasted: " + m.group(1).strip()[:400].replace("\n", " ") + " ...]", text, flags=re.S)
    return text.strip()


# ----------------------------------------------------------------------------------------------------- reading
entries = {}
usage_by_id = {}
for name in FILES:
    tool_names = {}
    for line in open(src / name, encoding="utf-8"):
        try:
            d = json.loads(line)
        except ValueError:
            continue
        kind = d.get("type")
        if kind not in ("user", "assistant"):
            continue
        ts = d.get("timestamp")
        message = d.get("message") or {}
        content = message.get("content")
        if kind == "assistant":
            mid = message.get("id") or d.get("uuid")
            u = message.get("usage") or {}
            row = {k: (u.get(k) or 0) for k in ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")}
            if message.get("model") != "<synthetic>" and (mid not in usage_by_id or row["output_tokens"] >= usage_by_id[mid][1]["output_tokens"]):
                usage_by_id[mid] = (ts, row)
        blocks = content if isinstance(content, list) else ([{"type": "text", "text": content}] if isinstance(content, str) else [])
        texts, tools, approvals, images = [], Counter(), [], 0
        for block in blocks:
            btype = block.get("type")
            if btype == "text":
                texts.append(block.get("text", ""))
            elif btype == "image":
                images += 1
            elif btype == "tool_use":
                tools[block.get("name", "tool")] += 1
                tool_names[block.get("id")] = (block.get("name"), block.get("input"))
            elif btype == "tool_result":
                tname, tinput = tool_names.get(block.get("tool_use_id"), (None, None))
                if tname == "AskUserQuestion":
                    result = block.get("content")
                    if isinstance(result, list):
                        result = " ".join(x.get("text", "") for x in result if isinstance(x, dict))
                    question = ""
                    if isinstance(tinput, dict) and tinput.get("questions"):
                        question = tinput["questions"][0].get("question", "")
                    approvals.append((question, str(result)))
        key = (ts, kind)
        record = {"ts": ts, "kind": kind, "texts": texts, "tools": tools, "approvals": approvals, "images": images, "summary": bool(d.get("isCompactSummary"))}
        if key in entries:
            # the same message copied into a later session file: keep the one that has more in it
            old = entries[key]
            if sum(len(t) for t in record["texts"]) > sum(len(t) for t in old["texts"]):
                entries[key] = record
        else:
            entries[key] = record

ordered = [entries[k] for k in sorted(entries, key=lambda k: (k[0], 0 if k[1] == "user" else 1))]

# ----------------------------------------------------------------------------------------------------- writing
parts = defaultdict(list)
for record in ordered:
    parts[phase_of(record["ts"])[1]].append(record)

MAX_CHARS = 900_000
index = []
number = 0
phase_list = [PLANNING] + PHASES
for phase in phase_list:
    slug = phase[1]
    records = parts.get(slug, [])
    if not records:
        continue
    chunks, current, size = [], [], 0
    for record in records:
        piece = []
        who = "Owner" if record["kind"] == "user" else "Claude"
        stamp = record["ts"][:16].replace("T", " ") + " UTC"
        if record["kind"] == "user":
            body = clean("\n\n".join(record["texts"]))
            if record["summary"] or body.startswith("This session is being continued"):
                body = "(context summary written by the tool when the conversation was compacted; omitted)"
            if not body and record["images"]:
                body = "[screenshot]"
            elif record["images"]:
                body += f"\n\n[+{record['images']} screenshot(s)]"
            if body:
                piece.append(f"### {who}, {stamp}\n\n{scrub(body)}\n")
            for question, answer in record["approvals"]:
                piece.append(f"### Approval request answered, {stamp}\n\n**Asked:** {scrub(question)[:600]}\n\n**Answer:** {scrub(answer)[:500]}\n")
        else:
            body = clean("\n\n".join(record["texts"]))
            tools = ", ".join(f"{n} x{c}" for n, c in sorted(record["tools"].items()))
            if body or tools:
                piece.append(f"### {who}, {stamp}\n\n" + (scrub(body) + "\n" if body else "") + (f"\n_Tools used: {tools}_\n" if tools else ""))
        text = "\n".join(piece)
        if not text:
            continue
        if size + len(text) > MAX_CHARS and current:
            chunks.append(current)
            current, size = [], 0
        current.append(text)
        size += len(text)
    if current:
        chunks.append(current)
    for ci, chunk in enumerate(chunks, start=1):
        number += 1
        suffix = f"-part-{ci}" if len(chunks) > 1 else ""
        name = f"{number:02d}-{slug}{suffix}.md"
        first = records[0]["ts"][:16].replace("T", " ")
        title = f"{phase[2]}" + (f" (part {ci} of {len(chunks)})" if len(chunks) > 1 else "")
        header = f"# {title}\n\nThe conversation between the owner and Claude Code, text only. Tool output is left out (only the names of the tools used are shown) and secrets, local paths and email addresses are removed. Times are UTC.\n\n---\n\n"
        body = header + "\n".join(chunk)
        (out / name).write_text(body, encoding="utf-8")
        index.append({"file": name, "phase": phase[2], "slug": slug, "bytes": len(body.encode("utf-8")), "messages": len(chunk)})

(out / "_parts.json").write_text(json.dumps(index, indent=1), encoding="utf-8")

# ----------------------------------------------------------------------------------------------------- usage
totals = defaultdict(Counter)
overall = Counter()
calls = Counter()
for mid, (ts, row) in usage_by_id.items():
    slug = phase_of(ts)[1]
    for k, v in row.items():
        totals[slug][k] += v
        overall[k] += v
    calls[slug] += 1
(out / "_usage.json").write_text(json.dumps({"overall": overall, "calls": sum(calls.values()), "by_phase": {k: dict(v, calls=calls[k]) for k, v in totals.items()}}, indent=1), encoding="utf-8")
print(json.dumps({"parts": len(index), "calls": sum(calls.values()), "overall": overall}, indent=1))
