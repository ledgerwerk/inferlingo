# Rule modeling patterns

Keep observations and application logic in deterministic code. Use InferLingo for explicit
relationships whose policy should be readable, separately reviewable, and explainable. The examples
below are offline and use sentence-shaped facts.

## Eligibility and readiness

Combine positive prerequisites and, when appropriate, a safely bound negation-as-failure condition:

```text
{subject} is eligible if
    {subject} has active status and
    {subject} completed training and
    not {subject} is blocked.
```

Every variable in a rule head must occur in a positive body condition; variables in a negative
condition must also be positively bound. For high-consequence decisions, keep facts and unification
exact, and explicitly test eligibility boundaries.

## Positive blocker reasons

A missing success is not a friendly explanation of failure. Model actionable reasons as positive
derived facts:

```text
{service} has blocker "tests failing" if
    {service} has failing tests.

{service} has blocker "release freeze" if
    {service} is frozen.
```

Then ask `{service} has blocker {reason}?`. This yields concrete, auditable results with ordinary
proofs and provenance instead of pretending the engine has explained why a goal failed.

## Recursive impact

Recursion is useful for dependency graphs, ownership inheritance, and escalation paths:

```text
{item} is affected if
    {item} depends on {dependency} and
    {dependency} is unavailable.

{item} is affected if
    {item} depends on {dependency} and
    {dependency} is affected.
```

The first rule finds direct impact; the second propagates impact through other affected items. See
[`dependency_impact.nl`](../examples/dependency_impact.nl) for a complete outage blast-radius example.

## Evidence-backed findings

Attach `Provenance` to an input `Fact` when collecting it. Rules derive findings without losing the
supporting evidence:

```python
from inferlingo import Fact, Provenance

Fact(
    "{artifact} has risky property",
    {"artifact": "payments-api"},
    provenance=Provenance(source="scanner/report.json", line=23, kind="security-scan"),
)
```

```text
{artifact} requires review if
    {artifact} has risky property.
```

The resulting proof identifies the rule, fact, and evidence location. The application owns and
validates its source evidence; InferLingo preserves but does not audit it.

## Normalize before rule evaluation

Use Python or a specialized deterministic subsystem for numeric comparisons, dates, parsing, API
calls, and schema checks. Convert their outcomes into explicit facts:

```python
if vulnerability_count > 3:
    facts.append(Fact("{service} has elevated vulnerability count", {"service": service}))
```

```text
{service} requires security review if
    {service} has elevated vulnerability count.
```

This keeps the rule language small, facts inspectable, and derivations grounded in explicit
observations.

## Separate rules, facts, and scenarios

Keep reusable rule files apart from runtime evidence. Use `RuleSet.from_files(...)` or repeated CLI
`--rules` options to compose rule packs; use `RuleSet.ask(..., facts=...)`, `Session`, or CLI `--facts`
for evaluation-specific observations. Each TOML scenario is an independent test case for the policy,
not for an external fact collector:

```bash
inferlingo test policies/release.nl policies/release.cases.toml
```

Name important rules with `# @rule` and explain their intent with `# @description`. Scenario
expectations should cover ready outcomes, blockers, and boundary conditions.

## Semantic bridge (advanced)

Use `PyJevUnifier` only when differently worded candidate statements may represent the same fact. It
must not create implications such as `father -> parent`; encode those as explicit rules. Semantic
matching is optional and should not silently decide authorization, payment, or destructive actions.

See [Semantic unification](semantic-unification.md) for configuration, evidence, and limits.
