import pytest

from inferlingo import ParseError, parse_program, parse_query


def test_parses_fact_and_rule_forms():
    program = parse_program(
        """
        Tweety is a canary.
        If X is a canary then X is a bird.
        X can fly if X is a bird.
        """
    )
    assert len(program.clauses) == 3
    assert program.clauses[0].is_fact
    assert program.clauses[1].head == "X is a bird"
    assert program.clauses[2].body[0].sentence == "X is a bird"


def test_or_creates_rule_alternatives_and_not_is_literal_flag():
    program = parse_program("X may enter if X has a badge or X is escorted.")
    assert len(program.clauses) == 2
    query = parse_query("X is known and not X is blocked?")
    assert query.alternatives[0][1].negated is True


def test_rule_head_cannot_be_negated():
    with pytest.raises(ParseError):
        parse_program("not X is safe if X is blocked.")
