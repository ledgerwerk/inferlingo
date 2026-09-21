"""Reusable program indexes for deterministic candidate retrieval."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from .models import Clause
from .terms import Atom, Phrase, sentence_tokens


class ProgramIndex:
    """Index fixed wording anchors without excluding semantic fallback candidates."""

    def __init__(self, clauses: Iterable[Clause]) -> None:
        self.clauses = tuple(clauses)
        self.exact_anchor_index: dict[str, tuple[int, ...]] = {}
        buckets: dict[str, list[int]] = defaultdict(list)
        for index, clause in enumerate(self.clauses):
            anchors = {token.value.lower() for token in _atoms(clause.head)}
            for anchor in anchors:
                buckets[anchor].append(index)
        self.exact_anchor_index = {key: tuple(value) for key, value in buckets.items()}

    def exact_candidates(self, goal: Phrase) -> tuple[Clause, ...]:
        goal_anchors = {token.value.lower() for token in _atoms(goal)}
        if not goal_anchors:
            return self.clauses
        matching: list[tuple[int, Clause]] = []
        for clause in self.clauses:
            clause_anchors = {token.value.lower() for token in _atoms(sentence_tokens(clause.head))}
            overlap = len(goal_anchors & clause_anchors)
            threshold = min(2, len(goal_anchors), len(clause_anchors))
            if overlap >= threshold:
                matching.append((overlap, clause))
        matching.sort(key=lambda item: -item[0])
        return tuple(clause for _score, clause in matching)

    def candidates(self, goal: Phrase) -> tuple[Clause, ...]:
        anchors = {token.value.lower() for token in _atoms(goal)}
        ranked: list[int] = []
        for anchor in sorted(anchors):
            for index in self.exact_anchor_index.get(anchor, ()):
                if index not in ranked:
                    ranked.append(index)
        ranked.extend(index for index in range(len(self.clauses)) if index not in ranked)
        return tuple(self.clauses[index] for index in ranked)


def _atoms(tokens: Iterable[object]) -> tuple[Atom, ...]:
    return tuple(token for token in tokens if isinstance(token, Atom))
