# InferLingo

InferLingo is a small Python rule engine for facts and rules written as readable sentences.
Use deterministic code to establish facts, InferLingo to derive consequences from explicit rules,
and optional semantic unification when differently worded sentences may express the same fact.

InferLingo is not a chatbot, planner, arithmetic engine, source-code analyzer, or action runner.
Python or another deterministic subsystem supplies facts. InferLingo applies the rules you write,
builds inspectable proofs, and returns derived consequences.

## Install

Install the base package for deterministic inference:

```bash
python -m pip install inferlingo
```

The base package is fully usable offline. The Python `KnowledgeBase` API defaults to
`ExactUnifier`, and the first CLI workflows should use `--exact-only`.

Install the optional semantic backend only when differently worded sentences should be compared:

```bash
python -m pip install 'inferlingo[jev]'
```

Authentication and provider configuration belong to pyjev and its configured Jev backend.

## 60-second exact example

Create `rules.nl`:

```text
Alice is an employee.
Bob is an employee.
Bob is suspended.

{person} may deploy if
    {person} is an employee and
    not {person} is suspended.
```

Run it without a model or network access:

```bash
inferlingo run rules.nl "{person} may deploy?" --exact-only --explain
```

The solution binds `person = Alice`. The result follows only from the facts and explicit rule.
Negation is failure to prove the positive goal for the already-bound person, not a stored classical
negative fact.

The smallest chain is also available:

```bash
inferlingo run examples/birds.nl "{bird} can fly?" --exact-only --explain
```

It derives `bird = Tweety` from the fact and rules in `examples/birds.nl`, not from outside knowledge.

## How it fits into Python

```python
from inferlingo import KnowledgeBase

kb = KnowledgeBase.from_text(
    """
    Alice is an employee.
    {person} may deploy if {person} is an employee.
    """
)
result = kb.ask_sync("{person} may deploy?")
print(result.solutions[0].bindings)
```

The result is `{"person": "Alice"}`. Use `await kb.ask(...)` in asynchronous applications.
`ask_sync()` must not be called from a running event loop.

`KnowledgeBase.add_fact()` safely quotes injected application values and can carry
`Provenance` metadata into proof steps:

```python
from inferlingo import KnowledgeBase, Provenance

kb = KnowledgeBase.from_text("URL {url} is approved if URL {url} is reachable.")
kb.add_fact(
    "URL {url} is reachable",
    url="https://example.com/a?x=1&y=2",
    provenance=Provenance(source="scanner.py", line=41, kind="http-check"),
)
```

## Optional semantic unification

`PyJevUnifier` first tries exact wording and only sends differently worded candidates to the
semantic backend. Semantic matching is a same-fact equivalence check. It does not invent logical
implications. An explicit rule is still required to derive `parent` from `father`.

```bash
python -m pip install 'inferlingo[jev]'
pyjev auth set
pyjev auth test
inferlingo run examples/family.nl "Homer is a parent of Lisa?" --explain
```

The CLI uses `PyJevUnifier` by default for `run`; pass `--exact-only` to force deterministic
offline execution. Semantic confidence and backend checks are diagnostic signals, not theorem
probabilities.

## Documentation

Read the [full documentation](https://github.com/ledgerwerk/inferlingo/tree/main/docs) for:

- [Getting started](docs/getting-started.md)
- [Language reference](docs/language.md)
- [Python API](docs/python-api.md)
- [CLI guide](docs/cli.md)
- [Semantic unification](docs/semantic-unification.md)
- [Proofs and provenance](docs/proofs-and-provenance.md)
- [Examples](docs/examples.md)

The documentation also covers strict safety validation, quoted atoms, recursion, search limits,
traces, debugging, development, and the generated API reference.

## Development

For a source checkout, install contributor and documentation dependencies:

```bash
python -m pip install -e '.[dev,docs]'
```

Run the quality checks:

```bash
python -m compileall inferlingo examples docs
pytest
ruff check .
python docs/make.py html
python -m build
twine check dist/*
```

The test suite is offline. Semantic tests use fake or injected clients and do not require a live
API key.

## License

Apache-2.0
