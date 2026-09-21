# Proofs and provenance

InferLingo is designed to make derived results inspectable.

## Successful proof versus global trace

A solution carries its successful branch-local proof:

```python
solution.proof
solution.proof.render()
```

The run carries a global trace:

```python
result.steps
```

The trace can include failed candidates, unsuccessful unifications, negation attempts, and search
cutoffs that do not belong to the final proof. Use the proof to answer "why this result?" and the
trace to answer "what did the resolver try?"

## Provenance

Applications can attach source metadata when injecting facts:

```python
kb.add_fact(
    "Function {fn} catches a broad exception",
    fn="process_order",
    provenance=Provenance(
        source="orders.py",
        line=81,
        kind="python-ast",
    ),
)
```

When the fact participates in a solution, its provenance is retained on the corresponding proof
step. Provenance is application-owned evidence. InferLingo carries the metadata through a
derivation but does not verify the external source.

`Provenance` contains:

- `source`;
- `line`;
- `kind`;
- `metadata`.

## Semantic proof metadata

A semantic proof step can also carry:

- method;
- confidence;
- individual checks;
- request IDs;
- backend usage;
- cache status.

This is diagnostic evidence from the semantic backend, not a mathematical probability assigned to
the full theorem.

## Python linter pattern

The Python linter example shows the intended embedding boundary:

```text
Python ast
    |
    | deterministic observations
    v
KnowledgeBase.add_fact(...)
    |
    | exact .nl rules
    v
"Function {fn} needs review?"
    |
    v
proof with source provenance
```

Python performs source inspection and emits facts. InferLingo applies explicit rules and returns
findings whose proofs show which source observations supported them. This is a practical use of a
small rule engine without turning InferLingo into a source-code analyzer.
