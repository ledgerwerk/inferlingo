from __future__ import annotations

import asyncio

import pytest

from inferlingo import Fact, KnowledgeBase, Provenance, RuleSet, Session


def test_knowledge_base_facade_and_safe_fact_injection():
    kb = KnowledgeBase.from_text(
        "Alice is an employee.\n{person} may deploy if {person} is an employee.",
        source="policy.nl",
    )
    kb.add_fact(
        "URL {url} is reachable",
        url="https://example.com/a",
        provenance=Provenance(source="scanner.py", line=4, kind="python-ast"),
    )
    result = kb.ask_sync("URL {url} is reachable?")
    assert result.solutions[0].bindings == {"url": "https://example.com/a"}
    assert result.solutions[0].proof.steps[0].provenance == Provenance(source="scanner.py", line=4, kind="python-ast")


def test_fact_renders_safe_values_and_copies_input_mapping():
    values = {"url": 'https://example.com/a?x=1&y=2 "quoted"'}
    fact = Fact(
        "URL {url} is reachable",
        values,
        provenance=Provenance(source="scanner.json", line=8, kind="http-check"),
        source="runtime-facts.nl",
    )
    values["url"] = "changed"

    assert '\\"quoted\\"' in fact.render()
    with pytest.raises(TypeError):
        fact.values["url"] = "mutated"  # type: ignore[index]

    rules = RuleSet.from_text("A static policy rule.")
    session = rules.session()
    assert isinstance(session, Session)
    session.add_fact(fact)
    result = session.ask_sync("URL {url} is reachable?")
    assert result.solutions[0].bindings == {"url": 'https://example.com/a?x=1&y=2 "quoted"'}
    assert result.solutions[0].proof.steps[0].provenance == fact.provenance
    assert result.solutions[0].proof.steps[0].source == "runtime-facts.nl"


def test_ruleset_sessions_and_per_request_facts_are_isolated():
    rules = RuleSet.from_text("{person} may deploy if {person} is an employee.")
    alice = rules.session()
    alice.add_fact(Fact("{person} is an employee", {"person": "Alice"}))
    bob = rules.session()
    bob.add_fact(Fact("{person} is an employee", {"person": "Bob"}))

    assert alice.ask_sync("{person} may deploy?").values("person") == ("Alice",)
    assert bob.ask_sync("{person} may deploy?").values("person") == ("Bob",)
    assert rules.ask_sync(
        "{person} may deploy?",
        facts=[Fact("{person} is an employee", {"person": "Carol"})],
    ).values("person") == ("Carol",)
    assert not rules.ask_sync("{person} may deploy?").matched


def test_ruleset_composes_multiple_rule_files(tmp_path):
    base = tmp_path / "base.nl"
    policy = tmp_path / "policy.nl"
    base.write_text("Alice has release role.\n", encoding="utf-8")
    policy.write_text("{person} may deploy if {person} has release role.\n", encoding="utf-8")

    rules = RuleSet.from_files([base, policy])
    result = rules.ask_sync("{person} may deploy?")

    assert result.values("person") == ("Alice",)
    assert rules.program.clauses[0].source == str(base)
    assert rules.program.clauses[1].source == str(policy)


def test_run_result_convenience_helpers():
    rules = RuleSet.from_text("Alice is known.\nBob is known.")
    result = rules.ask_sync("{person} is known?")
    assert result.matched
    assert result.first() == result.solutions[0]
    assert result.values("person") == ("Alice", "Bob")

    missing = rules.ask_sync("Carol is known?")
    assert not missing.matched
    assert missing.first() is None
    assert missing.values("person") == ()


def test_ask_sync_rejects_running_event_loop():
    async def scenario():
        kb = KnowledgeBase.from_text("Alice is known.")
        with pytest.raises(RuntimeError, match="running event loop"):
            kb.ask_sync("Alice is known?")

    asyncio.run(scenario())
