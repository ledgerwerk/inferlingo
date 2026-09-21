from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "inferlingo", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_cli_json_is_stable_and_includes_stats():
    completed = run_cli("run", "examples/birds.nl", "{bird} can fly?", "--exact-only", "--json")
    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    assert payload["solutions"][0]["bindings"] == {"bird": "Tweety"}
    assert payload["stats"]["clauses_considered"] > 0
    assert "<Variable" not in completed.stdout


def test_cli_explain_trace_and_debug_alias():
    explained = run_cli("run", "examples/birds.nl", "{bird} can fly?", "--exact-only", "--explain")
    traced = run_cli("run", "examples/birds.nl", "{bird} can fly?", "--exact-only", "--debug")
    assert explained.returncode == 0
    assert "EXPLANATIONS" in explained.stdout
    assert "Tweety" in explained.stdout
    assert traced.returncode == 0
    assert "PROOF TRACE" in traced.stdout


def test_cli_reports_source_aware_parse_errors_and_no_solutions():
    invalid = run_cli("validate", "examples/access_policy.nl")
    assert invalid.returncode == 0
    missing = run_cli("run", "examples/birds.nl", "Bob is a fish?", "--exact-only")
    assert missing.returncode == 0
    assert "No." in missing.stdout
