from __future__ import annotations

import asyncio

from inferlingo import ExactUnifier, Fact, NLEngine, Provenance, RuleSet, parse_program, parse_query


def test_each_solution_has_a_branch_local_proof_and_global_trace():
    program = parse_program(
        """
        Alice is known.
        Bob is known.
        {person} is trusted if {person} is known.
        """,
        source="policy.nl",
    )
    result = asyncio.run(NLEngine(program, ExactUnifier()).run(parse_query("{person} is trusted?")))
    assert [solution.bindings for solution in result.solutions] == [{"person": "Alice"}, {"person": "Bob"}]
    assert all(solution.proof.steps for solution in result.solutions)
    assert result.solutions[0].proof is not result.solutions[1].proof
    assert result.steps
    assert result.solutions[0].proof.steps[-1].source == "policy.nl"


def test_provenance_is_preserved_on_proof_steps():
    from inferlingo import KnowledgeBase

    kb = KnowledgeBase.from_text("Known fact.")
    kb.add_fact("Function {fn} is audited", fn="run", provenance=Provenance(source="audit.py", line=9))
    result = asyncio.run(kb.ask("Function {fn} is audited?"))
    assert result.solutions[0].proof.steps[0].provenance.source == "audit.py"


def test_solution_explanation_instantiates_rules_evidence_and_negation():
    rules = RuleSet.from_text(
        """
        # @rule release-ready
        # @description A service is ready only when required evidence is present and it is not frozen.
        {service} is release-ready if {service} has passing tests and not {service} is frozen.
        """,
        source="release_policy.nl",
    )
    fact = Fact(
        "{service} has passing tests",
        {"service": "checkout"},
        provenance=Provenance(source="ci/test-results.json", line=12, kind="ci"),
        source="runtime-facts.nl",
    )
    solution = rules.ask_sync("{service} is release-ready?", facts=[fact]).first()

    assert solution is not None
    explanation = solution.explain()
    assert "checkout is release-ready" in explanation
    assert "via rule: release-ready (release_policy.nl:4)" in explanation
    assert "A service is ready only when required evidence is present and it is not frozen." in explanation
    assert "evidence: checkout has passing tests" in explanation
    assert "source: ci/test-results.json:12" in explanation
    assert "checkout is frozen" in explanation
    assert "no matching positive fact (negation as failure)" in explanation
    assert "{service}" not in explanation
    assert solution.proof.steps[0].rule_name == "release-ready"
    assert solution.proof.render() == solution.proof.explain()
