import ast
from pathlib import Path

from inferlingo import ExactUnifier, KnowledgeBase, Provenance


def facts_for_file(path: str) -> list[tuple[str, dict[str, object], Provenance]]:
    tree = ast.parse(Path(path).read_text(encoding="utf-8"), filename=path)
    facts: list[tuple[str, dict[str, object], Provenance]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            facts.append(
                (
                    "Function {fn} catches a broad exception",
                    {"fn": node.name},
                    Provenance(source=path, line=node.lineno, kind="python-ast"),
                )
            )
    return facts


async def lint(path: str):
    kb = KnowledgeBase.from_file("examples/python_lint_rules.nl", unifier=ExactUnifier())
    for template, values, provenance in facts_for_file(path):
        kb.add_fact(template, provenance=provenance, **values)
    return await kb.ask("Function {fn} needs review?")
