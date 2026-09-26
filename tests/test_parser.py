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


def test_quoted_atoms_preserve_keywords_and_escaped_content():
    program = parse_program(
        r"""
        Message "fail if unavailable and not ready" is stored.
        Path "C:\\tmp\\a\\\"b.txt" exists.
        """
    )
    assert [clause.head for clause in program.clauses] == [
        'Message "fail if unavailable and not ready" is stored',
        r'Path "C:\\tmp\\a\\\"b.txt" exists',
    ]


def test_unmatched_quote_is_a_parse_error():
    with pytest.raises(ParseError):
        parse_program('Message "unterminated is stored.')


def test_rule_comment_directives_attach_to_next_rule_after_facts():
    program = parse_program(
        """
        # @rule release-ready
        # @description A service has all required release evidence.
        checkout has passing tests.
        {service} is release-ready if {service} has passing tests.
        """,
        source="release_policy.nl",
    )

    assert program.clauses[0].name is None
    rule = program.clauses[1]
    assert rule.name == "release-ready"
    assert rule.metadata == {"description": "A service has all required release evidence."}
    assert rule.source == "release_policy.nl"
    with pytest.raises(TypeError):
        rule.metadata["description"] = "changed"  # type: ignore[index]


def test_rule_directives_reject_duplicates_invalid_names_and_dangling_comments():
    with pytest.raises(ParseError, match="duplicate @rule directive"):
        parse_program("# @rule first\n# @rule second\n{person} is trusted if {person} is known.")
    with pytest.raises(ParseError, match="@rule names must start with a letter"):
        parse_program("# @rule not a valid id\n{person} is trusted if {person} is known.")
    with pytest.raises(ParseError, match="@rule directive was not followed by a rule"):
        parse_program("# @rule orphan\nAlice is known.")
