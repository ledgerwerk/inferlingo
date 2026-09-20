from inferlingo.terms import candidate_phrases, match_wording, substitute


def test_exact_wording_binds_single_and_multiword_phrases():
    assert match_wording("X is the father of Y", "Homer is the father of Bart") == {"X": "Homer", "Y": "Bart"}
    assert match_wording("X is the father of Bart", "Homer Simpson is the father of Bart") == {"X": "Homer Simpson"}


def test_fixed_word_mismatch_is_not_semantically_guessed():
    assert match_wording("Homer is the father of Lisa", "Lisa's dad is Homer") is None


def test_substitution_follows_variable_chains():
    assert substitute("X is known", {"X": "Y", "Y": "Alice"}) == "Alice is known"


def test_candidate_phrases_are_contiguous_and_exclude_variables():
    phrases = candidate_phrases("Lisa's dad is X")
    assert "Lisa's" in phrases
    assert "Lisa's dad" in phrases
    assert "X" not in phrases
