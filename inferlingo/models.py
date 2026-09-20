"""Small data model used by the parser, resolver, and unifier."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Literal:
    sentence: str
    negated: bool = False


@dataclass(frozen=True, slots=True)
class Clause:
    head: str
    body: tuple[Literal, ...] = ()
    source: str = ""
    line: int = 0

    @property
    def is_fact(self) -> bool:
        return not self.body


@dataclass(frozen=True, slots=True)
class Program:
    clauses: tuple[Clause, ...]


@dataclass(frozen=True, slots=True)
class Query:
    alternatives: tuple[tuple[Literal, ...], ...]
    text: str


@dataclass(frozen=True, slots=True)
class Check:
    question: str
    probability: float
    passed: bool


@dataclass(frozen=True, slots=True)
class Unification:
    unified: bool
    bindings: dict[str, str] = field(default_factory=dict)
    method: str = "exact"
    confidence: float = 1.0
    note: str | None = None
    checks: tuple[Check, ...] = ()
    calls: int = 0
    cached: bool = False


@dataclass(frozen=True, slots=True)
class ProofStep:
    kind: str
    depth: int
    goal: str
    clause: str | None = None
    method: str | None = None
    confidence: float | None = None
    bindings: dict[str, str] = field(default_factory=dict)
    note: str | None = None


@dataclass(frozen=True, slots=True)
class Solution:
    bindings: dict[str, str]
    answer: str


@dataclass(frozen=True, slots=True)
class RunResult:
    solutions: tuple[Solution, ...]
    steps: tuple[ProofStep, ...]
    truncated: bool
    unification_calls: int
    cached_unifications: int
