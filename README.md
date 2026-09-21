# InferLingo

InferLingo is a small Python rule engine for facts and rules written as readable sentences.
Use Python to compute exact facts, InferLingo to derive consequences, and an optional semantic
unifier when two sentences express the same fact with different wording.

## Quick start

```bash
python -m pip install -e '.[dev]'
inferlingo run examples/birds.nl "{bird} can fly?" --exact-only --explain
inferlingo run examples/access_policy.nl "{person} may deploy?" --exact-only --explain
inferlingo run examples/dependency_impact.nl "{service} is affected?" --exact-only --json
```

The exact examples require no credentials and never contact a model. The expected bindings are
`Tweety`, `Alice`, and `auth`, `api`, `web` respectively. More examples are in `examples/README.md`.

## Python API

```python
from inferlingo import ExactUnifier, KnowledgeBase, Provenance

kb = KnowledgeBase.from_file("examples/python_lint_rules.nl", unifier=ExactUnifier())
kb.add_fact(
    "Function {fn} catches a broad exception",
    fn="process_order",
    provenance=Provenance(source="orders.py", line=81, kind="python-ast"),
)
kb.add_fact(
    "Function {fn} has an exception path that does not re-raise",
    fn="process_order",
    provenance=Provenance(source="orders.py", line=84, kind="python-ast"),
)

result = await kb.ask("Function {fn} may swallow errors?")
for solution in result.solutions:
    print(solution.bindings)
    print(solution.proof.render())
```

`ask_sync()` provides the same API outside an event loop. Calling it from an active event loop
raises a clear error, so asynchronous callers should use `await ask()`.

The lower-level API remains available:

```python
from inferlingo import ExactUnifier, NLEngine, parse_program, parse_query

result = await NLEngine(parse_program("Alice is known."), ExactUnifier()).run(
    parse_query("Alice is known?")
)
```

## Language

Facts and rules can use uppercase compatibility variables or descriptive braced variables:

```text
Tweety is a canary.
{bird} is a bird if {bird} is a canary.
{bird} can fly if {bird} is a bird.
{person} is trusted if {person} is known and not {person} is blocked.
```

Quoted atoms preserve opaque application values exactly:

```text
Artifact "https://example.com/a" is reachable.
User "john@example.com" is active.
Version "3.14.2" is deployed.
Path "/srv/app/config.yaml" exists.
```

Quoted values may contain spaces, escaped quotes, and escaped backslashes. Keywords inside a
quoted value are ordinary text. Comments use `#`, `%`, or `//` outside quoted values.

Rules are validated in strict mode. Facts must be ground, rule-head variables must occur in a
positive condition, and negative-condition variables must be range restricted by positive
conditions. Negation means failure to prove the positive fact. Unground negation is rejected.

## Deterministic and semantic boundaries

Exact unification is deterministic and offline. It handles wording, variable bindings, and
multi-token phrases. It does not contact a model.

`PyJevUnifier` is optional:

```bash
python -m pip install -e '.[dev,jev]'
pyjev auth set
pyjev auth test
inferlingo run examples/family.nl "Homer is a parent of Lisa?" --explain
```

Semantic unification recognizes equivalent statements. It does not turn implication into
synonymy. The explicit rule in `family.nl` expresses `father -> parent`; the semantic backend
may only recognize `Lisa's dad is Homer` and `Homer is the father of Lisa` as the same fact.
Semantic judgments retain their checks and confidence signals. They are not theorem
probabilities. Batched semantic candidates use bounded two-phase requests and a bounded,
configuration-aware in-memory cache.

## CLI output and exit codes

`inferlingo validate FILE` parses a program without a backend. `inferlingo run FILE QUERY` supports:

- `--exact-only` for offline deterministic execution
- `--json` for stable machine-readable solutions, proofs, trace, and stats
- `--explain` for the proof attached to each solution
- `--trace` for all search attempts, including failures and cutoffs
- `--stats` for aggregate backend, indexing, and proof counters
- `--debug` as a compatibility alias for `--trace`

Exit codes are:

- `0`: command completed, including a query with no solutions
- `1`: backend or runtime failure
- `2`: invalid file, syntax, or rule-safety error
- `130`: interrupted by the user

## Architecture

```text
.nl program
    |
    v
quote-aware parser and safety validation
    |
    v
indexed deterministic resolver and proof paths
    |
    +--> exact wording and bindings
    |
    +--> optional batched semantic unifier
              |
              v
             pyjev
```

Deterministic code computes facts. InferLingo derives logical consequences. Semantic models are
used only at an explicit equivalence judgment boundary. InferLingo does not translate free-form
questions, perform arithmetic, inspect source code, execute actions, or invent missing facts.

## Development

```bash
pytest -q
ruff check .
python -m build
```

The test suite is offline. It uses fake semantic clients for batching and does not require an API
key.

## License

Apache-2.0.
