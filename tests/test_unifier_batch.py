from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from pyjev import AsyncJev

from inferlingo import Sentence
from inferlingo.terms import sentence_tokens
from inferlingo.unifier import ExactUnifier, PyJevUnifier


@dataclass
class FakeUsage:
    input_tokens: int
    output_tokens: int
    total_tokens: int

    def model_dump(self, *, mode: str) -> dict[str, int]:
        del mode
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
        }


@dataclass
class FakeNoulAnswer:
    noul: float

    def model_dump(self, *, mode: str) -> dict[str, float]:
        del mode
        return {"noul": self.noul}


@dataclass
class FakeChoiceAnswer:
    choice: str
    confidence: float
    probabilities: dict[str, float]

    def model_dump(self, *, mode: str) -> dict[str, Any]:
        del mode
        return {
            "choice": self.choice,
            "confidence": self.confidence,
            "probabilities": self.probabilities,
        }


@dataclass
class FakeSystemResponse:
    nouls: dict[str, FakeNoulAnswer]
    choices: dict[str, FakeChoiceAnswer]
    model: str
    usage: FakeUsage
    request_id: str

    def model_dump(self, *, mode: str) -> dict[str, Any]:
        return {
            "nouls": {name: answer.model_dump(mode=mode) for name, answer in self.nouls.items()},
            "choices": {name: answer.model_dump(mode=mode) for name, answer in self.choices.items()},
            "model": self.model,
            "usage": self.usage.model_dump(mode=mode),
            "request_id": self.request_id,
        }


class FakeAsyncTypeSafeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[dict[str, Any], dict[str, Any], str | None]] = []
        self.close_calls = 0

    async def system_one(self, *, state, questions, model=None):
        self.calls.append((state, questions, model))
        request_number = len(self.calls)
        nouls: dict[str, FakeNoulAnswer] = {}
        choices: dict[str, FakeChoiceAnswer] = {}
        for name in questions:
            if name.startswith("relation:"):
                choices[name] = FakeChoiceAnswer(
                    choice="same",
                    confidence=0.96,
                    probabilities={
                        "same": 0.96,
                        "more_specific": 0.02,
                        "more_general": 0.01,
                        "swapped": 0.0,
                        "different": 0.01,
                    },
                )
            elif name.startswith("bind:"):
                choices[name] = FakeChoiceAnswer(
                    choice="0",
                    confidence=0.98,
                    probabilities={"0": 0.98, "__none__": 0.02},
                )
            else:
                nouls[name] = FakeNoulAnswer(0.95 if name.startswith("align:") else 0.98)
        return FakeSystemResponse(
            nouls=nouls,
            choices=choices,
            model="fake-model",
            usage=FakeUsage(
                input_tokens=10 * request_number,
                output_tokens=4 * request_number,
                total_tokens=14 * request_number,
            ),
            request_id=f"request-{request_number}",
        )

    async def aclose(self) -> None:
        self.close_calls += 1


class TrackingAsyncJev(AsyncJev):
    def __init__(self, *, client: FakeAsyncTypeSafeClient) -> None:
        super().__init__(client=client)
        self.close_calls = 0

    async def close(self) -> None:
        self.close_calls += 1
        await super().close()


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


def test_pyjev_batch_uses_typed_asyncjev_bundle_results_and_cache():
    async def scenario():
        sdk_client = FakeAsyncTypeSafeClient()
        jev = TrackingAsyncJev(client=sdk_client)
        unifier = PyJevUnifier(jev=jev, semantic_batch_size=8)
        goal = await sentence("Homer is the father of {child}")
        candidates = [await sentence("Lisa's dad is Homer"), await sentence("Maggie's dad is Homer")]

        first = await unifier.unify_many(goal, candidates)
        second = await unifier.unify_many(goal, candidates)

        assert [result.unified for result in first] == [True, True]
        assert [result.bindings for result in first] == [{"child": "Lisa"}, {"child": "Maggie"}]
        assert len(sdk_client.calls) == 2
        assert [len(call[1]) for call in sdk_client.calls] == [4, 4]
        assert sdk_client.calls[1][0]["pairs"]["c0"] == {
            "goal": "Homer is the father of V0",
            "candidate": "Lisa's dad is Homer",
        }
        assert all(result.calls == 2 for result in first)
        assert all(result.usage.requests == 2 for result in first)
        assert all(result.usage.questions == 8 for result in first)
        assert all(result.usage.request_ids == ("request-1", "request-2") for result in first)
        assert all(result.usage.model == "fake-model" for result in first)
        assert first[0].usage.usage == {"input_tokens": 30, "output_tokens": 12, "total_tokens": 42}
        assert first[0].checks[0].probability == 0.96
        assert first[0].checks[1].probability == 0.98
        assert all(result.cached for result in second)
        assert all(result.calls == 0 and result.usage.cached for result in second)
        assert len(sdk_client.calls) == 2
        await unifier.close()
        assert jev.close_calls == 0
        assert sdk_client.close_calls == 0
        await jev.close()
        assert jev.close_calls == 1
        assert sdk_client.close_calls == 0

    asyncio.run(scenario())
