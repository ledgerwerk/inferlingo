"""A deterministic asynchronous resolver over natural-language clauses."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .errors import UnsafeNegationError
from .models import (
    Clause,
    Proof,
    ProofStep,
    Query,
    RunResult,
    RunStats,
    Solution,
    Unification,
)
from .program import ProgramIndex
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
    provenance: Any = None


@dataclass(slots=True)
class _RunState:
    steps: list[ProofStep]
    step_count: int = 0
    truncated: bool = False
    backend_requests: int = 0
    semantic_questions: int = 0
    cache_hits: int = 0
    clauses_considered: int = 0
    exact_matches: int = 0
    semantic_matches: int = 0
    fresh_counter: int = 0


class NLEngine:
    """Resolve parsed queries against indexed clauses with a pluggable unifier."""

    def __init__(self, program, unifier: Unifier) -> None:
        """Create an engine for a parsed program and unifier."""
        self.program = program
        self.unifier = unifier
        self.index = ProgramIndex(program.clauses)

    async def run(
        self,
        query: Query,
        *,
        max_depth: int = 25,
        max_steps: int = 2000,
        max_solutions: int = 50,
    ) -> RunResult:
        """Run a query with positive depth, step, and solution bounds."""
        if max_depth < 1 or max_steps < 1 or max_solutions < 1:
            raise ValueError("max_depth, max_steps, and max_solutions must be positive")

        query_variables: list[str] = []
        for alternative in query.alternatives:
            for literal in alternative:
                for variable in variables_in(literal.sentence):
                    if variable not in query_variables:
                        query_variables.append(variable)

        state = _RunState(steps=[])
        raw_solutions: list[tuple[dict[Variable, Phrase], Proof, tuple[Any, ...]]] = []
        for alternative in query.alternatives:
            goals = tuple(_Goal(sentence_tokens(literal.sentence, scope=0), literal.negated) for literal in alternative)
            async for substitution, proof in self._solve(
                list(goals),
                {},
                Proof(),
                depth=0,
                ancestors=frozenset(),
                state=state,
                max_depth=max_depth,
                max_steps=max_steps,
            ):
                raw_solutions.append((substitution, proof, alternative))
                if len(raw_solutions) >= max_solutions or state.truncated:
                    break
            if len(raw_solutions) >= max_solutions or state.truncated:
                break

        solutions: list[Solution] = []
        seen: set[tuple[tuple[str, str], ...]] = set()
        for substitution, proof, alternative in raw_solutions:
            bindings = {
                variable: _render_unquoted(substitute_tokens((Variable(variable, 0),), substitution))
                for variable in query_variables
            }
            key = tuple(sorted(bindings.items()))
            if key in seen:
                continue
            seen.add(key)
            answer_parts = []
            for literal in alternative:
                sentence = _render_unquoted(substitute_tokens(sentence_tokens(literal.sentence, scope=0), substitution))
                answer_parts.append(("not " if literal.negated else "") + sentence)
            solutions.append(Solution(bindings=bindings, answer=" and ".join(answer_parts), proof=proof))

        stats = RunStats(
            backend_requests=state.backend_requests,
            semantic_questions=state.semantic_questions,
            cache_hits=state.cache_hits,
            clauses_considered=state.clauses_considered,
            proof_steps=sum(len(solution.proof.steps) for solution in solutions),
            exact_matches=state.exact_matches,
            semantic_matches=state.semantic_matches,
        )
        return RunResult(solutions=tuple(solutions), steps=tuple(state.steps), truncated=state.truncated, stats=stats)

    async def _solve(
        self,
        goals: list[_Goal],
        substitution: dict[Variable, Phrase],
        proof: Proof,
        *,
        depth: int,
        ancestors: frozenset[tuple[bool, tuple[str, ...]]],
        state: _RunState,
        max_depth: int,
        max_steps: int,
    ):
        if state.truncated:
            return
        if not goals:
            yield substitution, proof
            return
        if depth >= max_depth:
            self._trace_cutoff(goals[0], substitution, depth, state, f"Maximum proof depth {max_depth} reached.")
            return

        selected_index = _select_goal(goals, substitution)
        current = goals[selected_index]
        rest = goals[:selected_index] + goals[selected_index + 1 :]
        current_tokens = substitute_tokens(current.sentence, substitution)
        current_sentence = _render_unquoted(current_tokens)

        if current.negated:
            proved = False
            async for _substitution, _proof in self._solve(
                [_Goal(current_tokens)],
                dict(substitution),
                Proof(),
                depth=depth + 1,
                ancestors=ancestors,
                state=state,
                max_depth=max_depth,
                max_steps=max_steps,
            ):
                proved = True
                break
            step = ProofStep(
                kind="negation",
                depth=depth,
                goal=current_sentence,
                note=(
                    "Positive goal was proved, so negation fails."
                    if proved
                    else "No positive proof found; negation holds."
                ),
            )
            state.steps.append(step)
            if not proved:
                async for result in self._solve(
                    rest,
                    substitution,
                    Proof(steps=proof.steps + (step,)),
                    depth=depth + 1,
                    ancestors=ancestors,
                    state=state,
                    max_depth=max_depth,
                    max_steps=max_steps,
                ):
                    yield result
            return

        key = _variant_key(current_tokens, current.negated)
        if key in ancestors:
            self._trace_cutoff(
                current,
                substitution,
                depth,
                state,
                "Variant goal already active; recursive branch stopped.",
            )
            return
        next_ancestors = ancestors | {key}

        candidates = (
            self.index.exact_candidates(current_tokens)
            if type(self.unifier) is ExactUnifier
            else self.index.candidates(current_tokens)
        )
        internals = [self._freshen_clause(clause, state) for clause in candidates]
        unifications = await self._unify_candidates(current_tokens, [internal.head for internal in internals])
        for internal, unification in zip(internals, unifications, strict=True):
            if state.step_count >= max_steps:
                state.truncated = True
                self._trace_cutoff(current, substitution, depth, state, f"Maximum proof steps {max_steps} reached.")
                return
            state.step_count += 1
            state.clauses_considered += 1
            state.backend_requests += unification.usage.requests or unification.calls
            state.semantic_questions += unification.usage.questions
            state.cache_hits += int(unification.cached or unification.usage.cached)
            success = unification.unified and _merge_internal(substitution, unification.bindings) is not None
            if unification.method == "exact":
                state.exact_matches += int(success)
            else:
                state.semantic_matches += int(success)
            step = ProofStep(
                kind="success" if success else "failure",
                depth=depth,
                goal=current_sentence,
                clause=_render_unquoted(internal.head),
                method=unification.method,
                confidence=unification.confidence,
                bindings=_display_bindings(unification.bindings),
                note=(
                    unification.note
                    if success or not unification.unified
                    else "Bindings conflict with the current proof branch."
                ),
                source=internal.source,
                line=internal.line,
                provenance=internal.provenance,
                checks=unification.checks,
                request_ids=unification.usage.request_ids,
                usage=unification.usage,
            )
            state.steps.append(step)
            if not success:
                continue
            merged = _merge_internal(substitution, unification.bindings)
            if merged is None:
                continue
            next_goals = [
                _Goal(substitute_tokens(goal.sentence, merged), goal.negated) for goal in [*internal.body, *rest]
            ]
            async for result in self._solve(
                next_goals,
                merged,
                Proof(steps=proof.steps + (step,)),
                depth=depth + 1,
                ancestors=next_ancestors,
                state=state,
                max_depth=max_depth,
                max_steps=max_steps,
            ):
                yield result

    async def _unify_candidates(self, goal: Phrase, candidates: list[Phrase]) -> tuple[Unification, ...]:
        batch = getattr(self.unifier, "unify_many", None)
        if batch is None or (
            type(self.unifier) is not ExactUnifier and type(self.unifier).unify_many is ExactUnifier.unify_many
        ):
            return tuple(await asyncio.gather(*(self._unify(goal, candidate) for candidate in candidates)))
        if type(self.unifier) is ExactUnifier:
            return tuple(
                await self.unifier.unify_many(Sentence(goal), [Sentence(candidate) for candidate in candidates])
            )
        goal_variables: dict[str, Variable] = {}
        goal_text = _render_wire(goal, goal_variables)
        wire_candidates: list[Sentence] = []
        candidate_variables: list[dict[str, Variable]] = []
        for candidate in candidates:
            variables = dict(goal_variables)
            candidate_text = _render_wire(candidate, variables)
            candidate_variables.append(variables)
            wire_candidates.append(Sentence(sentence_tokens(candidate_text)))
        results = await batch(Sentence(sentence_tokens(goal_text)), wire_candidates)
        converted: list[Unification] = []
        for result, variables in zip(results, candidate_variables, strict=True):
            bindings: dict[Variable, Phrase] = {}
            for name, value in result.bindings.items():
                variable = name if isinstance(name, Variable) else variables.get(name, Variable(name))
                bindings[variable] = value if isinstance(value, tuple) else _wire_phrase(value, variables)
            converted.append(
                Unification(
                    unified=result.unified,
                    bindings=bindings,
                    method=result.method,
                    confidence=result.confidence,
                    note=result.note,
                    checks=result.checks,
                    calls=result.calls,
                    cached=result.cached,
                    usage=result.usage,
                )
            )
        return tuple(converted)

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
            usage=result.usage,
        )

    @staticmethod
    def _freshen_clause(clause: Clause, state: _RunState) -> _InternalClause:
        state.fresh_counter += 1
        scope = state.fresh_counter
        head = sentence_tokens(clause.head, scope=scope)
        body = tuple(_Goal(sentence_tokens(literal.sentence, scope=scope), literal.negated) for literal in clause.body)
        return _InternalClause(head, body, clause.source, clause.line, clause.provenance)

    @staticmethod
    def _trace_cutoff(
        goal: _Goal,
        substitution: Mapping[Variable, Phrase],
        depth: int,
        state: _RunState,
        note: str,
    ) -> None:
        state.steps.append(
            ProofStep(
                kind="cutoff",
                depth=depth,
                goal=_render_unquoted(substitute_tokens(goal.sentence, substitution)),
                note=note,
            )
        )


def _select_goal(goals: list[_Goal], substitution: Mapping[Variable, Phrase]) -> int:
    positive: list[tuple[int, int]] = []
    bound_negative: list[int] = []
    unbound_negative: list[tuple[int, list[str]]] = []
    for index, goal in enumerate(goals):
        variables = list(dict.fromkeys(token for token in goal.sentence if isinstance(token, Variable)))
        bound = {variable for variable in variables if _is_ground(substitute_tokens((variable,), substitution))}
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


def _is_ground(tokens: Phrase) -> bool:
    return bool(tokens) and all(isinstance(token, Atom) for token in tokens)


def _variant_key(tokens: Phrase, negated: bool) -> tuple[bool, tuple[str, ...]]:
    return negated, tuple(f"?{token.name}" if isinstance(token, Variable) else token.value.lower() for token in tokens)


def _render_unquoted(tokens: Phrase) -> str:
    return render_tokens(tokens, preserve_quotes=False)


def _display_bindings(bindings: Mapping[Any, Any]) -> dict[str, str]:
    displayed: dict[str, str] = {}
    for variable, value in bindings.items():
        name = variable.name if isinstance(variable, Variable) else variable
        displayed[name] = value if isinstance(value, str) else _render_unquoted(value)
    return displayed


def _merge_internal(base: Mapping[Variable, Phrase], extra: Mapping[Any, Any]) -> dict[Variable, Phrase] | None:
    merged = dict(base)
    for raw_variable, raw_value in extra.items():
        variable = raw_variable if isinstance(raw_variable, Variable) else Variable(raw_variable)
        value = raw_value if isinstance(raw_value, tuple) else sentence_tokens(str(raw_value))
        if variable.scope == 0 and len(value) == 1 and isinstance(value[0], Variable) and value[0].scope != 0:
            # A query variable matched a fresh rule variable. Keep the
            # query identity and alias the fresh variable back to it.
            alias = value[0]
            if alias not in merged:
                merged[alias] = (variable,)
            continue
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
        else:
            rendered.append(token.value)
    return " ".join(rendered)


def _wire_phrase(value: str, variables: Mapping[str, Variable]) -> Phrase:
    result: list[Variable | Atom] = []
    for token in sentence_tokens(value):
        result.append(variables.get(token.name, token) if isinstance(token, Variable) else token)
    return tuple(result)
