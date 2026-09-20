from __future__ import annotations

import asyncio
from dataclasses import dataclass

from inferlingo.unifier import PyJevUnifier


@dataclass
class FakeNoul:
    value: float


@dataclass
class FakeChoice:
    value: str
    probabilities: dict[str, float]
    confidence: float = 0.99


class FakeJev:
    def __init__(self):
        self.calls = []

    async def noul(self, question, *, state, model=None):
        self.calls.append(("noul", question, state, model))
        if "Could the goal" in question:
            return FakeNoul(0.95)
        return FakeNoul(0.98)

    async def choice(self, question, *, state, choices, model=None):
        self.calls.append(("choice", question, state, model))
        if "Which offered phrase" in question:
            label = next(label for label, phrase in choices.items() if phrase == "Lisa")
            return FakeChoice(label, {label: 0.97})
        return FakeChoice(
            "same",
            {"same": 0.96, "more_specific": 0.02, "more_general": 0.01, "swapped": 0.0, "different": 0.01},
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
        assert second.unified
        assert second.bindings == {"Y1": "Lisa"}
        assert second.cached is True
        assert second.calls == 0
        assert len(fake.calls) == 4

    asyncio.run(scenario())
