from __future__ import annotations

import argparse
import ast
import asyncio
from collections.abc import Iterator
from pathlib import Path

from inferlingo import ExactUnifier, KnowledgeBase, Provenance

ROOT = Path(__file__).parents[1]
BROAD_EXCEPTION_NAMES = {"BaseException", "Exception"}
PERSISTENCE_CALLS = {"commit", "save", "save_order", "update", "write"}
NOTIFICATION_CALLS = {"notify", "send", "send_email", "send_notification"}


def _call_name(node: ast.Call) -> str | None:
    function = node.func
    if isinstance(function, ast.Name):
        return function.id
    if isinstance(function, ast.Attribute):
        return function.attr
    return None


def _contains_raise(handler: ast.ExceptHandler) -> bool:
    return any(isinstance(node, ast.Raise) for node in ast.walk(handler))


def _function_nodes(tree: ast.AST) -> Iterator[ast.FunctionDef | ast.AsyncFunctionDef]:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node


def facts_for_file(path: str | Path) -> list[tuple[str, dict[str, object], Provenance]]:
    source_path = Path(path)
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    facts: list[tuple[str, dict[str, object], Provenance]] = []

    for function in _function_nodes(tree):
        function_name = function.name
        function_line = function.lineno
        handlers = [node for node in ast.walk(function) if isinstance(node, ast.ExceptHandler)]
        broad_handlers = [
            handler
            for handler in handlers
            if handler.type is None or (isinstance(handler.type, ast.Name) and handler.type.id in BROAD_EXCEPTION_NAMES)
        ]
        for handler in broad_handlers:
            facts.append(
                (
                    "Function {fn} catches a broad exception",
                    {"fn": function_name},
                    Provenance(source=str(source_path), line=handler.lineno, kind="python-ast"),
                )
            )
            if not _contains_raise(handler):
                facts.append(
                    (
                        "Function {fn} has an exception path that does not re-raise",
                        {"fn": function_name},
                        Provenance(source=str(source_path), line=handler.lineno, kind="python-ast"),
                    )
                )

        if function.end_lineno is not None and function.end_lineno - function_line + 1 >= 50:
            facts.append(
                (
                    "Function {fn} is long",
                    {"fn": function_name},
                    Provenance(source=str(source_path), line=function_line, kind="python-ast"),
                )
            )

        calls = [node for node in ast.walk(function) if isinstance(node, ast.Call)]
        for call in calls:
            call_name = _call_name(call)
            if call_name in PERSISTENCE_CALLS:
                facts.append(
                    (
                        "Function {fn} writes persistent state",
                        {"fn": function_name},
                        Provenance(source=str(source_path), line=call.lineno, kind="python-ast"),
                    )
                )
            if call_name in NOTIFICATION_CALLS:
                facts.append(
                    (
                        "Function {fn} sends a notification",
                        {"fn": function_name},
                        Provenance(source=str(source_path), line=call.lineno, kind="python-ast"),
                    )
                )
    return facts


async def lint(path: str | Path):
    rules_path = ROOT / "examples/python_lint_rules.nl"
    kb = KnowledgeBase.from_file(rules_path, unifier=ExactUnifier())
    for template, values, provenance in facts_for_file(path):
        kb.add_fact(template, provenance=provenance, **values)
    return await kb.ask("Function {fn} needs review?")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Advanced example: deterministic Python observations feeding explicit InferLingo policy rules."
    )
    parser.add_argument("path", type=Path, help="Python source file to inspect")
    args = parser.parse_args()
    result = asyncio.run(lint(args.path))
    print("InferLingo deterministic analyzer + policy demo")
    print("Python AST observations -> explicit .nl policy rules -> findings")
    if not result.solutions:
        print("No review findings.")
        return
    for solution in result.solutions:
        print(f"Function {solution.bindings['fn']} needs review")
        print(solution.proof.render())


if __name__ == "__main__":
    main()
