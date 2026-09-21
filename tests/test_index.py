from __future__ import annotations

import asyncio

from inferlingo import ExactUnifier, NLEngine, parse_program, parse_query
from inferlingo.program import ProgramIndex
from inferlingo.terms import sentence_tokens


def test_index_prioritizes_exact_anchors_without_excluding_fallbacks():
    program = parse_program("Alice is known.\nBob is blocked.\n")
    index = ProgramIndex(program.clauses)
    candidates = index.candidates(sentence_tokens("Alice is known"))
    assert candidates[0].head == "Alice is known"
    assert {clause.head for clause in candidates} == {"Alice is known", "Bob is blocked"}


def test_variant_self_recursion_terminates_without_depth_or_step_explosion():
    program = parse_program("{x} is stuck if {x} is stuck.")
    result = asyncio.run(
        NLEngine(program, ExactUnifier()).run(parse_query("Alice is stuck?"), max_depth=50, max_steps=50)
    )
    assert result.solutions == ()
    assert result.truncated is False
    assert any(step.kind == "cutoff" for step in result.steps)
