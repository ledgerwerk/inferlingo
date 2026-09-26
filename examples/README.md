# InferLingo examples

InferLingo derives consequences from facts your application already knows. Deterministic code or external systems collect the facts; exact, readable rules combine them; proofs retain the evidence. The examples below progress from practical policy to language mechanics and optional semantic matching. Install the package before running scripts from this directory. The release-gate, outage, and policy examples work offline without pyjev.

## Release gate: `release_policy.nl` and `release_gate.py`

This is the flagship example. Python supplies simulated facts from CI, change management, a security scanner, and a release calendar. InferLingo applies a separately maintained rule pack to derive release readiness and positive blocker reasons. It does not query those systems or decide what action to take.

```bash
python examples/release_gate.py
```

The output shows `checkout` as ready and `billing` blocked by test failures, missing change approval, critical vulnerabilities, and a release freeze. Evidence locations are carried into the findings. For one or two fixed conditions ordinary Python may be simpler; the rules become useful when independent sources and evolving policy need separate lifecycles.

The accompanying offline suite tests policy outcomes separately from the Python fact collector:

```bash
inferlingo test examples/release_policy.nl examples/release_policy.cases.toml
```

## Service outage blast radius: `dependency_impact.nl`

The service catalog describes a dependency chain from `checkout-web` through `checkout-api` and `payments` to an unavailable PostgreSQL service. Recursive rules derive the affected services and the proof records the dependency path.

```bash
inferlingo run examples/dependency_impact.nl "{service} is affected?" --exact-only --explain
```

Expected affected services: `payments`, `checkout-api`, and `checkout-web`.

## Eligibility and access policy: `access_policy.nl`

This example combines employee and training facts with a suspension check. Negation as failure means the positive suspension goal could not be proved for the already-bound person; it is not a stored classical negative fact.

```bash
inferlingo run examples/access_policy.nl "{person} may deploy?" --exact-only --explain
```

Expected binding: `person = Alice`. For security-sensitive authorization, use exact inference and model positive evidence explicitly.

## Deterministic analyzer + external policy: `python_linter.py`

This is an advanced embedding pattern, not the primary product story. The Python AST analyzer computes exact source observations; a separately maintained `.nl` ruleset derives review findings and preserves source locations. Keep extraction implementation logic distinct from organization review policy.

```bash
python examples/python_linter.py examples/python_linter_fixture.py
```

## Basic chaining: `birds.nl`

This small program teaches fact/rule chaining and syntax. It derives that Tweety can fly only from the explicit canary and bird rules; it is a language tutorial, not the product's value proposition.

```bash
inferlingo run examples/birds.nl "{bird} can fly?" --exact-only --explain
```

## Optional semantic equivalence: `family.nl`

This advanced example separates same-fact wording compatibility from explicit logical implications. Semantic matching may recognize differently worded statements as equivalent; the father-to-parent implication still comes from a rule. Install the optional backend only when that interoperability feature is needed:

```bash
python -m pip install 'inferlingo[jev]'
inferlingo run examples/family.nl "Homer is a parent of Lisa?" --explain
```

## Python API: `api_usage.py`

The embedding example loads rules, adds exact facts with `Provenance`, asks for a derived finding, and renders its proof.

```bash
python examples/api_usage.py
```

## Running the full example test coverage

Every `.nl` file under `examples/` is parsed in strict mode, and deterministic examples are exercised without a semantic backend:

```bash
pytest -q tests/test_examples.py
```
