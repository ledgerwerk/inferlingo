"""High-level embedding API for InferLingo."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from .engine import NLEngine
from .models import Clause, Fact, Program, Provenance, RunResult
from .parser import parse_program, parse_query
from .unifier import ExactUnifier, Unifier


def _fact_clause(fact: Fact, *, strict: bool) -> Clause:
    parsed = parse_program(f"{fact.render()}.", source=fact.source or "<memory>", strict=strict)
    if len(parsed.clauses) != 1 or not parsed.clauses[0].is_fact:
        raise ValueError("add_fact requires a fact template")
    clause = parsed.clauses[0]
    return Clause(
        head=clause.head,
        source=clause.source,
        line=clause.line,
        provenance=fact.provenance,
    )


def _ask_sync(
    ask: Callable[..., Awaitable[RunResult]],
    query: str,
    kwargs: dict[str, object],
    *,
    api_name: str,
) -> RunResult:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(ask(query, **kwargs))
    raise RuntimeError(f"{api_name} cannot be called from a running event loop; use await ask()")


class KnowledgeBase:
    """Mutable collection of readable facts and rules with an async query API."""

    def __init__(self, *, unifier: Unifier | None = None, strict: bool = True) -> None:
        self.unifier = unifier or ExactUnifier()
        self.strict = strict
        self._clauses: list[Clause] = []

    @classmethod
    def from_text(
        cls,
        text: str,
        *,
        source: str = "<memory>",
        unifier: Unifier | None = None,
        strict: bool = True,
    ) -> KnowledgeBase:
        """Create a knowledge base by parsing NL text in strict mode by default."""
        knowledge_base = cls(unifier=unifier, strict=strict)
        knowledge_base.add_text(text, source=source)
        return knowledge_base

    @classmethod
    def from_file(
        cls,
        path: str | Path,
        *,
        unifier: Unifier | None = None,
        strict: bool = True,
    ) -> KnowledgeBase:
        """Create a knowledge base from a UTF-8 file path."""
        file_path = Path(path)
        return cls.from_text(
            file_path.read_text(encoding="utf-8"),
            source=str(file_path),
            unifier=unifier,
            strict=strict,
        )

    @property
    def program(self) -> Program:
        """Return the current clauses as an immutable `Program` view."""
        return Program(tuple(self._clauses))

    def add_text(self, text: str, *, source: str = "<memory>") -> None:
        """Parse and append facts or rules, using the knowledge base strictness setting."""
        parsed = parse_program(text, source=source, strict=self.strict)
        self._clauses.extend(parsed.clauses)

    def add_fact(
        self,
        template: str,
        /,
        *,
        provenance: Provenance | None = None,
        source: str | None = None,
        **values: object,
    ) -> None:
        """Add one ground fact, quoting each injected value as an opaque atom."""
        self._clauses.append(_fact_clause(Fact(template, values, provenance, source), strict=self.strict))

    async def ask(
        self,
        query: str,
        *,
        max_depth: int = 25,
        max_steps: int = 2000,
        max_solutions: int = 50,
    ) -> RunResult:
        """Asynchronously resolve a query and return its bounded run result."""
        return await NLEngine(self.program, self.unifier).run(
            parse_query(query),
            max_depth=max_depth,
            max_steps=max_steps,
            max_solutions=max_solutions,
        )

    def ask_sync(self, query: str, **limits: int) -> RunResult:
        """Resolve a query from synchronous code outside an active event loop."""
        return _ask_sync(self.ask, query, dict(limits), api_name="ask_sync()")

    def __len__(self) -> int:
        return len(self._clauses)


@dataclass(frozen=True, slots=True, init=False)
class RuleSet:
    """Immutable parsed rules reusable across isolated evaluation sessions."""

    program: Program
    unifier: Unifier
    strict: bool

    def __init__(
        self,
        program: Program,
        *,
        unifier: Unifier | None = None,
        strict: bool = True,
    ) -> None:
        object.__setattr__(self, "program", program)
        object.__setattr__(self, "unifier", unifier or ExactUnifier())
        object.__setattr__(self, "strict", strict)

    @classmethod
    def from_text(
        cls,
        text: str,
        *,
        source: str = "<memory>",
        unifier: Unifier | None = None,
        strict: bool = True,
    ) -> RuleSet:
        """Parse one immutable rule set from NL text."""
        return cls(parse_program(text, source=source, strict=strict), unifier=unifier, strict=strict)

    @classmethod
    def from_file(
        cls,
        path: str | Path,
        *,
        unifier: Unifier | None = None,
        strict: bool = True,
    ) -> RuleSet:
        """Load an immutable rule set from one UTF-8 file."""
        file_path = Path(path)
        return cls.from_text(
            file_path.read_text(encoding="utf-8"),
            source=str(file_path),
            unifier=unifier,
            strict=strict,
        )

    @classmethod
    def from_files(
        cls,
        *paths: str | Path | Iterable[str | Path],
        unifier: Unifier | None = None,
        strict: bool = True,
    ) -> RuleSet:
        """Compose rules from multiple files, preserving each clause's source path."""
        file_paths: list[Path] = []
        for entry in paths:
            if isinstance(entry, (str, Path)):
                file_paths.append(Path(entry))
            else:
                file_paths.extend(Path(path) for path in entry)
        if not file_paths:
            raise ValueError("from_files requires at least one rule file")
        clauses: list[Clause] = []
        for file_path in file_paths:
            parsed = parse_program(
                file_path.read_text(encoding="utf-8"),
                source=str(file_path),
                strict=strict,
            )
            clauses.extend(parsed.clauses)
        return cls(Program(tuple(clauses)), unifier=unifier, strict=strict)

    def session(self) -> Session:
        """Create an evaluation session with facts isolated from other sessions."""
        return Session(self)

    async def ask(
        self,
        query: str,
        *,
        facts: Iterable[Fact] = (),
        max_depth: int = 25,
        max_steps: int = 2000,
        max_solutions: int = 50,
    ) -> RunResult:
        """Evaluate a query against fresh runtime facts without retaining them."""
        session = self.session()
        session.add_facts(facts)
        return await session.ask(
            query,
            max_depth=max_depth,
            max_steps=max_steps,
            max_solutions=max_solutions,
        )

    def ask_sync(
        self,
        query: str,
        *,
        facts: Iterable[Fact] = (),
        max_depth: int = 25,
        max_steps: int = 2000,
        max_solutions: int = 50,
    ) -> RunResult:
        """Synchronously evaluate a query outside an active event loop."""
        kwargs: dict[str, object] = {
            "facts": facts,
            "max_depth": max_depth,
            "max_steps": max_steps,
            "max_solutions": max_solutions,
        }
        return _ask_sync(self.ask, query, kwargs, api_name="ask_sync()")


