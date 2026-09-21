from __future__ import annotations

import asyncio
from pathlib import Path

from examples.python_linter import facts_for_file
from inferlingo import ExactUnifier, KnowledgeBase, parse_program

ROOT = Path(__file__).parents[1]


def ask(path: str, query: str):
    return asyncio.run(KnowledgeBase.from_file(ROOT / path, unifier=ExactUnifier()).ask(query))


def test_exact_examples_execute_without_backend():
    assert ask("examples/birds.nl", "{bird} can fly?").solutions[0].bindings == {"bird": "Tweety"}
    assert [
        solution.bindings["person"] for solution in ask("examples/access_policy.nl", "{person} may deploy?").solutions
    ] == ["Alice"]
    assert {
        solution.bindings["service"]
        for solution in ask("examples/dependency_impact.nl", "{service} is affected?").solutions
    } == {"auth", "api", "web"}


def test_python_linter_rules_derive_findings():
    kb = KnowledgeBase.from_file(ROOT / "examples/python_lint_rules.nl", unifier=ExactUnifier())
    kb.add_fact("Function {fn} catches a broad exception", fn="process_order")
    kb.add_fact("Function {fn} has an exception path that does not re-raise", fn="process_order")
    result = asyncio.run(kb.ask("Function {fn} may swallow errors?"))
    assert result.solutions[0].bindings == {"fn": "process_order"}


def test_python_linter_extracts_facts_and_derives_review(tmp_path):
    source = tmp_path / "orders.py"
    source.write_text(
        """
def process_order(order):
    try:
        save_order(order)
    except Exception:
        send_notification(order)


def safe_order(order):
    try:
        save_order(order)
    except ValueError:
        raise
        """,
        encoding="utf-8",
    )

    facts = facts_for_file(source)
    process_facts = [(template, values) for template, values, _provenance in facts if values["fn"] == "process_order"]
    assert ("Function {fn} catches a broad exception", {"fn": "process_order"}) in process_facts
    assert (
        "Function {fn} has an exception path that does not re-raise",
        {"fn": "process_order"},
    ) in process_facts
    assert not any(
        template == "Function {fn} catches a broad exception" and values["fn"] == "safe_order"
        for template, values, _provenance in facts
    )

    kb = KnowledgeBase.from_file(ROOT / "examples/python_lint_rules.nl", unifier=ExactUnifier())
    for template, values, provenance in facts:
        kb.add_fact(template, provenance=provenance, **values)
    result = asyncio.run(kb.ask("Function {fn} needs review?"))
    assert {solution.bindings["fn"] for solution in result.solutions} == {"process_order"}
    assert any(step.provenance and step.provenance.source == str(source) for step in result.solutions[0].proof.steps)


def test_all_nl_examples_parse_in_strict_mode():
    for path in sorted((ROOT / "examples").glob("*.nl")):
        parse_program(path.read_text(encoding="utf-8"), source=str(path), strict=True)
