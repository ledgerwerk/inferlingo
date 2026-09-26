# Proofs and provenance

InferLingo makes successful derivations inspectable. A solution's branch-local proof explains why
that answer exists; application-supplied provenance can connect supporting facts to their source
records. Provenance is carried, not independently verified by the engine.

## Explain a successful result

Give rules stable names and descriptions with comment directives:

```text
# @rule release-ready
# @description Require CI evidence and ensure the service is not frozen.
{service} is release-ready if
    {service} has passing tests and
    not {service} is frozen.
```

Attach provenance as facts enter the evaluation, then inspect the instantiated solution explanation:

```python
from inferlingo import Fact, Provenance, RuleSet

rules = RuleSet.from_file("release_policy.nl")
result = rules.ask_sync(
    "{service} is release-ready?",
    facts=[
        Fact(
            "{service} has passing tests",
            {"service": "checkout"},
            provenance=Provenance(source="ci/test-results.json", line=12, kind="ci"),
        )
        Fact("{service} has an approved change", {"service": "checkout"}),
        Fact("{service} has acceptable vulnerability status", {"service": "checkout"}),
    ],
)
print(result.first().explain())
```

The tree identifies the concrete result and rule, supporting evidence, and the successful
negation-as-failure check. An absent positive fact is not a stored classical negative. For a policy
example with multiple evidence sources and blockers, run `python examples/release_gate.py`.

`solution.explain()` applies the solution's query bindings, so variable names are replaced with their
resolved values. `solution.proof.explain()` accepts optional bindings directly, and
`solution.proof.render()` remains a compatibility alias for the tree renderer.

## Proof versus global trace

A solution carries its successful branch-local proof:

```python
solution.proof
solution.explain()
```

The run carries a global trace:

```python
result.steps
```

The trace can include failed candidates, unsuccessful unifications, negation attempts, and search
cutoffs that do not belong to the final proof. Use the proof to answer “why this result?” and the
trace to answer “what did the resolver try?”

## Provenance

Applications can attach source metadata to a `Fact` or use the compatible `KnowledgeBase.add_fact()`
interface:

```python
from inferlingo import Fact, Provenance

fact = Fact(
    "Function {fn} catches a broad exception",
    {"fn": "process_order"},
    provenance=Provenance(
        source="orders.py",
        line=81,
        kind="python-ast",
    ),
)
```

When the fact participates in a solution, its provenance is retained on the corresponding proof
step and shown as evidence in the explanation. `Provenance` contains `source`, `line`, `kind`, and
arbitrary application `metadata`. The application owns the meaning and accuracy of this evidence.

Rule clauses also retain source path and line. Named rule identity appears in explanations, making
`via rule: release-ready` more useful than a bare line number while preserving the file location.

## Semantic proof metadata

A semantic proof step can additionally carry method, confidence, individual checks, request IDs,
backend usage, and cache status. `Solution.semantic_confidences` and
`minimum_semantic_confidence` expose the confidence signals from semantic steps. These are backend
diagnostics, not mathematical probabilities assigned to the full theorem.

## Report actionable failure reasons

Backward-chaining proofs explain successful answers; absence of an answer is not a ready-made
“why-not” report. For policy reporting, derive positive blockers explicitly:

```text
{service} has blocker "tests failing" if
    {service} has failing tests.

{service} has blocker "release freeze" if
    {service} is frozen.
```

Then query `{service} has blocker {reason}?`. The resulting blocker facts have ordinary proofs and
can carry the same evidence provenance as any other derivation. See [Rule modeling patterns](patterns.md).

## Deterministic analyzer + policy pattern

The Python linter remains an advanced example of this boundary:

```text
Python AST
    |
    | deterministic observations
    v
Fact values with source provenance
    |
    | exact .nl rules
    v
derived finding + proof
```

Python performs source inspection and emits facts. InferLingo applies separately maintained rules
and returns findings whose proofs show which source observations supported them. This is an embedding
pattern, not a claim that InferLingo itself analyzes source code.
