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


def test_cli_runs_offline_toml_scenarios():
    completed = run_cli(
        "test",
        "examples/release_policy.nl",
        "examples/release_policy.cases.toml",
    )

    assert completed.returncode == 0
    assert "PASS healthy checkout service is release ready" in completed.stdout
    assert "PASS release freeze blocks readiness" in completed.stdout
    assert "PASS critical vulnerability becomes a blocker" in completed.stdout
    assert "3 passed, 0 failed" in completed.stdout


def test_cli_composes_multiple_rule_and_fact_files(tmp_path):
    base_rules = tmp_path / "base.nl"
    extra_rules = tmp_path / "training.nl"
    ci_facts = tmp_path / "ci.nl"
    training_facts = tmp_path / "training-facts.nl"
    base_rules.write_text("{person} is an employee if {person} is active.\n", encoding="utf-8")
    extra_rules.write_text(
        "{person} may deploy if {person} is an employee and {person} completed training.\n",
        encoding="utf-8",
    )
    ci_facts.write_text("Alice is active.\n", encoding="utf-8")
    training_facts.write_text("Alice completed training.\n", encoding="utf-8")

    completed = run_cli(
        "run",
        str(base_rules),
        "Alice may deploy?",
        "--rules",
        str(extra_rules),
        "--facts",
        str(ci_facts),
        "--facts",
        str(training_facts),
        "--exact-only",
    )

    assert completed.returncode == 0
    assert "Yes." in completed.stdout


def test_cli_scenario_mismatch_exits_nonzero(tmp_path):
    rule_file = tmp_path / "rules.nl"
    case_file = tmp_path / "cases.toml"
    rule_file.write_text("Alice is known.\n", encoding="utf-8")
    case_file.write_text(
        'schema = 1\n\n[[case]]\nname = "wrong expectation"\nquery = "Alice is known?"\nexpect = false\n',
        encoding="utf-8",
    )

    completed = run_cli("test", str(rule_file), str(case_file))

    assert completed.returncode == 1
    assert "FAIL wrong expectation" in completed.stdout
    assert "0 passed, 1 failed" in completed.stdout
