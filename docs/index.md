# InferLingo

**Readable rules over facts your application already knows.**

InferLingo is a small explainable derivation and policy engine. Deterministic application code and
external systems establish facts; explicit, version-controlled rules derive consequences; proofs can
retain provenance back to the evidence. Optional pyjev integration is a narrow same-fact wording
bridge, not general natural-language reasoning.

```text
Python / scanners / APIs compute facts
                    |
                    v
InferLingo applies explicit rules
                    |
                    v
         derived results + proofs
                    |
                    v
your application decides what to do
```

InferLingo does not fetch facts, parse arbitrary prose, perform arithmetic, classify intent, plan, or
execute actions.

## First useful workflow

From a source checkout, run the release policy demo and its offline rule scenarios:

```bash
python -m pip install -e .
python examples/release_gate.py
inferlingo test examples/release_policy.nl examples/release_policy.cases.toml
```

The demo derives a ready service and actionable blockers from facts supplied by Python. For a
mechanics-only introduction, see the [examples guide](examples.md).

## Choose a guide

- [Getting started](getting-started.md): run the release policy, scenarios, and Python API.
- [Concepts](concepts.md): facts, rules, queries, proofs, and bounded search.
- [Rule modeling patterns](patterns.md): eligibility, blockers, recursion, and evidence.
- [Language reference](language.md): statements, directives, variables, negation, and strict safety.
- [Python API](python-api.md): immutable rules, structured facts, sessions, and compatibility APIs.
- [CLI guide](cli.md): scenario testing, file composition, output, and exit codes.
- [Proofs and provenance](proofs-and-provenance.md): explanations and evidence.
- [Semantic unification](semantic-unification.md): optional same-fact matching through pyjev.
- [Examples](examples.md): release policy, service outage, access policy, and advanced integrations.
- [Debugging](debugging.md): parse errors, traces, truncation, and semantic diagnostics.
- [API reference](api/index.md): generated signatures and docstrings.
- [Development](development.md): contributor setup, checks, tests, and versioning.

```{toctree}
:maxdepth: 2
:hidden:

getting-started
concepts
patterns
language
python-api
cli
proofs-and-provenance
semantic-unification
examples
debugging
api/index
development
changelog
```
