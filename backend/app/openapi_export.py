"""Write the API contract out of the running app, so the file clients generate their types from can never be written by
hand. A test fails when the committed copy is stale.

    python -m app.openapi_export openapi > openapi.json      the contract
    python -m app.openapi_export api-list > ../docs/api.md   the same operations as a readable table
"""

import json
import sys
from typing import Any

from fastapi import FastAPI

from app.main import create_app

METHODS = ("get", "post", "put", "patch", "delete")


def render_openapi(app: FastAPI) -> str:
    """The OpenAPI document as stable JSON: the same app always gives the same bytes."""
    return json.dumps(app.openapi(), indent=2, ensure_ascii=False) + "\n"


def _who(operation: dict[str, Any]) -> str:
    if operation.get("x-public"):
        return "anyone"
    return ", ".join(operation.get("x-roles", []))


def render_api_list(app: FastAPI) -> str:
    """Every operation, grouped by tag, with who may call it."""
    spec = app.openapi()
    groups: dict[str, list[tuple[str, str, dict[str, Any]]]] = {}
    for path, item in spec["paths"].items():
        for method in METHODS:
            operation = item.get(method)
            if operation is not None:
                tag = (operation.get("tags") or ["other"])[0]
                groups.setdefault(tag, []).append((method.upper(), path, operation))
    lines = [
        "# API",
        "",
        "Generated from `backend/openapi.json` by `python -m app.openapi_export api-list`. Do not edit by hand.",
        "Every path is under `/api/v1` except the probes. Errors share one shape (`docs/architecture.md`, section 8).",
        "",
    ]
    for tag in sorted(groups):
        lines += [f"## {tag}", "", "| Method | Path | Operation | Who | What it does |", "|---|---|---|---|---|"]
        for method, path, operation in sorted(groups[tag], key=lambda row: (row[1], row[0])):
            summary = (operation.get("description") or operation.get("summary") or "").strip().splitlines()
            first = summary[0].replace("|", "/") if summary else ""
            lines.append(f"| {method} | `{path}` | `{operation['operationId']}` | {_who(operation)} | {first} |")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    what = argv[1] if len(argv) > 1 else ""
    app = create_app()
    if what == "openapi":
        sys.stdout.write(render_openapi(app))
    elif what == "api-list":
        sys.stdout.write(render_api_list(app))
    else:
        sys.stderr.write("usage: python -m app.openapi_export openapi|api-list\n")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
