from __future__ import annotations

import asyncio

from inferlingo import ExactUnifier, NLEngine, Provenance, parse_program, parse_query


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
