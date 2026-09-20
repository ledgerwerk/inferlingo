# inferlingo

A small, model-neutral Prolog-like logic interpreter whose facts and rules stay in readable English.
Ordinary Python performs parsing, substitutions, backtracking, rule execution, negation-as-failure,
and exact wording matches. Differently worded sentences can be delegated to a pluggable semantic
unifier. The MVP ships with an optional `PyJevUnifier` adapter for pyjev/Jev.

This is an MVP inspired by `narphorium/nl-logic-interpreter`, rewritten as a Python-first library
with the semantic-model boundary kept behind a small `Unifier` protocol.

## What this MVP includes

- root-level Python package (`inferlingo/`) — **no `src/` layer**;
- **dynamic versions from Git tags** via `setuptools-scm`;
- facts and rules written one sentence per line;
- variables such as `X`, `Y`, `Z1`;
- `if`, `then`, `when`, `and`, `or`, and leading `not`;
- SLD-style depth-first proof search and rule-variable freshening;
- exact unification in normal Python before any model call;
- a model-neutral `Unifier` protocol plus an optional pyjev-backed semantic adapter;
- canonicalized async semantic-unification cache and configurable backend concurrency;
- an `--exact-only` mode that never contacts a semantic model;
- structured proof steps for `--debug` output;
- offline unit tests that do not require an API key.

The deliberate MVP limitation is **no System Two question translator**. Write a goal directly, for
example `X is a grandfather of Bart?`, rather than `Who is Bart's grandfather?`. This keeps every AI
operation a structured semantic judgment when the optional Jev adapter is used.

## Install

From the extracted project:

For deterministic logic only:

```bash
python -m pip install -e '.[dev]'
```

For the included Jev semantic backend:

```bash
python -m pip install -e '.[dev,jev]'
```

Then configure pyjev in the normal way:

```bash
pyjev auth set
pyjev auth test
```

or use `TYPESAFE_API_KEY`.

## Try the deterministic example

```bash
inferlingo run programs/birds.nl "X can fly?" --exact-only --debug
```

Expected solution:

```text
X = Tweety
```

No model is used because every proof step uses the same wording.

## Try semantic unification

`programs/family.nl` deliberately contains this fact:

```text
Lisa's dad is Homer.
```

and this rule:

```text
If X is the father of Y then X is a parent of Y.
```

Ask:

```bash
inferlingo run programs/family.nl "Homer is a parent of Lisa?" --debug
```

The engine can match the query to the rule head deterministically. It then needs to prove:

```text
Homer is the father of Lisa
```

against:

```text
Lisa's dad is Homer
```

That differently worded pair is sent through the configured semantic unifier. The CLI currently uses the optional `PyJevUnifier` adapter.

You can also ask for bindings:

```bash
inferlingo run programs/family.nl "X is a parent of Lisa?"
```

## Program syntax

Facts are ordinary lines:

```text
Tweety is a canary.
Lisa's dad is Homer.
```

Rules support these forms:

```text
If X is a canary then X is a bird.
If X is a bird, X can fly.
When X is a bird, X can fly.
X is a canary then X is a bird.
X can fly if X is a bird.
X can fly when X is a bird.
```

Conditions can use `and`, `or`, commas, semicolons, and leading `not`:

```text
X is trusted if X is known and not X is blocked.
X may enter if X has a badge or X is escorted.
```

`not` is **negation as failure**. Negative wording inside a normal sentence is just wording.

## Why the semantic unifier has two phases

For differently worded goal/candidate pairs, the MVP follows the same basic safety idea as the source
project:

1. **Align** — ask whether the sentences could state the same fact and, for each variable, which phrase
   in the other sentence it denotes. Candidates below the alignment threshold are rejected early.
2. **Verify** — fill the bindings, then ask both how statement B relates to statement A and whether
   they concern the same participants. Only `same` with sufficient probability and sufficient
   participant probability counts as unification.

This prevents an implication such as `father -> parent` from being silently treated as a paraphrase.
That implication should be an explicit rule.

The included Jev adapter uses pyjev's typed `noul()` and `choice()` primitives. This means one semantic unification can
use more API calls than the TypeScript reference, which bundles dynamic questions. A natural pyjev
follow-up is a first-class typed **dynamic bundle** API; the rest of this interpreter would not need to
change.

## Architecture

```text
.nl program
    |
    v
parser.py  ------------------------------- deterministic
    |
    v
engine.py (SLD/backtracking/negation)
    |
    +--> exact wording match -------------- deterministic
    |
    +--> PyJevUnifier --------------------- judgment boundary
             |
             +--> align: Noul + Choice(s)
             |
             +--> verify: Choice + Noul
             |
             v
           pyjev -> typesafe-sdk -> Jev
```

The logic engine depends only on the small `Unifier` protocol. Tests can inject a fake unifier,
`--exact-only` swaps in `ExactUnifier`, and future adapters can target other semantic classifiers or
judgment models without changing the parser or inference engine.

## Dynamic versioning

There is no version string to edit in source code.

`pyproject.toml` declares:

```toml
[project]
dynamic = ["version"]

[tool.setuptools_scm]
version_file = "inferlingo/_version.py"
fallback_version = "0.0.0"
parentdir_prefix_version = "inferlingo-"
local_scheme = "no-local-version"
```

Normal release flow:

```bash
git init
git add .
git commit -m "Initial inferlingo MVP"
git tag v0.1.0
python -m build
```

`setuptools-scm` derives the package version from Git and writes the generated
`inferlingo/_version.py` into build contexts.

## Development

```bash
pytest
ruff check .
python -m build
python -m twine check dist/*
```

The test suite is intentionally offline; it exercises parsing, exact unification, SLD resolution,
negation, semantic-unifier integration through a fake, and package version fallback behavior without
contacting Jev.

## Not in the MVP

- free-form question -> logical-goal translation;
- web UI / step-through visualizer;
- persistence;
- cut/operator syntax;
- full Prolog term grammar;
- occurs-check / arbitrary nested terms;
- typed dynamic pyjev bundles in one API request.

Those can be added without changing the main boundary: deterministic logic in Python, ambiguous
semantic equivalence behind a pluggable backend.

## License

Apache-2.0.
