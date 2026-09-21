from __future__ import annotations

import asyncio

from inferlingo import ExactUnifier, NLEngine, Unification, parse_program, parse_query


def run(coro):
    return asyncio.run(coro)


def test_exact_rule_chain_returns_binding():
    program = parse_program(
        """
        Tweety is a canary.
        If X is a canary then X is a bird.
        X can fly if X is a bird.
        """
    )
    result = run(NLEngine(program, ExactUnifier()).run(parse_query("X can fly?")))
    assert [solution.bindings for solution in result.solutions] == [{"X": "Tweety"}]
    assert result.unification_calls == 0


def test_ground_query_returns_proof_or_no_proof():
    program = parse_program("Alice is known.")
    yes = run(NLEngine(program, ExactUnifier()).run(parse_query("Alice is known?")))
    no = run(NLEngine(program, ExactUnifier()).run(parse_query("Bob is known?")))
    assert len(yes.solutions) == 1
    assert no.solutions == ()


def test_negation_as_failure():
    program = parse_program(
        """
        Alice is known.
        Alice has a badge.
        Mallory is known.
        Mallory is blocked.
        X is trusted if X is known and not X is blocked.
        """
    )
    result = run(NLEngine(program, ExactUnifier()).run(parse_query("X is trusted?")))
    assert [solution.bindings for solution in result.solutions] == [{"X": "Alice"}]


class DadParaphraseUnifier(ExactUnifier):
    async def unify(self, goal: str, candidate: str) -> Unification:
        exact = await super().unify(goal, candidate)
        if exact.unified:
            return exact
        if goal == "Homer is the father of Lisa" and candidate == "Lisa's dad is Homer":
            return Unification(True, method="fake-jev", confidence=0.97, calls=2, note="test paraphrase")
        return exact


def test_engine_is_independent_of_jev_transport():
    program = parse_program(
        """
        Lisa's dad is Homer.
        If X is the father of Y then X is a parent of Y.
        """
    )
    result = run(NLEngine(program, DadParaphraseUnifier()).run(parse_query("Homer is a parent of Lisa?")))
    assert len(result.solutions) == 1
    assert result.unification_calls == 2


def test_rule_variable_scope_does_not_capture_query_variable_name():
    program = parse_program(
        """
        Homer is a parent of Lisa.
        Lisa is a parent of Bart.
        Maggie is female.
        X is a grandparent of Z if X is a parent of Y and Y is a parent of Z.
        """
    )
    result = run(NLEngine(program, ExactUnifier()).run(parse_query("Homer is a grandparent of Bart and Y3 is female?")))
    assert [solution.bindings for solution in result.solutions] == [{"Y3": "Maggie"}]


def test_negation_order_does_not_change_safe_result():
    for body in (
        "not {person} is blocked and {person} is a user",
        "{person} is a user and not {person} is blocked",
    ):
        program = parse_program(
            f"""
            Alice is a user.
            Bob is a user.
            Bob is blocked.
            {{person}} is allowed if {body}.
            """
        )
        result = run(NLEngine(program, ExactUnifier()).run(parse_query("{person} is allowed?")))
        assert [solution.bindings for solution in result.solutions] == [{"person": "Alice"}]
