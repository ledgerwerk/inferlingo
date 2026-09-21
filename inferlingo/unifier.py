"""Exact unification plus the optional pyjev semantic backend."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from .models import Check, Unification
from .terms import (
    Sentence,
    bind,
    candidate_phrases,
    canonicalize_pair,
    match_sentences,
    match_wording,
    normalize,
    restore_variables,
    substitute,
    variables_in,
)


class Unifier(Protocol):
    async def unify(self, goal: str, candidate: str) -> Unification: ...


class ExactUnifier:
    """Only same-wording variable unification; never contacts a model."""

    async def unify_sentences(self, goal: Sentence, candidate: Sentence) -> Unification:
        bindings = match_sentences(goal, candidate)
        if bindings is None:
            return Unification(False, method="exact", confidence=0.0, note="Different wording.")
        return Unification(
            True,
            bindings=bindings,
            method="exact",
            confidence=1.0,
            note="Same wording.",
        )

    async def unify(self, goal: str, candidate: str) -> Unification:
        bindings = match_wording(goal, candidate)
        if bindings is None:
            return Unification(False, method="exact", confidence=0.0, note="Different wording.")
        return Unification(True, bindings=bindings, method="exact", confidence=1.0, note="Same wording.")


AskNoul = Callable[..., Awaitable[Any]]
AskChoice = Callable[..., Awaitable[Any]]


class PyJevUnifier:
    """Semantic sentence unification on top of pyjev's public async primitive API.

    The unifier first tries deterministic wording matching. Differently worded pairs are canonicalized
    and cached, then go through a permissive alignment phase and a stricter verification phase.
    """

    ALIGN_THRESHOLD = 0.30
    MATCH_THRESHOLD = 0.70
    NONE = "__none__"

    SAME_FACT = (
        "Paraphrases, synonyms, and different word order may count as the same fact. A merely related "
        "or implied relation does not, and swapping who does what to whom does not."
    )
    VARIABLES = (
        "Single capital letters such as X, Y and Z, optionally followed by digits, are variables: "
        "placeholders that stand for a person, thing, value, or short phrase."
    )
    RELATIONS = {
        "same": "B states the same fact as A, perhaps reworded with synonyms or a different word order",
        "more_specific": "B is more specific than A and may imply A, but is not the same fact",
        "more_general": "B is more general than A and may be implied by A, but is not the same fact",
        "swapped": "B uses a related relation but the participants play different roles",
        "different": "B states a different fact",
    }

    def __init__(
        self,
        *,
        jev: Any | None = None,
        model: str | None = None,
        align_threshold: float = ALIGN_THRESHOLD,
        match_threshold: float = MATCH_THRESHOLD,
        concurrency: int = 8,
    ) -> None:
        if not 0 <= align_threshold <= 1:
            raise ValueError("align_threshold must be between 0 and 1")
        if not 0 <= match_threshold <= 1:
            raise ValueError("match_threshold must be between 0 and 1")
        if concurrency < 1:
            raise ValueError("concurrency must be at least 1")

        self.model = model
        self.align_threshold = align_threshold
        self.match_threshold = match_threshold
        self._semaphore = asyncio.Semaphore(concurrency)
        self._cache: dict[tuple[str, str], asyncio.Task[Unification]] = {}
        self._owns_jev = jev is None
        if jev is None:
            try:
                from pyjev import AsyncJev
            except ImportError as exc:  # pragma: no cover - optional backend dependency
                raise RuntimeError("Install InferLingo with the Jev extra: pip install inferlingo[jev]") from exc
            jev = AsyncJev(model=model)
        self._jev = jev

    async def __aenter__(self) -> PyJevUnifier:
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        del exc_type, exc, traceback
        await self.close()

    async def close(self) -> None:
        if self._owns_jev:
            await self._jev.close()

    async def _noul(self, question: str, *, state: Any) -> Any:
        async with self._semaphore:
            return await self._jev.noul(question, state=state, model=self.model)

    async def _choice(self, question: str, *, state: Any, choices: dict[str, Any]) -> Any:
        async with self._semaphore:
            return await self._jev.choice(question, state=state, choices=choices, model=self.model)

    async def unify(self, goal: str, candidate: str) -> Unification:
        exact = match_wording(goal, candidate)
        if exact is not None:
            return Unification(True, bindings=exact, method="exact", confidence=1.0, note="Same wording.")

        canonical_goal, canonical_candidate, restore = canonicalize_pair(goal, candidate)
        key = (canonical_goal, canonical_candidate)
        cached = key in self._cache
        task = self._cache.get(key)
        if task is None:
            task = asyncio.create_task(self._semantic_unify(canonical_goal, canonical_candidate))
            self._cache[key] = task
        try:
            result = await task
        except Exception:
            if self._cache.get(key) is task:
                self._cache.pop(key, None)
            raise

        restored_bindings = {
            restore_variables(variable, restore): restore_variables(value, restore)
            for variable, value in result.bindings.items()
        }
        restored_checks = tuple(
            Check(
                question=restore_variables(check.question, restore),
                probability=check.probability,
                passed=check.passed,
            )
            for check in result.checks
        )
        note = restore_variables(result.note, restore) if result.note else None
        return Unification(
            unified=result.unified,
            bindings=restored_bindings,
            method=result.method,
            confidence=result.confidence,
            note=note,
            checks=restored_checks,
            calls=0 if cached else result.calls,
            cached=cached,
        )

    async def _semantic_unify(self, goal: str, candidate: str) -> Unification:
        calls = 0
        checks: list[Check] = []
        state = {"variables": self.VARIABLES, "goal": goal, "candidate": candidate}

        match = await self._noul(
            f"Could the goal and candidate state the same fact once variables are filled in? {self.SAME_FACT}",
            state=state,
        )
        calls += 1
        p_match = float(match.value)
        checks.append(
            Check(
                question=f'Could "{goal}" and "{candidate}" state the same fact?',
                probability=p_match,
                passed=p_match >= self.align_threshold,
            )
        )
        if p_match < self.align_threshold:
            return Unification(
                False,
                method="jev",
                confidence=p_match,
                note="Alignment rejected the pair before variable binding.",
                checks=tuple(checks),
                calls=calls,
            )

        bindings: dict[str, str] = {}
        slots: list[tuple[str, str, list[str]]] = []
        for variable in variables_in(goal):
            slots.append((variable, "goal", candidate_phrases(candidate)))
        for variable in variables_in(candidate):
            slots.append((variable, "candidate", candidate_phrases(goal)))

        async def choose_binding(variable: str, side: str, phrases: list[str]):
            if not phrases:
                return variable, None, 0
            labels = {f"p{index}": phrase for index, phrase in enumerate(phrases)}
            criteria: dict[str, Any] = {label: phrase for label, phrase in labels.items()}
            criteria[self.NONE] = "None of these phrases is the value of the variable"
            result = await self._choice(
                (
                    f"The variable {variable} appears in the {side}. "
                    "Which offered phrase from the other sentence does it stand for?"
                ),
                state=state,
                choices=criteria,
            )
            selected = None if result.value == self.NONE else labels.get(result.value)
            return variable, selected, 1

        if slots:
            picks = await asyncio.gather(*(choose_binding(*slot) for slot in slots))
            for variable, selected, used_calls in picks:
                calls += used_calls
                if selected is None:
                    continue
                if not bind(variable, selected, bindings):
                    return Unification(
                        False,
                        method="jev",
                        confidence=0.0,
                        note=f'Binding {variable} to "{selected}" conflicts with another binding.',
                        checks=tuple(checks),
                        calls=calls,
                    )

        filled_goal = substitute(goal, bindings)
        filled_candidate = substitute(candidate, bindings)
        if normalize(filled_goal) == normalize(filled_candidate):
            return Unification(
                True,
                bindings=bindings,
                method="jev",
                confidence=1.0,
                note="With the variables filled in, the wording is identical.",
                checks=tuple(checks),
                calls=calls,
            )

        verify_state = {
            "variables": self.VARIABLES,
            "a": filled_goal,
            "b": filled_candidate,
        }
        relation_task = self._choice(
            "How does statement B relate to statement A?",
            state=verify_state,
            choices=self.RELATIONS,
        )
        participants_task = self._noul(
            (
                "After filling variables, do statements A and B refer to exactly the same "
                "people and things? Different names are different individuals."
            ),
            state=verify_state,
        )
        relation, participants = await asyncio.gather(relation_task, participants_task)
        calls += 2

        p_same = float(relation.probabilities.get("same", 0.0))
        p_participants = float(participants.value)
        checks.extend(
            [
                Check(
                    question=f'Does "{filled_candidate}" state the same fact as "{filled_goal}"?',
                    probability=p_same,
                    passed=p_same >= self.match_threshold,
                ),
                Check(
                    question="Are the statements about the same people and things?",
                    probability=p_participants,
                    passed=p_participants >= self.match_threshold,
                ),
            ]
        )
        confidence = min(p_same, p_participants)
        unified = p_same >= self.match_threshold and p_participants >= self.match_threshold
        if unified:
            note = "Verified as the same fact about the same participants."
        elif p_participants < self.match_threshold:
            note = "Verification says the statements concern different participants."
        else:
            relation_name = getattr(relation, "value", "different")
            note = f"Verification classified the semantic relation as {relation_name!r}, not the same fact."

        return Unification(
            unified,
            bindings=bindings if unified else {},
            method="jev",
            confidence=confidence,
            note=note,
            checks=tuple(checks),
            calls=calls,
        )
