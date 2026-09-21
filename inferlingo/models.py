"""Public data models used by the parser, resolver, and unifiers."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class Provenance:
    """Application-owned evidence attached to a fact or derived clause."""

    source: str | None = None
    line: int | None = None
    kind: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Literal:
    """A sentence condition, optionally evaluated as negation-as-failure."""
    sentence: str
    negated: bool = False


@dataclass(frozen=True, slots=True)
class Clause:
    """A rule head with body conditions and optional source provenance."""
    head: str
    body: tuple[Literal, ...] = ()
    source: str = ""
    line: int = 0
    provenance: Provenance | None = None

    @property
    def is_fact(self) -> bool:
        return not self.body


@dataclass(frozen=True, slots=True)
class Program:
    """An immutable collection of parsed clauses."""
    clauses: tuple[Clause, ...]


@dataclass(frozen=True, slots=True)
class Query:
    """A parsed query containing alternative literal branches."""
    alternatives: tuple[tuple[Literal, ...], ...]
    text: str


@dataclass(frozen=True, slots=True)
class Check:
    """One semantic-backend check with its confidence and pass result."""
    question: str
    probability: float
    passed: bool


@dataclass(frozen=True, slots=True)
class BackendUsage:
    """Counters and identifiers describing backend work for a unification."""
    requests: int = 0
    questions: int = 0
    cached: bool = False
    request_ids: tuple[str, ...] = ()
    model: str | None = None
    usage: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Unification:
    """The result of exact or semantic unification, including diagnostics."""
    unified: bool
    bindings: dict[str, str] = field(default_factory=dict)
    method: str = "exact"
    confidence: float = 1.0
    note: str | None = None
    checks: tuple[Check, ...] = ()
    calls: int = 0
    cached: bool = False
    usage: BackendUsage = field(default_factory=BackendUsage)


@dataclass(frozen=True, slots=True)
class ProofStep:
    """One resolver attempt or result in a proof or global trace."""
    kind: str
    depth: int
    goal: str
    clause: str | None = None
    method: str | None = None
    confidence: float | None = None
    bindings: dict[str, str] = field(default_factory=dict)
    note: str | None = None
    source: str | None = None
    line: int | None = None
    provenance: Provenance | None = None
    checks: tuple[Check, ...] = ()
    request_ids: tuple[str, ...] = ()
    usage: BackendUsage | None = None


@dataclass(frozen=True, slots=True)
class Proof:
    """A branch-local sequence of proof steps for one solution."""
    steps: tuple[ProofStep, ...] = ()

    def render(self) -> str:
        """Render proof goals, clauses, and available provenance as readable lines."""
        lines: list[str] = []
        for step in self.steps:
            indent = "  " * step.depth
            line = f"{indent}{step.goal}"
            if step.kind == "success" and step.clause:
                line += f" because {step.clause}"
            elif step.kind == "negation":
                line += " (negation holds)"
            lines.append(line)
            if step.provenance and (step.provenance.source or step.provenance.line):
                location = step.provenance.source or "<memory>"
                if step.provenance.line is not None:
                    location += f":{step.provenance.line}"
                lines.append(f"{indent}  source: {location}")
        return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class RunStats:
    """Aggregate resolver and backend counters for one run."""
    backend_requests: int = 0
    semantic_questions: int = 0
    cache_hits: int = 0
    clauses_considered: int = 0
    proof_steps: int = 0
    exact_matches: int = 0
    semantic_matches: int = 0


@dataclass(frozen=True, slots=True)
class Solution:
    """One query answer with bindings, rendered text, and its proof."""
    bindings: dict[str, str]
    answer: str
    proof: Proof = field(default_factory=Proof)

    @property
    def semantic_confidences(self) -> tuple[float, ...]:
        return tuple(
            step.confidence
            for step in self.proof.steps
            if step.method not in (None, "exact") and step.confidence is not None
        )

    @property
    def minimum_semantic_confidence(self) -> float | None:
        values = self.semantic_confidences
        return min(values) if values else None


@dataclass(frozen=True, slots=True)
class RunResult:
    """The complete bounded result of resolving a query."""
    solutions: tuple[Solution, ...]
    steps: tuple[ProofStep, ...]
    truncated: bool
    stats: RunStats = field(default_factory=RunStats)

    @property
    def unification_calls(self) -> int:
        return self.stats.backend_requests

    @property
    def cached_unifications(self) -> int:
        return self.stats.cache_hits
