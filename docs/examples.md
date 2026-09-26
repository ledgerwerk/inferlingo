# Examples

The examples show InferLingo's product boundary: deterministic application code supplies facts;
readable rules derive consequences; successful results carry proofs and evidence. The release gate,
service outage, and policy scenarios work offline with exact inference and no pyjev dependency.

## Release gate: separate facts, rules, and scenarios

`examples/release_gate.py` uses the structured `Fact` and reusable `RuleSet` APIs. It simulates inputs
from CI, change management, a security scanner, and a release calendar, then derives readiness and
positive blocker reasons from `examples/release_policy.nl`.

```bash
python examples/release_gate.py
inferlingo test examples/release_policy.nl examples/release_policy.cases.toml
```

The first command reports `checkout` as ready and explains blockers for `billing`, including evidence
locations. The TOML suite tests the rule pack independently from Python fact collection. This example
shows when rules earn their keep: multiple evidence sources contribute to policy that can change
without rewriting data collectors.

## Service outage blast radius: `dependency_impact.nl`

The service catalog describes a dependency chain from `checkout-web` through `checkout-api` and
`payments` to an unavailable PostgreSQL service. Recursive rules derive affected services; the proof
records the dependency path.

```bash
inferlingo run examples/dependency_impact.nl "{service} is affected?" --exact-only --explain
```

Expected affected services: `payments`, `checkout-api`, and `checkout-web`.

## Eligibility and access policy: `access_policy.nl`

This example combines employee and training facts with a suspension check:

```bash
inferlingo run examples/access_policy.nl "{person} may deploy?" --exact-only --explain
```

Expected binding: `person = Alice`. Negation as failure means the positive suspension goal could not
be proved for the already-bound person; it is not a stored classical negative fact. Use exact
inference for security-sensitive authorization.

## Advanced: deterministic analyzer + external policy

`python_linter.py` is an advanced embedding pattern, not InferLingo's primary product story. The
Python AST analyzer computes exact source observations; a separately maintained `.nl` ruleset derives
review findings and preserves source locations. Extraction is implementation logic; review policy is
organization logic.

```bash
python examples/python_linter.py examples/python_linter_fixture.py
```

## Language tutorial: `birds.nl`

This small program teaches fact/rule chaining and syntax. It derives that Tweety can fly only from the
explicit canary and bird rules; it demonstrates mechanics rather than the product's value proposition.

```bash
inferlingo run examples/birds.nl "{bird} can fly?" --exact-only --explain
```

## Optional semantic equivalence: `family.nl`

This advanced example separates same-fact wording compatibility from explicit logical implications.
Semantic matching may recognize differently worded statements as equivalent; the father-to-parent
implication still comes from a rule. Install the optional backend only when this interoperability
feature is needed:

```bash
python -m pip install 'inferlingo[jev]'
inferlingo run examples/family.nl "Homer is a parent of Lisa?" --explain
```

## Python API: `api_usage.py`

This smaller embedding example shows the compatible mutable `KnowledgeBase` API, fact injection,
provenance, and proof rendering. The release-gate example demonstrates `RuleSet` and `Fact` for the
isolated application-policy lifecycle.

```bash
python examples/api_usage.py
```

## Test coverage

Every `.nl` file under `examples/` is parsed in strict mode, and deterministic examples are exercised
without a semantic backend:

```bash
pytest -q tests/test_examples.py
```
