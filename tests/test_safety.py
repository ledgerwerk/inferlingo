import asyncio

import pytest

from inferlingo import ExactUnifier, NLEngine, ParseError, parse_program, parse_query
from inferlingo.errors import UnsafeNegationError


def test_strict_mode_rejects_non_ground_facts():
    with pytest.raises(ParseError, match="ground"):
        parse_program("{person} is active.")


def test_strict_mode_rejects_head_only_variables():
    with pytest.raises(ParseError, match="head"):
        parse_program("{person} can access production if system is online.")


def test_strict_mode_rejects_negative_only_variables():
    with pytest.raises(ParseError, match="negative"):
        parse_program("{person} is trusted if not {resource} is blocked.")


def test_unbound_query_negation_raises_a_clear_error():
    program = parse_program("Bob is blocked.")
    with pytest.raises(UnsafeNegationError, match="bound"):
        asyncio.run(NLEngine(program, ExactUnifier()).run(parse_query("not X is blocked?")))
