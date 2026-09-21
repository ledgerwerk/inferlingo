# Getting started

This guide uses the access-policy example to show exact inference without a semantic backend or
network access.

## Install

```bash
python -m pip install inferlingo
```

The base installation is sufficient for deterministic inference. Use `--exact-only` with the CLI.
Install `inferlingo[jev]` only when you need optional semantic same-fact matching.

## Validate a program

The program in `examples/access_policy.nl` contains:

```text
Alice is an employee.
Alice completed deployment training.
Bob is an employee.
Bob completed deployment training.
Bob is suspended.

{person} may deploy if
    {person} is an employee and
    {person} completed deployment training and
    not {person} is suspended.
```

Validate syntax and strict rule safety:

```bash
inferlingo validate examples/access_policy.nl
```

`validate` parses the program and reports fact and rule-clause counts. It does not contact Jev.

## Ask a variable query

```bash
inferlingo run examples/access_policy.nl "{person} may deploy?" --exact-only --explain
```

Alice satisfies the two positive conditions and is not suspended, so the variable binds to Alice.
Bob is excluded because `Bob is suspended` is provable. The `not` condition is negation-as-failure:
the positive fact cannot be proved for the bound person. It is not a stored classical negative fact.

A variable query prints bindings and a ground query prints `Yes.` or `No.`:

```bash
inferlingo run examples/access_policy.nl "Alice may deploy?" --exact-only
```

A valid query with no solutions is still a successful CLI execution.

## Use Python

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

The output is:

```python
{"person": "Alice"}
```

The high-level API defaults to `ExactUnifier`, so this example is offline. Use `await kb.ask(...)`
in an async application. See [Python API](python-api.md) for safe fact injection, provenance,
limits, and result metadata.

## Continue learning

- Learn the syntax in [Language reference](language.md).
- Understand proofs and global traces in [Proofs and provenance](proofs-and-provenance.md).
- Add semantic same-fact matching with [Semantic unification](semantic-unification.md).
