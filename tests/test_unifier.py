from __future__ import annotations

import asyncio
from dataclasses import dataclass

from inferlingo import KnowledgeBase
from inferlingo.unifier import PyJevUnifier


@dataclass
class FakeNoul:
    value: float
    model: str
    usage: dict[str, int]
    request_id: str


@dataclass
class FakeChoice:
    value: str
    probabilities: dict[str, float]
    model: str
    usage: dict[str, int]
    request_id: str
    confidence: float = 0.99


class FakeJev:
    def __init__(self):
        self.calls = []

    def _metadata(self):
        return {
            "model": "fake-model",
            "usage": {"input_tokens": 1, "output_tokens": 2, "total_tokens": 3},
            "request_id": f"request-{len(self.calls)}",
        }

    async def noul(self, question, *, state, model=None):
        self.calls.append(("noul", question, state, model))
        if "Could the goal" in question:
            return FakeNoul(0.95, **self._metadata())
        return FakeNoul(0.98, **self._metadata())

    async def choice(self, question, *, state, choices, model=None):
        self.calls.append(("choice", question, state, model))
        if "Which offered phrase" in question:
            label = next(label for label, phrase in choices.items() if phrase == "Lisa")
            return FakeChoice(label, {label: 0.97}, **self._metadata())
        return FakeChoice(
            "same",
            {"same": 0.96, "more_specific": 0.02, "more_general": 0.01, "swapped": 0.0, "different": 0.01},
            **self._metadata(),
        )

    async def close(self):
        raise AssertionError("injected client is caller-owned")


def test_pyjev_unifier_aligns_and_verifies_paraphrase_and_caches_canonical_pair():
    async def scenario():
        fake = FakeJev()
        unifier = PyJevUnifier(jev=fake, concurrency=4)
        first = await unifier.unify("Homer is the father of X", "Lisa's dad is Homer")
        second = await unifier.unify("Homer is the father of Y1", "Lisa's dad is Homer")
        assert first.unified
        assert first.bindings == {"X": "Lisa"}
        assert first.confidence == 0.96
        assert first.calls == 4  # align + binding + relation + participants
        assert first.usage.requests == 4
        assert first.usage.questions == 4
        assert set(first.usage.request_ids) == {"request-1", "request-2", "request-3", "request-4"}
        assert first.usage.model == "fake-model"
        assert first.usage.usage == {"input_tokens": 4, "output_tokens": 8, "total_tokens": 12}
        assert second.unified
        assert second.bindings == {"Y1": "Lisa"}
        assert second.cached is True
        assert second.calls == 0
        assert second.usage.cached is True
        assert len(fake.calls) == 4

    asyncio.run(scenario())


def test_semantic_metadata_is_retained_in_proof_steps():
    async def scenario():
        fake = FakeJev()
        knowledge = KnowledgeBase.from_text(
            "Lisa's dad is Homer.",
            unifier=PyJevUnifier(jev=fake),
        )
        result = await knowledge.ask("Homer is the father of Lisa?")
        solution = result.first()

        assert solution is not None
        step = next(step for step in solution.proof.steps if step.method == "jev")
        assert step.request_ids == ("request-1", "request-2", "request-3")
        assert step.usage is not None
        assert step.usage.requests == 3
        assert step.usage.questions == 3
        assert step.usage.model == "fake-model"
        assert step.usage.usage == {"input_tokens": 3, "output_tokens": 6, "total_tokens": 9}

    asyncio.run(scenario())
