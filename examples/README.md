# InferLingo examples

The examples progress from deterministic exact inference to optional semantic unification and Python embedding. Run the deterministic examples without credentials or network access.

## Basic chaining: `birds.nl`

This is the smallest complete InferLingo program. It contains a canary fact, a rule deriving that the canary is a bird, and a second rule deriving that the bird can fly.

```bash
inferlingo run examples/birds.nl "{bird} can fly?" --exact-only --explain
```

Expected binding: `bird = Tweety`. The result comes only from the two explicit rules. InferLingo does not use outside knowledge about canaries.

## Policy and negation: `access_policy.nl`

This example combines several conditions with `and` and uses negation as failure. Alice is an employee who completed training and is not suspended, while Bob is suspended.

```bash
inferlingo run examples/access_policy.nl "{person} may deploy?" --exact-only --explain
```

Expected binding: `person = Alice`. The condition `not {person} is suspended` means the positive goal could not be proved for that already-bound person. It is not a separate classical negative fact.

## Recursive dependency impact: `dependency_impact.nl`

Quoted service names form a dependency graph. Recursive rules propagate an unavailable database through auth and api to web.

```bash
inferlingo run examples/dependency_impact.nl "{service} is affected?" --exact-only --explain
```

Expected bindings, ignoring order: `auth`, `api`, and `web`. Quoted atoms preserve opaque application values such as service names.

## Semantic equivalence: `family.nl`

This example separates semantic wording equivalence from explicit logic. The fact `Lisa's dad is Homer` may need semantic unification to match `Homer is the father of Lisa`. The rule from father to parent remains explicit.

```bash
inferlingo run examples/family.nl "Homer is a parent of Lisa?" --explain
```

Use the optional `jev` extra for this example:

```bash
python -m pip install -e '.[dev]'
inferlingo run examples/family.nl "Homer is a parent of Lisa?" --explain
```

The semantic backend may bridge paraphrasing and word order. It must not invent the `father -> parent` implication.

## Python API: `api_usage.py`

This runnable example loads the linter rules, adds exact facts from a hypothetical Python AST with `Provenance`, asks for a derived finding, and renders its proof.

```bash
python examples/api_usage.py
```

Expected output includes the binding `process_order` and proof lines pointing to `orders.py:81` and `orders.py:84`.

## Python semantic linter: `python_lint_rules.nl` and `python_linter.py`

The linter architecture keeps deterministic source inspection in Python and logical consequences in InferLingo. The AST extractor emits facts such as broad exception handling and missing re-raise behavior. The `.nl` rules derive `may swallow errors` and `needs review`.

```bash
python examples/python_linter.py examples/python_linter_fixture.py
```

The fixture produces a review finding for `process_order`. A function with a narrow exception handler that re-raises does not produce the swallowing finding. Provenance from the Python source is retained in the proof.

## Running the full example test coverage

Every `.nl` file under `examples/` is parsed in strict mode by the tests. The exact examples are also exercised without a semantic backend:

```bash
pytest -q tests/test_examples.py
```