class Session:
    """Runtime facts and queries scoped to one use of an immutable `RuleSet`."""

    __slots__ = ("rules", "_facts")

    def __init__(self, rules: RuleSet) -> None:
        self.rules = rules
        self._facts: list[Clause] = []

    def add_fact(self, fact: Fact) -> None:
        """Add one structured ground fact to this session only."""
        if not isinstance(fact, Fact):
            raise TypeError("Session.add_fact expects a Fact")
        self._facts.append(_fact_clause(fact, strict=self.rules.strict))

    def add_facts(self, facts: Iterable[Fact]) -> None:
        """Add structured facts from an iterable to this session only."""
        for fact in facts:
            self.add_fact(fact)

    @property
    def program(self) -> Program:
        """Return the immutable rules plus this session's runtime facts."""
        return Program((*self.rules.program.clauses, *self._facts))

    async def ask(
        self,
        query: str,
        *,
        max_depth: int = 25,
        max_steps: int = 2000,
        max_solutions: int = 50,
    ) -> RunResult:
        """Asynchronously resolve a query using this session's facts."""
        return await NLEngine(self.program, self.rules.unifier).run(
            parse_query(query),
            max_depth=max_depth,
            max_steps=max_steps,
            max_solutions=max_solutions,
        )

    def ask_sync(
        self,
        query: str,
        *,
        max_depth: int = 25,
        max_steps: int = 2000,
        max_solutions: int = 50,
    ) -> RunResult:
        """Synchronously resolve a query outside an active event loop."""
        kwargs: dict[str, object] = {
            "max_depth": max_depth,
            "max_steps": max_steps,
            "max_solutions": max_solutions,
        }
        return _ask_sync(self.ask, query, kwargs, api_name="ask_sync()")
