"""A compact asynchronous SLD-style resolver over natural-language clauses."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from .errors import UnsafeNegationError
from .models import Clause, Program, ProofStep, Query, RunResult, Solution, Unification
from .terms import (
    Atom,
    Phrase,
    Sentence,
    Variable,
    render_tokens,
    sentence_tokens,
    substitute_tokens,
    variables_in,
)
from .unifier import ExactUnifier, Unifier


@dataclass(frozen=True, slots=True)
class _Goal:
    sentence: Phrase
    negated: bool = False


@dataclass(frozen=True, slots=True)
class _InternalClause:
    head: Phrase
    body: tuple[_Goal, ...]
    source: str
    line: int


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
        raw_solutions: list[dict[Variable, Phrase]] = []
        for alternative in query.alternatives:
            goals = tuple(_Goal(sentence_tokens(literal.sentence, scope=0), literal.negated) for literal in alternative)
            async for substitution in self._solve(
                list(goals),
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
            bindings = {
                variable: _render_unquoted(substitute_tokens((Variable(variable, 0),), substitution))
                for variable in query_variables
            }
            key = tuple(sorted(bindings.items()))
            if key in seen:
                continue
            seen.add(key)
            answer_parts = []
            for literal in query.alternatives[0]:
                sentence = _render_unquoted(substitute_tokens(sentence_tokens(literal.sentence, scope=0), substitution))
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
        goals: list[_Goal],
        substitution: dict[Variable, Phrase],
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
                    goal=_render_unquoted(substitute_tokens(goals[0].sentence, substitution)),
                    note=f"Maximum proof depth {max_depth} reached.",
                )
            )
            return

        selected_index = _select_goal(goals, substitution)
        current = goals[selected_index]
        rest = goals[:selected_index] + goals[selected_index + 1 :]
        current_tokens = substitute_tokens(current.sentence, substitution)
        current_sentence = _render_unquoted(current_tokens)
        if current.negated:
            proved = False
            async for _ in self._solve(
                [_Goal(current_tokens)],
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
                    note=(
                        "Positive goal was proved, so negation fails."
                        if proved
                        else "No positive proof found; negation holds."
                    ),
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
        for clause in clauses:
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
            unification = await self._unify(current_tokens, clause.head)
            state.unification_calls += unification.calls
            state.cached_unifications += int(unification.cached)
            merged = _merge_internal(substitution, unification.bindings) if unification.unified else None
            success = merged is not None
            state.steps.append(
                ProofStep(
                    kind="success" if success else "failure",
                    depth=depth,
                    goal=current_sentence,
                    clause=_render_unquoted(clause.head),
                    method=unification.method,
                    confidence=unification.confidence,
                    bindings=_display_bindings(unification.bindings),
                    note=(
                        unification.note
                        if success or not unification.unified
                        else "Bindings conflict with the current proof branch."
                    ),
                )
            )
            if not success:
                continue

            next_goals = [
                _Goal(substitute_tokens(goal.sentence, merged), goal.negated) for goal in [*clause.body, *rest]
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

    async def _unify(self, goal: Phrase, candidate: Phrase) -> Unification:
        if type(self.unifier) is ExactUnifier:
            return await self.unifier.unify_sentences(Sentence(goal), Sentence(candidate))

        wire_variables: dict[str, Variable] = {}
        goal_text = _render_wire(goal, wire_variables)
        candidate_text = _render_wire(candidate, wire_variables)
        result = await self.unifier.unify(goal_text, candidate_text)
        bindings: dict[Variable, Phrase] = {}
        for name, value in result.bindings.items():
            variable = wire_variables.get(name, Variable(name))
            bindings[variable] = _wire_phrase(value, wire_variables)
        return Unification(
            unified=result.unified,
            bindings=bindings,
            method=result.method,
            confidence=result.confidence,
            note=result.note,
            checks=result.checks,
            calls=result.calls,
            cached=result.cached,
        )

    @staticmethod
    def _freshen_clause(clause: Clause, state: _RunState) -> _InternalClause:
        state.fresh_counter += 1
        scope = state.fresh_counter
        head = sentence_tokens(clause.head, scope=scope)
        body = tuple(_Goal(sentence_tokens(literal.sentence, scope=scope), literal.negated) for literal in clause.body)
        return _InternalClause(head=head, body=body, source=clause.source, line=clause.line)


def _select_goal(goals: list[_Goal], substitution: Mapping[Variable, Phrase]) -> int:
    positive: list[tuple[int, int]] = []
    bound_negative: list[int] = []
    unbound_negative: list[tuple[int, list[str]]] = []
    for index, goal in enumerate(goals):
        variables = list(dict.fromkeys(token for token in goal.sentence if isinstance(token, Variable)))
        bound = {
            variable
            for variable in variables
            if substitute_tokens((variable,), substitution)
            and all(isinstance(token, Atom) for token in substitute_tokens((variable,), substitution))
        }
        if not goal.negated:
            positive.append((len(bound), index))
        elif len(bound) == len(variables):
            bound_negative.append(index)
        else:
            unbound_negative.append((index, [variable.name for variable in variables if variable not in bound]))
    if positive:
        return max(positive, key=lambda item: (item[0], -item[1]))[1]
    if bound_negative:
        return bound_negative[0]
    if unbound_negative:
        _, variables = unbound_negative[0]
        names = ", ".join(dict.fromkeys(variables))
        raise UnsafeNegationError(
            f"unsafe negation: variable(s) {names} must be bound by a positive goal before negation"
        )
    raise RuntimeError("goal planner received an empty goal list")


def _render_unquoted(tokens: Phrase) -> str:
    return render_tokens(tokens, preserve_quotes=False)


def _display_bindings(bindings: Mapping[Variable, Phrase] | Mapping[str, str]) -> dict[str, str]:
    displayed: dict[str, str] = {}
    for variable, value in bindings.items():
        name = variable.name if isinstance(variable, Variable) else variable
        if isinstance(value, str):
            displayed[name] = value
        else:
            displayed[name] = _render_unquoted(value)
    return displayed


def _merge_internal(base: Mapping[Variable, Phrase], extra: Mapping[Variable, Phrase]) -> dict[Variable, Phrase] | None:
    merged = dict(base)
    for variable, value in extra.items():
        value = substitute_tokens(value, merged)
        existing = merged.get(variable)
        if existing is not None:
            if _render_unquoted(substitute_tokens(existing, merged)).lower() != _render_unquoted(value).lower():
                return None
        else:
            merged[variable] = value
    for variable in list(merged):
        merged[variable] = substitute_tokens(merged[variable], merged)
    return merged


def _render_wire(tokens: Phrase, variables: dict[str, Variable]) -> str:
    rendered: list[str] = []
    for token in tokens:
        if isinstance(token, Variable):
            wire_name = token.name if token.scope == 0 else f"__inferlingo_{token.scope}_{token.name}"
            variables[wire_name] = token
            rendered.append("{" + wire_name + "}")
        elif isinstance(token, Atom):
            rendered.append(token.value)
    return " ".join(rendered)


def _wire_phrase(value: str, variables: Mapping[str, Variable]) -> Phrase:
    result: list[Variable | Atom] = []
    for token in sentence_tokens(value):
        if isinstance(token, Variable):
            result.append(variables.get(token.name, token))
        else:
            result.append(token)
    return tuple(result)
