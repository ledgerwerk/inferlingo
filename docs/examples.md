# Examples

The source examples are runnable demonstrations. The exact examples work offline with the base
package. The family example needs the optional semantic backend.

## `birds.nl`

Purpose: the smallest fact to rule to rule chain.

```bash
inferlingo run examples/birds.nl "{bird} can fly?" --exact-only --explain
```

It demonstrates explicit derivation and a variable binding.

## `access_policy.nl`

Purpose: conjunction, negation-as-failure, and a variable result.

```bash
inferlingo run examples/access_policy.nl "{person} may deploy?" --exact-only --explain
```

Alice succeeds while suspended Bob does not.

## `dependency_impact.nl`

Purpose: quoted atoms and recursion.

```bash
inferlingo run examples/dependency_impact.nl "{service} is affected?" --exact-only --json
```

Expected bindings, ignoring order, are `auth`, `api`, and `web`.

## `family.nl`

Purpose: semantic equivalence plus an explicit implication rule. It requires
`inferlingo[jev]` and the authentication configured for the selected pyjev backend. Do not make
this the first example because it is not offline.

## `api_usage.py`

Purpose: high-level Python API, fact injection, provenance, and proof rendering.

```bash
python examples/api_usage.py
```

## Python linter

`python_lint_rules.nl` and `python_linter.py` demonstrate a real embedding pattern:

```bash
python examples/python_linter.py examples/python_linter_fixture.py
```

The data flow is:

```text
ast.parse()
    |
    | deterministic observations
    v
KnowledgeBase.add_fact()
    |
    | exact .nl rules
    v
"Function {fn} needs review?"
    |
    v
proof with source provenance
```

The script requires the project to be installed or otherwise available on Python's import path.
Running a script in `examples/` changes Python's initial import search root, so standard checkout
instructions should install the project before running it.
