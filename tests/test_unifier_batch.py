from __future__ import annotations

import asyncio

from inferlingo import Sentence
from inferlingo.terms import sentence_tokens
from inferlingo.unifier import ExactUnifier, PyJevUnifier


class BundleJev:
    def __init__(self):
        self.calls = []

    async def run(self, *, state, questions, model=None):
        self.calls.append((state, questions, model))
        if any(label.startswith("align:") for label in questions):
            return {label: {"value": 0.95} for label in questions}
        response = {}
        for label in questions:
            if label.startswith("relation:"):
                response[label] = {"value": "same", "probabilities": {"same": 0.96}}
            else:
                response[label] = {"value": 0.98}
        return response


async def sentence(text: str) -> Sentence:
    return Sentence(sentence_tokens(text))


def test_exact_unifier_supports_batch_protocol():
    async def scenario():
        results = await ExactUnifier().unify_many(
            await sentence("Alice is known"),
            [await sentence("Alice is known"), await sentence("Bob is known")],
        )
        assert [result.unified for result in results] == [True, False]

    asyncio.run(scenario())


def test_pyjev_batch_uses_two_requests_and_cache():
    async def scenario():
        fake = BundleJev()
        unifier = PyJevUnifier(jev=fake, semantic_batch_size=8)
        goal = await sentence("Homer is the father of Lisa")
        candidates = [await sentence("Lisa's dad is Homer"), await sentence("Lisa's parent is Homer")]
        first = await unifier.unify_many(goal, candidates)
        second = await unifier.unify_many(goal, candidates)
        assert all(result.unified for result in first)
        assert len(fake.calls) == 2
        assert all(result.cached for result in second)

    asyncio.run(scenario())
