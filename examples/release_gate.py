"""Offline release-gate demo: deterministic inputs, explicit rules, and evidence."""

from __future__ import annotations

import asyncio
from pathlib import Path

from inferlingo import ExactUnifier, Fact, Provenance, RuleSet, Solution

ROOT = Path(__file__).resolve().parent

# These fixtures stand in for adapters to CI, change management, a security
# scanner, and the release calendar. The rule engine does not query those systems.
FACTS: tuple[Fact, ...] = (
    Fact(
        "{service} has passing tests",
        {"service": "checkout"},
        provenance=Provenance("ci/test-results.json", 1, "ci"),
    ),
    Fact(
        "{service} has failing tests",
        {"service": "billing"},
        provenance=Provenance("ci/test-results.json", 18, "ci"),
    ),
    Fact(
        "{service} has an approved change",
        {"service": "checkout"},
        provenance=Provenance("change/CHG-481.md", 1, "change-management"),
    ),
    Fact(
        "{service} needs change approval",
        {"service": "billing"},
        provenance=Provenance("change/CHG-482.md", 1, "change-management"),
    ),
    Fact(
        "{service} has acceptable vulnerability status",
        {"service": "checkout"},
        provenance=Provenance("scanner/report.json", 8, "security-scan"),
    ),
    Fact(
        "{service} has critical vulnerabilities",
        {"service": "billing"},
        provenance=Provenance("scanner/report.json", 23, "security-scan"),
    ),
    Fact(
        "{service} is frozen",
        {"service": "billing"},
        provenance=Provenance("calendar/release-freeze", 1, "calendar"),
    ),
)


def build_policy() -> RuleSet:
    """Load reusable exact rules; per-run facts are supplied separately."""
    return RuleSet.from_file(ROOT / "release_policy.nl", unifier=ExactUnifier())


async def render_report() -> str:
    """Return the complete human-readable demo output."""
    policy = build_policy()
    ready_result = await policy.ask("{service} is release-ready?", facts=FACTS)
    blocker_result = await policy.ask("{service} has blocker {reason}?", facts=FACTS)

    ready = sorted(solution.bindings["service"] for solution in ready_result.solutions)
    blockers: dict[str, list[Solution]] = {}
    for solution in blocker_result.solutions:
        service = solution.bindings["service"]
        blockers.setdefault(service, []).append(solution)

    lines = [
        "InferLingo release policy demo",
        "===============================",
        "",
        "Python collected exact facts from CI, change management, security, and the release calendar.",
        "InferLingo only applies the explicit rules in release_policy.nl.",
        "",
        "READY",
    ]
    lines.extend(f"  {service}" for service in ready)
    lines.extend(("", "BLOCKED"))
    for service in sorted(blockers):
        lines.append(f"  {service}")
        for solution in sorted(blockers[service], key=lambda item: item.bindings["reason"]):
            lines.append(f"    - {solution.bindings['reason']}")
            evidence: list[str] = []
            for step in solution.proof.steps:
                provenance = step.provenance
                if provenance is None or provenance.source is None:
                    continue
                location = provenance.source
                if provenance.line is not None:
                    location += f":{provenance.line}"
                if location not in evidence:
                    evidence.append(location)
            lines.append(f"      evidence: {', '.join(evidence) if evidence else 'policy input'}")

    lines.extend(
        (
            "",
            "What InferLingo did:",
            "  1. accepted exact facts supplied by Python",
            "  2. applied version-controlled release rules",
            "  3. derived readiness and actionable blocker reasons",
            "  4. retained provenance for supporting evidence",
        )
    )
    return "\n".join(lines)


def main() -> None:
    print(asyncio.run(render_report()))


if __name__ == "__main__":
    main()
