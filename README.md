[![PyPI - Version](https://img.shields.io/pypi/v/inferlingo)](https://pypi.org/project/inferlingo/)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/inferlingo)
![PyPI - Downloads](https://img.shields.io/pypi/dm/inferlingo)
[![codecov](https://codecov.io/gh/ledgerwerk/inferlingo/graph/badge.svg?token=WzRI7jIoDg)](https://codecov.io/gh/ledgerwerk/inferlingo)

# InferLingo

InferLingo is a small Python rule engine for deriving explainable policy, eligibility, compliance,
and impact results from facts your application already knows.

Use it when facts and rules have different lifecycles: collect trustworthy observations in Python or
external systems, keep changing policy in readable rule files, and retain proofs showing which
conditions and evidence produced a result. InferLingo applies explicit rules; it is not a chatbot,
planner, arithmetic engine, source-code analyzer, or action runner.

```text
Python / APIs / scanners collect facts
                 |
                 v
InferLingo derives consequences from explicit rules
                 |
                 v
proofs + provenance explain successful results
                 |
                 v
your application decides what to do
```

## Install

```bash
python -m pip install inferlingo
```

The base package is usable offline and uses exact unification by default in the Python API. The CLI
preserves its semantic-capable default for `run`; pass `--exact-only` for deterministic, offline
execution. Install optional semantic support only when differently worded statements may express the
same fact:

```bash
python -m pip install 'inferlingo[jev]'
```

Optional pyjev matching compares candidate facts. It does not invent logical implications or replace
explicit policy rules. For authorization and other high-consequence decisions, prefer exact inference.

## 60-second example: release policy

From a source checkout, run the flagship example and its rule scenarios:

```bash
python -m pip install -e .
python examples/release_gate.py
inferlingo test examples/release_policy.nl examples/release_policy.cases.toml
```

Python supplies simulated facts from CI, change management, a security scanner, and a release
calendar. The rules derive that `checkout` is ready and report four actionable blockers for `billing`,
with evidence locations. The rule pack and TOML scenarios can be reviewed and tested independently of
fact collection. InferLingo does not contact those systems or decide what action to take.

## Embed policy in Python

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

if result.matched:
    print(result.values("service"))  # ('checkout',)
```

`RuleSet` keeps reusable rules separate from per-evaluation facts. Each call gets an isolated fact
set; structured `Fact` values are safely quoted, and provenance flows into successful proof steps.
Use `await rules.ask(...)` in async applications. `KnowledgeBase` remains available for mutable,
backwards-compatible workflows.

## Why not just Python?

A few conditions may be simpler as an `if` statement. InferLingo becomes useful when multiple
independent evidence sources feed rules that change separately from collectors, when rule packs need
scenario tests, or when decisions need inspectable derivations and source provenance. Keep numeric,
date, API, and parsing work in deterministic application code; turn its results into facts for the
rule engine.

## Documentation

- [Getting started](docs/getting-started.md)
- [Concepts](docs/concepts.md)
- [Rule modeling patterns](docs/patterns.md)
- [Language reference](docs/language.md)
- [Python API](docs/python-api.md)
- [CLI guide](docs/cli.md)
- [Proofs and provenance](docs/proofs-and-provenance.md)
- [Semantic unification](docs/semantic-unification.md)
- [Examples](docs/examples.md)
- [API reference](docs/api/index.md)

## Development

```bash
python -m pip install -e '.[dev,docs]'
python -m compileall inferlingo examples docs
pytest
ruff check .
python docs/make.py html
python -m build
twine check dist/*
```

The test suite is offline. Semantic tests use fake or injected clients and do not require live
credentials.

## License

Apache-2.0
