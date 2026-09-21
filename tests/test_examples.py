from __future__ import annotations

import asyncio
from pathlib import Path

from inferlingo import ExactUnifier, KnowledgeBase

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
