from __future__ import annotations

import asyncio

import pytest

from inferlingo import KnowledgeBase, Provenance


def test_knowledge_base_facade_and_safe_fact_injection():
    kb = KnowledgeBase.from_text(
        "Alice is an employee.\n{person} may deploy if {person} is an employee.",
        source="policy.nl",
    )
    kb.add_fact(
        "URL {url} is reachable",
        url="https://example.com/a",
        provenance=Provenance(source="scanner.py", line=4, kind="python-ast"),
    )
    result = kb.ask_sync("URL {url} is reachable?")
    assert result.solutions[0].bindings == {"url": "https://example.com/a"}
    assert result.solutions[0].proof.steps[0].provenance == Provenance(source="scanner.py", line=4, kind="python-ast")


def test_ask_sync_rejects_running_event_loop():
    async def scenario():
        kb = KnowledgeBase.from_text("Alice is known.")
        with pytest.raises(RuntimeError, match="running event loop"):
            kb.ask_sync("Alice is known?")

    asyncio.run(scenario())
