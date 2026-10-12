"""Rules from CLAUDE.md enforced by reading the source, not by hope."""

import ast
import re
from collections.abc import Iterator
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "app"
DIVISION_ALLOWED = {"core/money.py", "core/allocation.py"}
STATUS_ALLOWED = {"core/transitions.py"}
EMOJI = re.compile("[\U0001f300-\U0001faff☀-➿⭐✅❌]")


def sources(subpackage: str | None = None) -> Iterator[tuple[str, ast.Module, str]]:
    root = APP / subpackage if subpackage else APP
    for path in sorted(root.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        yield path.relative_to(APP).as_posix(), ast.parse(text), text


def imported_modules(tree: ast.Module) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
            found.update(f"{node.module}.{alias.name}" for alias in node.names)
    return found


def under(module: str, package: str) -> bool:
    return module == package or module.startswith(package + ".")


def test_there_is_source_to_check() -> None:
    assert len(list(sources())) > 10


def test_routers_never_import_models_or_repositories() -> None:
    for name, tree, _ in sources("routers"):
        for module in imported_modules(tree):
            assert not under(module, "app.models"), f"{name} imports {module}"
            assert not under(module, "app.repositories"), f"{name} imports {module}"


def test_services_never_import_fastapi_or_starlette_or_routers() -> None:
    for name, tree, _ in sources("services"):
        for module in imported_modules(tree):
            for forbidden in ("fastapi", "starlette", "app.routers", "app.deps", "app.main"):
                assert not under(module, forbidden), f"{name} imports {module}"


def test_repositories_and_core_stay_below_the_services() -> None:
    for subpackage, forbidden in (
        ("repositories", ("app.services", "app.routers", "fastapi")),
        ("core", ("app.services", "app.routers", "app.repositories", "app.models", "fastapi", "sqlalchemy")),
        ("models", ("app.services", "app.routers", "app.repositories", "fastapi")),
    ):
        for name, tree, _ in sources(subpackage):
            for module in imported_modules(tree):
                for bad in forbidden:
                    assert not under(module, bad), f"{name} imports {module}"


def test_only_the_error_module_touches_http_exceptions() -> None:
    for name, tree, _ in sources():
        if name == "errors.py":
            continue
        for module in imported_modules(tree):
            assert not module.endswith("HTTPException"), f"{name} imports {module}; raise a DomainError instead"
        for node in ast.walk(tree):
            if isinstance(node, ast.Raise) and node.exc is not None:
                call = node.exc
                target = call.func if isinstance(call, ast.Call) else call
                assert not (isinstance(target, ast.Name) and target.id == "HTTPException"), name


def test_division_happens_only_in_money_and_allocation() -> None:
    for name, tree, _ in sources():
        if name in DIVISION_ALLOWED:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div | ast.FloorDiv | ast.Mod):
                pytest.fail(f"{name}:{node.lineno} divides; money maths belongs in core/money.py or core/allocation.py")
            if isinstance(node, ast.AugAssign) and isinstance(node.op, ast.Div | ast.FloorDiv | ast.Mod):
                pytest.fail(f"{name}:{node.lineno} divides")
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "divmod":
                pytest.fail(f"{name}:{node.lineno} divides")


def test_there_are_no_floats_in_the_application() -> None:
    for name, tree, _ in sources():
        for node in ast.walk(tree):
            # core/money.py names `float` once, to refuse it at the boundary.
            if isinstance(node, ast.Name) and node.id in {"float", "Float"} and name != "core/money.py":
                pytest.fail(f"{name}:{node.lineno} uses {node.id}; money is Decimal and NUMERIC(14,2)")
            if isinstance(node, ast.Attribute) and node.attr in {
                "Float",
                "FLOAT",
                "REAL",
                "DOUBLE_PRECISION",
            }:
                pytest.fail(f"{name}:{node.lineno} uses {node.attr}")
            if isinstance(node, ast.Constant) and isinstance(node.value, float):
                pytest.fail(f"{name}:{node.lineno} has a float literal")


def test_status_is_assigned_only_in_transitions() -> None:
    for name, tree, _ in sources():
        if name in STATUS_ALLOWED:
            continue
        for node in ast.walk(tree):
            targets: list[ast.expr] = []
            if isinstance(node, ast.Assign):
                targets = node.targets
            elif isinstance(node, ast.AugAssign | ast.AnnAssign):
                targets = [node.target]
            for target in targets:
                assert not (isinstance(target, ast.Attribute) and target.attr == "status"), (
                    f"{name}:{target.lineno} assigns .status; use core/transitions.py"
                )
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "setattr":
                field = node.args[1] if len(node.args) > 1 else None
                assert not (isinstance(field, ast.Constant) and field.value == "status"), (
                    f"{name}:{node.lineno} sets status with setattr"
                )


def test_no_naive_datetime_calls() -> None:
    for name, tree, _ in sources():
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in {"utcnow", "utcfromtimestamp"}:
                pytest.fail(f"{name}:{node.lineno} uses a naive datetime function")


def test_only_the_clock_reads_the_system_time() -> None:
    for name, tree, _ in sources():
        if name == "core/clock.py":
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "now":
                owner = node.func.value
                assert not (isinstance(owner, ast.Name) and owner.id == "datetime"), (
                    f"{name}:{node.lineno} calls datetime.now(); inject a Clock"
                )


def test_no_unfinished_markers_or_emoji_in_the_source() -> None:
    marker = re.compile(r"\b(TODO|FIXME|XXX|HACK)\b")
    for name, tree, text in sources():
        assert not marker.search(text), f"{name} has an unfinished marker"
        assert not EMOJI.search(text), f"{name} has an emoji"
        for node in ast.walk(tree):
            if isinstance(node, ast.Raise) and node.exc is not None:
                call = node.exc.func if isinstance(node.exc, ast.Call) else node.exc
                assert not (isinstance(call, ast.Name) and call.id == "NotImplementedError"), f"{name} is a stub"


def test_request_schemas_reject_unknown_fields() -> None:
    import importlib
    import pkgutil

    import app.schemas as schemas_package
    from app.schemas.base import RequestModel

    for module in pkgutil.iter_modules(schemas_package.__path__):
        importlib.import_module(f"app.schemas.{module.name}")
    stack = list(RequestModel.__subclasses__())
    while stack:
        model = stack.pop()
        assert model.model_config.get("extra") == "forbid", model.__name__
        stack.extend(model.__subclasses__())
