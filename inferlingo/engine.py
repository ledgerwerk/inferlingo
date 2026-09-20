"""A compact asynchronous SLD-style resolver over natural-language clauses."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from .models import Clause, Literal, Program, ProofStep, Query, RunResult, Solution
from .terms import freshen, merge_substitutions, substitute, variables_in
from .unifier import Unifier


@dataclass(slots=True)
class _RunState:
    steps: list[ProofStep]
    step_count: int = 0
    truncated: bool = False
    unification_calls: int = 0
    cached_unifications: int = 0
    fresh_counter: int = 0


class NLEngine:
    def __init__(self, program: Program, unifier: Unifier) -> None:
        self.program = program
        self.unifier = unifier

    async def run(
        self,
        query: Query,
        *,
        max_depth: int = 25,
        max_steps: int = 2000,
        max_solutions: int = 50,
    ) -> RunResult:
        if max_depth < 1 or max_steps < 1 or max_solutions < 1:
            raise ValueError("max_depth, max_steps, and max_solutions must be positive")

        query_variables: list[str] = []
        for alternative in query.alternatives:
            for literal in alternative:
                for variable in variables_in(literal.sentence):
                    if variable not in query_variables:
                        query_variables.append(variable)

        state = _RunState(steps=[])
        raw_solutions: list[dict[str, str]] = []
        for alternative in query.alternatives:
            async for substitution in self._solve(
                list(alternative),
                {},
                depth=0,
                state=state,
                max_depth=max_depth,
                max_steps=max_steps,
            ):
                raw_solutions.append(substitution)
                if len(raw_solutions) >= max_solutions or state.truncated:
                    break
            if len(raw_solutions) >= max_solutions or state.truncated:
                break

        solutions: list[Solution] = []
        seen: set[tuple[tuple[str, str], ...]] = set()
        for substitution in raw_solutions:
            bindings = {variable: substitute(variable, substitution) for variable in query_variables}
            key = tuple(sorted(bindings.items()))
            if key in seen:
                continue
            seen.add(key)
            answer_parts = []
            for literal in query.alternatives[0]:
                sentence = substitute(literal.sentence, substitution)
                answer_parts.append(("not " if literal.negated else "") + sentence)
            solutions.append(Solution(bindings=bindings, answer=" and ".join(answer_parts)))

        return RunResult(
            solutions=tuple(solutions),
            steps=tuple(state.steps),
            truncated=state.truncated,
            unification_calls=state.unification_calls,
            cached_unifications=state.cached_unifications,
        )

    async def _solve(
        self,
        goals: list[Literal],
        substitution: dict[str, str],
        *,
        depth: int,
        state: _RunState,
        max_depth: int,
        max_steps: int,
    ):
        if state.truncated:
            return
        if not goals:
            yield substitution
            return
        if depth >= max_depth:
            state.steps.append(
                ProofStep(
                    kind="cutoff",
                    depth=depth,
                    goal=substitute(goals[0].sentence, substitution),
                    note=f"Maximum proof depth {max_depth} reached.",
                )
            )
            return

        current, *rest = goals
        current_sentence = substitute(current.sentence, substitution)
        if current.negated:
            proved = False
            async for _ in self._solve(
                [Literal(current_sentence, negated=False)],
                dict(substitution),
                depth=depth + 1,
                state=state,
                max_depth=max_depth,
                max_steps=max_steps,
            ):
                proved = True
                break
            state.steps.append(
                ProofStep(
                    kind="negation",
                    depth=depth,
                    goal=current_sentence,
                    note="Positive goal was proved, so negation fails." if proved else "No positive proof found; negation holds.",
                )
            )
            if not proved:
                async for result in self._solve(
                    rest,
                    substitution,
                    depth=depth + 1,
                    state=state,
                    max_depth=max_depth,
                    max_steps=max_steps,
                ):
                    yield result
            return

        clauses = [self._freshen_clause(clause, state) for clause in self.program.clauses]
        unifications = await asyncio.gather(
            *(self.unifier.unify(current_sentence, clause.head) for clause in clauses)
        )

        for clause, unification in zip(clauses, unifications, strict=True):
            if state.step_count >= max_steps:
                state.truncated = True
                state.steps.append(
                    ProofStep(
                        kind="cutoff",
                        depth=depth,
                        goal=current_sentence,
                        note=f"Maximum proof steps {max_steps} reached.",
                    )
                )
                return

            state.step_count += 1
            state.unification_calls += unification.calls
            state.cached_unifications += int(unification.cached)
            merged = merge_substitutions(substitution, unification.bindings) if unification.unified else None
            success = merged is not None
            state.steps.append(
                ProofStep(
                    kind="success" if success else "failure",
                    depth=depth,
                    goal=current_sentence,
                    clause=clause.head,
                    method=unification.method,
                    confidence=unification.confidence,
                    bindings=dict(unification.bindings),
                    note=unification.note if success or not unification.unified else "Bindings conflict with the current proof branch.",
                )
            )
            if not success:
                continue

            next_goals = [
                Literal(substitute(literal.sentence, merged), literal.negated)
                for literal in [*clause.body, *rest]
            ]
            async for result in self._solve(
                next_goals,
                merged,
                depth=depth + 1,
                state=state,
                max_depth=max_depth,
                max_steps=max_steps,
            ):
                yield result

    @staticmethod
    def _freshen_clause(clause: Clause, state: _RunState) -> Clause:
        mapping: dict[str, str] = {}

        def next_id() -> int:
            state.fresh_counter += 1
            return state.fresh_counter

        head = freshen(clause.head, mapping, next_id)
        body = tuple(
            Literal(freshen(literal.sentence, mapping, next_id), literal.negated)
            for literal in clause.body
        )
        return Clause(head=head, body=body, source=clause.source, line=clause.line)
