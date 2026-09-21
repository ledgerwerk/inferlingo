"""High-level embedding API for InferLingo."""

from __future__ import annotations

import asyncio
from pathlib import Path

from .engine import NLEngine
from .models import Clause, Program, Provenance, RunResult
from .parser import parse_program, parse_query
from .terms import Atom, Variable, render_tokens, sentence_tokens
from .unifier import ExactUnifier, Unifier


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
        file_path = Path(path)
        return cls.from_text(
            file_path.read_text(encoding="utf-8"),
            source=str(file_path),
            unifier=unifier,
            strict=strict,
        )

    @property
    def program(self) -> Program:
        return Program(tuple(self._clauses))

    def add_text(self, text: str, *, source: str = "<memory>") -> None:
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
        tokens = sentence_tokens(template)
        substitutions: dict[Variable, tuple[Atom, ...]] = {}
        for token in tokens:
            if isinstance(token, Variable):
                if token.name not in values:
                    raise ValueError(f"Missing value for fact variable {token.name!r}")
                substitutions[token] = (Atom(str(values[token.name]), quoted=True),)
        rendered = render_tokens(
            (replacement for token in tokens for replacement in substitutions.get(token, (token,))),
            preserve_quotes=True,
        )
        parsed = parse_program(rendered + ".", source=source or "<memory>", strict=self.strict)
        if len(parsed.clauses) != 1 or not parsed.clauses[0].is_fact:
            raise ValueError("add_fact requires a fact template")
        clause = parsed.clauses[0]
        self._clauses.append(
            Clause(
                head=clause.head,
                source=clause.source,
                line=clause.line,
                provenance=provenance,
            )
        )

    async def ask(
        self,
        query: str,
        *,
        max_depth: int = 25,
        max_steps: int = 2000,
        max_solutions: int = 50,
    ) -> RunResult:
        return await NLEngine(self.program, self.unifier).run(
            parse_query(query),
            max_depth=max_depth,
            max_steps=max_steps,
            max_solutions=max_solutions,
        )

    def ask_sync(self, query: str, **limits: int) -> RunResult:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.ask(query, **limits))
        raise RuntimeError("ask_sync() cannot be called from a running event loop; use await ask()")

    def __len__(self) -> int:
        return len(self._clauses)
