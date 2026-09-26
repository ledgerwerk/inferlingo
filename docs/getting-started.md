# Getting started

InferLingo is for applications that collect trustworthy facts in ordinary code and want separate,
reviewable rules to derive policy, eligibility, compliance, or impact results. The engine does not
collect data from CI, scanners, APIs, or calendars, and it does not decide what action to take.

## Install

```bash
python -m pip install inferlingo
```

The base installation is enough for deterministic inference. Python APIs default to
`ExactUnifier`; use `--exact-only` with the CLI for offline exact execution. Optional pyjev support is
for same-fact wording compatibility, not a requirement for the workflows below.

## Run the release policy example

From a source checkout, run the example and the independent scenario suite:

```bash
python -m pip install -e .
python examples/release_gate.py
inferlingo test examples/release_policy.nl examples/release_policy.cases.toml
```

The Python example supplies sample evidence from CI, change management, a security scanner, and the
release calendar. `release_policy.nl` contains reusable policy rules; the report derives readiness and
positive blocker reasons while retaining evidence provenance. The scenario file tests the rules without
running or depending on the Python fact collector.

Inspect the separately maintained rules:

```text
{service} is release-ready if
    {service} has passing tests and
    {service} has an approved change and
    {service} has acceptable vulnerability status and
    not {service} is frozen.
```

Validate a rule pack without contacting any semantic backend:

```bash
inferlingo validate examples/release_policy.nl
```

For direct CLI evaluation, put runtime observations in fact-only files and compose them with the
rules:

```bash
inferlingo run examples/release_policy.nl "checkout is release-ready?" \
  --facts build_facts.nl --facts security_facts.nl --exact-only --explain
```

`--rules` can similarly add more rule files. Existing positional usage remains valid:

```bash
inferlingo run examples/birds.nl "{bird} can fly?" --exact-only --explain
```

## Embed a reusable rule set

`RuleSet` separates immutable rules from runtime facts. A `Fact` safely inserts application values as
opaque atoms and can attach source provenance to proof steps:

```python
from inferlingo import ExactUnifier, Fact, Provenance, RuleSet

rules = RuleSet.from_file("examples/release_policy.nl", unifier=ExactUnifier())
facts = [
    Fact(
        "{service} has passing tests",
        {"service": "checkout"},
        provenance=Provenance(source="ci/test-results.json", line=1, kind="ci"),
    ),
    Fact("{service} has an approved change", {"service": "checkout"}),
    Fact("{service} has acceptable vulnerability status", {"service": "checkout"}),
]
result = rules.ask_sync("{service} is release-ready?", facts=facts)
print(result.values("service"))
```

The output is `('checkout',)`. Each `RuleSet.ask()` evaluation gets fresh, isolated facts. In async
code use `await rules.ask(...)`; use `rules.session()` when several queries should share a single
request's facts. `KnowledgeBase` remains supported for existing mutable workflows.

## Learn the language mechanics

The access policy example demonstrates conjunction and safe negation-as-failure:

```bash
inferlingo run examples/access_policy.nl "{person} may deploy?" --exact-only --explain
```

Alice matches; suspended Bob does not. `not {person} is suspended` means the positive suspension goal
cannot be proved for the already-bound person. It is not a stored classical negative fact. See the
[language reference](language.md) for safety constraints and the [concepts guide](concepts.md) for the
execution model.

## Continue learning

- [Rule modeling patterns](patterns.md) for eligibility, blockers, recursion, and evidence.
- [Python API](python-api.md) for sessions, composition, limits, and results.
- [CLI guide](cli.md) for scenario schemas, file composition, and output options.
- [Proofs and provenance](proofs-and-provenance.md) for explanations and evidence.
- [Examples](examples.md) for the release gate, service outage, and advanced integrations.
