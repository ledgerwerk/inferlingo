"""Exact unification plus the optional pyjev semantic backend."""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from collections.abc import Awaitable, Callable, Sequence
from typing import Any, Protocol

from .models import BackendUsage, Check, Unification
from .terms import (
    Sentence,
    bind,
    candidate_phrases,
    canonicalize_pair,
    match_sentences,
    match_wording,
    normalize,
    render_tokens,
    restore_variables,
    substitute,
    variables_in,
)


class Unifier(Protocol):
    async def unify(self, goal: str, candidate: str) -> Unification: ...


class BatchUnifier(Unifier, Protocol):
    async def unify_many(
        self,
        goal: Sentence,
        candidates: Sequence[Sentence],
    ) -> Sequence[Unification]: ...


class ExactUnifier:
    """Only same-wording variable unification; never contacts a model."""

    async def unify_sentences(self, goal: Sentence, candidate: Sentence) -> Unification:
        """Unify parsed sentences using exact wording and return bindings."""
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
        """Unify two sentence strings without contacting a semantic backend."""
        bindings = match_wording(goal, candidate)
        if bindings is None:
            return Unification(False, method="exact", confidence=0.0, note="Different wording.")
        return Unification(True, bindings=bindings, method="exact", confidence=1.0, note="Same wording.")

    async def unify_many(
        self,
        goal: Sentence,
        candidates: Sequence[Sentence],
    ) -> Sequence[Unification]:
        """Unify one parsed goal against several candidates concurrently."""
        return tuple(await asyncio.gather(*(self.unify_sentences(goal, candidate) for candidate in candidates)))


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
        cache_size: int = 2048,
        semantic_batch_size: int = 32,
    ) -> None:
        """Configure the optional backend, thresholds, concurrency, batch size, and cache."""
        if not 0 <= align_threshold <= 1:
            raise ValueError("align_threshold must be between 0 and 1")
        if not 0 <= match_threshold <= 1:
            raise ValueError("match_threshold must be between 0 and 1")
        if concurrency < 1:
            raise ValueError("concurrency must be at least 1")
        if cache_size < 1:
            raise ValueError("cache_size must be at least 1")
        if semantic_batch_size < 1:
            raise ValueError("semantic_batch_size must be at least 1")

        self.model = model
        self.align_threshold = align_threshold
        self.match_threshold = match_threshold
        self.semantic_batch_size = semantic_batch_size
        self.cache_size = cache_size
        self._semaphore = asyncio.Semaphore(concurrency)
        self._cache: OrderedDict[tuple[Any, ...], asyncio.Task[Unification]] = OrderedDict()
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
        """Unify sentence strings exactly first, then verify semantic equivalence when needed."""
        exact = match_wording(goal, candidate)
        if exact is not None:
            return Unification(True, bindings=exact, method="exact", confidence=1.0, note="Same wording.")

        canonical_goal, canonical_candidate, restore = canonicalize_pair(goal, candidate)
        key = self._cache_key(canonical_goal, canonical_candidate)
        cached = key in self._cache
        task = self._cache.get(key)
        if task is None:
            task = asyncio.create_task(self._semantic_unify(canonical_goal, canonical_candidate))
            self._cache[key] = task
            self._trim_cache()
        else:
            self._cache.move_to_end(key)
        try:
            result = await task
        except Exception:
            if self._cache.get(key) is task:
                self._cache.pop(key, None)
            raise

        return self._restore_result(result, restore, cached)

    async def unify_many(
        self,
        goal: Sentence,
        candidates: Sequence[Sentence],
    ) -> Sequence[Unification]:
        """Batch exact and semantic unification while preserving candidate order."""
        goal_text = render_tokens(goal.tokens)
        candidate_texts = [render_tokens(candidate.tokens) for candidate in candidates]
        results: list[Unification | None] = [None] * len(candidate_texts)
        pending: list[tuple[int, str, str, tuple[Any, ...]]] = []
        for index, candidate_text in enumerate(candidate_texts):
            exact = match_wording(goal_text, candidate_text)
            if exact is not None:
                results[index] = Unification(True, bindings=exact, method="exact", confidence=1.0, note="Same wording.")
                continue
            canonical_goal, canonical_candidate, restore = canonicalize_pair(goal_text, candidate_text)
            key = self._cache_key(canonical_goal, canonical_candidate)
            task = self._cache.get(key)
            if task is not None:
                self._cache.move_to_end(key)
                cached_result = await task
                results[index] = self._restore_result(cached_result, restore, True)
            else:
                pending.append((index, canonical_goal, canonical_candidate, restore))
        for start in range(0, len(pending), self.semantic_batch_size):
            chunk = pending[start : start + self.semantic_batch_size]
            semantic = await self._semantic_unify_many(
                chunk[0][1],
                [item[2] for item in chunk],
            )
            for item, result in zip(chunk, semantic, strict=True):
                index, canonical_goal, canonical_candidate, restore = item
                key = self._cache_key(canonical_goal, canonical_candidate)
                task = asyncio.create_task(_resolved(result))
                self._cache[key] = task
                self._trim_cache()
                results[index] = self._restore_result(result, restore, False)
        return tuple(result for result in results if result is not None)

    def _cache_key(self, goal: str, candidate: str) -> tuple[Any, ...]:
        return ("pyjev-v2", self.model, self.align_threshold, self.match_threshold, goal, candidate)

    def _trim_cache(self) -> None:
        while len(self._cache) > self.cache_size:
            self._cache.popitem(last=False)

    @staticmethod
    def _restore_result(result: Unification, restore: dict[str, str], cached: bool) -> Unification:
        restored_bindings = {
            restore_variables(variable, restore): restore_variables(value, restore)
            for variable, value in result.bindings.items()
        }
        restored_checks = tuple(
            Check(restore_variables(check.question, restore), check.probability, check.passed)
            for check in result.checks
        )
        usage = BackendUsage(
            requests=result.usage.requests,
            questions=result.usage.questions,
            cached=cached,
            request_ids=result.usage.request_ids,
            model=result.usage.model,
            usage=result.usage.usage,
        )
        return Unification(
            unified=result.unified,
            bindings=restored_bindings,
            method=result.method,
            confidence=result.confidence,
            note=restore_variables(result.note, restore) if result.note else None,
            checks=restored_checks,
            calls=0 if cached else result.calls,
            cached=cached,
            usage=usage,
        )

    async def _semantic_unify_many(self, goal: str, candidates: Sequence[str]) -> tuple[Unification, ...]:
        if not hasattr(self._jev, "run"):
            return tuple(await asyncio.gather(*(self._semantic_unify(goal, candidate) for candidate in candidates)))
        try:
            from pyjev.compile import build_choice, build_noul
        except ImportError:  # pragma: no cover - injected clients may not install pyjev
            return tuple(await asyncio.gather(*(self._semantic_unify(goal, candidate) for candidate in candidates)))

        variables = list(dict.fromkeys(variables_in(goal)))
        for candidate in candidates:
            variables.extend(variable for variable in variables_in(candidate) if variable not in variables)
        state = {
            "definition": self.SAME_FACT,
            "variables": self.VARIABLES,
            "goal": goal,
            "candidates": {f"c{i}": c for i, c in enumerate(candidates)},
        }
        phase_a: dict[str, Any] = {}
        binding_labels: dict[str, tuple[int, str]] = {}
        for index, candidate in enumerate(candidates):
            label = f"align:c{index}"
            phase_a[label] = build_noul(f"Could candidate c{index} state the same fact as the goal? {self.SAME_FACT}")
            for variable in variables_in(goal):
                key = f"bind:c{index}:goal:{variable}"
                phrases = candidate_phrases(candidate) + [self.NONE]
                phase_a[key] = build_choice(
                    f"Which phrase in candidate c{index} fills goal variable {variable}?",
                    {str(i): value for i, value in enumerate(phrases)},
                )
                binding_labels[key] = (index, variable)
            for variable in variables_in(candidate):
                key = f"bind:c{index}:candidate:{variable}"
                phrases = candidate_phrases(goal) + [self.NONE]
                phase_a[key] = build_choice(
                    f"Which phrase in the goal fills candidate variable {variable}?",
                    {str(i): value for i, value in enumerate(phrases)},
                )
                binding_labels[key] = (index, variable)
        response_a = await self._run_bundle(state, phase_a)
        survivors: list[tuple[int, dict[str, str], str, str]] = []
        for index, candidate in enumerate(candidates):
            alignment = _result_value(response_a, f"align:c{index}", 0.0)
            if float(alignment) < self.align_threshold:
                continue
            bindings: dict[str, str] = {}
            for label, (candidate_index, variable) in binding_labels.items():
                if candidate_index != index:
                    continue
                selected = _result_value(response_a, label, self.NONE)
                if isinstance(selected, str) and selected != self.NONE:
                    try:
                        side = label.split(":")[2]
                        source = candidate if side == "goal" else goal
                        phrases = candidate_phrases(source)
                        selected = phrases[int(selected)] if selected.isdigit() else selected
                    except (IndexError, ValueError):
                        selected = self.NONE
                if selected != self.NONE and isinstance(selected, str):
                    bindings[variable] = selected
            filled_goal = substitute(
                goal,
                {name: value for name, value in bindings.items() if f"{{{name}}}" in goal},
            )
            filled_candidate = substitute(
                candidate,
                {name: value for name, value in bindings.items() if f"{{{name}}}" in candidate},
            )
            survivors.append((index, bindings, filled_goal, filled_candidate))
        if not survivors:
            usage = BackendUsage(
                requests=1,
                questions=len(phase_a),
                model=self.model,
            )
            return tuple(Unification(False, method="jev", confidence=0.0, calls=1, usage=usage) for _ in candidates)
        phase_b: dict[str, Any] = {}
        for index, _bindings, _filled_goal, _filled_candidate in survivors:
            phase_b[f"relation:c{index}"] = build_choice(
                f"How does candidate c{index} relate to the goal?",
                self.RELATIONS,
            )
            phase_b[f"participants:c{index}"] = build_noul(
                "Do the two statements refer to exactly the same people and things?"
            )
        response_b = await self._run_bundle({"variables": self.VARIABLES}, phase_b)
        output: list[Unification] = [Unification(False, method="jev", confidence=0.0) for _ in candidates]
        for index, bindings, filled_goal, filled_candidate in survivors:
            relation = _result_value(response_b, f"relation:c{index}", "different")
            participants = float(_result_value(response_b, f"participants:c{index}", 0.0))
            p_same = float(_result_probability(response_b, f"relation:c{index}", "same"))
            checks = (
                Check(
                    f'Does "{filled_candidate}" state the same fact as "{filled_goal}"?',
                    p_same,
                    p_same >= self.match_threshold,
                ),
                Check(
                    "Are the statements about the same people and things?",
                    participants,
                    participants >= self.match_threshold,
                ),
            )
            unified = p_same >= self.match_threshold and participants >= self.match_threshold and relation == "same"
            output[index] = Unification(
                unified,
                bindings=bindings if unified else {},
                method="jev",
                confidence=min(p_same, participants),
                note=(
                    "Verified as the same fact about the same participants."
                    if unified
                    else f"Verification classified the relation as {relation!r}."
                ),
                checks=checks,
                calls=2,
                usage=BackendUsage(
                    requests=2,
                    questions=len(phase_a) + len(phase_b),
                    model=self.model,
                ),
            )
        return tuple(output)

    async def _run_bundle(self, state: Any, questions: dict[str, Any]) -> dict[str, Any]:
        async with self._semaphore:
            return await self._jev.run(state=state, questions=questions, model=self.model)

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


async def _resolved(value: Unification) -> Unification:
    return value


def _result_value(results: Any, label: str, default: Any) -> Any:
    value = results.get(label, default) if isinstance(results, dict) else default
    if isinstance(value, dict):
        return value.get("value", default)
    return getattr(value, "value", value)


def _result_probability(results: Any, label: str, choice: str) -> float:
    value = results.get(label) if isinstance(results, dict) else None
    probabilities = value.get("probabilities", {}) if isinstance(value, dict) else getattr(value, "probabilities", {})
    if isinstance(probabilities, dict):
        return float(probabilities.get(choice, 0.0))
    selected = _result_value(results, label, 0.0)
    return float(selected) if isinstance(selected, (int, float)) else 0.0
