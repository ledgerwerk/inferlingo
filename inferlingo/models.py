"""Public data models used by the parser, resolver, and unifiers."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from .terms import Atom, Variable, render_tokens, sentence_tokens, strip_sentence, substitute


@dataclass(frozen=True, slots=True)
class Provenance:
    """Application-owned evidence attached to a fact or derived clause."""

    source: str | None = None
    line: int | None = None
    kind: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Fact:
    """A structured ground fact supplied by the application."""

    template: str
    values: Mapping[str, object] = field(default_factory=dict)
    provenance: Provenance | None = None
    source: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", MappingProxyType(dict(self.values)))

    def render(self) -> str:
        """Render the fact template with values safely quoted as opaque atoms."""
        tokens = sentence_tokens(self.template)
        substitutions: dict[Variable, tuple[Atom, ...]] = {}
        for token in tokens:
            if isinstance(token, Variable):
                if token.name not in self.values:
                    raise ValueError(f"Missing value for fact variable {token.name!r}")
                substitutions[token] = (Atom(str(self.values[token.name]), quoted=True),)
        rendered = render_tokens(
            (replacement for token in tokens for replacement in substitutions.get(token, (token,))),
            preserve_quotes=True,
        )
        return strip_sentence(rendered)


@dataclass(frozen=True, slots=True)
class Literal:
    """A sentence condition, optionally evaluated as negation-as-failure."""

    sentence: str
    negated: bool = False


@dataclass(frozen=True, slots=True)
class Clause:
    """A rule head with body conditions, source provenance, and optional identity."""

    head: str
    body: tuple[Literal, ...] = ()
    source: str = ""
    line: int = 0
    provenance: Provenance | None = None
    name: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

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
    rule_name: str | None = None
    rule_description: str | None = None
    is_fact: bool = False


@dataclass(frozen=True, slots=True)
class Proof:
    """A branch-local sequence of proof steps for one solution."""

    steps: tuple[ProofStep, ...] = ()

    def render(self) -> str:
        """Render this proof as an explainable tree (compatibility entry point)."""
        return self.explain()

    def explain(self, bindings: Mapping[str, str] | None = None) -> str:
        """Render rule applications, evidence provenance, and negation-as-failure details."""
        variable_bindings = bindings or {}
        lines: list[str] = []
        for step in self.steps:
            indent = "  " * step.depth
            goal = substitute(step.goal, variable_bindings) if variable_bindings else step.goal
            if step.is_fact and step.provenance is not None:
                location_source = step.provenance.source or step.source
                location_line = step.provenance.line if step.provenance.line is not None else step.line
            else:
                location_source = step.source or (step.provenance.source if step.provenance else None)
                location_line = step.line or (step.provenance.line if step.provenance else None)
            location = location_source or ""
            if location_line is not None:
                location += f":{location_line}"
            if step.kind == "negation":
                lines.append(f"{indent}{goal}")
                if step.note and "Positive goal was proved" in step.note:
                    lines.append(f"{indent}  negation failed: the positive goal was proved")
                else:
                    lines.append(f"{indent}  no matching positive fact (negation as failure)")
            elif step.kind == "success" and step.is_fact:
                lines.append(f"{indent}evidence: {goal}")
                if location:
                    lines.append(f"{indent}  source: {location}")
            elif step.kind == "success":
                lines.append(f"{indent}{goal}")
                rule = step.rule_name or step.clause or "unnamed rule"
                suffix = f" ({location})" if location else ""
                lines.append(f"{indent}  via rule: {rule}{suffix}")
                if step.rule_description:
                    lines.append(f"{indent}    {step.rule_description}")
            elif step.kind == "failure":
                lines.append(f"{indent}not proved: {goal}")
                if step.note:
                    lines.append(f"{indent}  {step.note}")
            elif step.kind == "cutoff":
                lines.append(f"{indent}search stopped: {goal}")
                if step.note:
                    lines.append(f"{indent}  {step.note}")
            else:
                lines.append(f"{indent}{goal}")
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

    def explain(self) -> str:
        """Render this solution's proof with its final query bindings applied."""
        return self.proof.explain(self.bindings)


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

    @property
    def matched(self) -> bool:
        """Whether the query produced at least one solution."""
        return bool(self.solutions)

    def first(self) -> Solution | None:
        """Return the first solution, if any."""
        return self.solutions[0] if self.solutions else None

    def values(self, variable: str) -> tuple[str, ...]:
        """Return values bound to one query variable in solution order."""
        return tuple(solution.bindings[variable] for solution in self.solutions if variable in solution.bindings)
