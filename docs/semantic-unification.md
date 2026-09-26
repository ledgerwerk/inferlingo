# Semantic unification

Semantic unification is an optional interoperability aid for applications that already have candidate
facts. It is not general natural-language understanding, extraction, classification, or policy reasoning.
Install it with:

```bash
python -m pip install 'inferlingo[jev]'
```

Authentication and provider configuration belong to pyjev and its underlying Jev SDK. InferLingo
does not define a second credential system.

## Exact first

`PyJevUnifier` first attempts deterministic wording unification. Only differently worded candidate
pairs reach semantic evaluation. Enabling semantic mode therefore does not replace exact logic.

## Security boundary

For authorization, payments, destructive infrastructure changes, and other high-consequence decisions,
use exact facts and explicit rules by default. Semantic unification can reconcile wording, but an
ambiguous same-fact judgment must not silently authorize an action. Keep `ExactUnifier` for policy
enforcement unless your application deliberately validates and gates semantic evidence.

Semantic matching is intended for same-fact equivalence, including possible paraphrases, synonyms,
and different word order. It should reject merely related statements, one-way implication,
more-specific or more-general statements, and participant or role swaps.

For example:

```text
Lisa's dad is Homer.
```

may semantically match:

```text
Homer is the father of Lisa.
```

An explicit rule is still needed for:

```text
{parent} is a parent of {child} if
    {parent} is the father of {child}.
```

The semantic backend may bridge the fact to the father wording. InferLingo's explicit rule derives
the parent relation. The backend must not invent that implication.

## Verification and confidence

A `Unification` preserves its method, confidence, individual `Check` values, backend usage, request
IDs when available, and cache status. A semantic `ProofStep` can carry the same diagnostic data.
`Solution.semantic_confidences` and `minimum_semantic_confidence` expose confidence signals from
semantic proof steps.

These values describe backend judgments and checks. They are not probabilities that the complete
logical theorem is true. The application decides what policy to apply.

## Configuration

```python
from inferlingo import PyJevUnifier

unifier = PyJevUnifier(
    jev=None,
    model=None,
    align_threshold=0.30,
    match_threshold=0.70,
    concurrency=8,
    cache_size=2048,
    semantic_batch_size=32,
)
```

The alignment threshold is a permissive early filter. The match threshold is used in stricter
verification. Changing either threshold changes backend policy, not the meaning of a logical proof.
Concurrency bounds backend work, batch size bounds candidates grouped into semantic batches, and
cache size bounds in-memory semantic results.

## Batching

When the injected pyjev client exposes the batch interface, candidates use a bounded two-phase
process:

1. alignment and variable-binding questions;
2. relation and participant verification for survivors.

This can evaluate multiple candidates in two backend requests rather than one independent request
sequence per candidate. Injected clients without the interface use the available fallback.

## Cache

Semantic results are held in a bounded in-memory cache scoped to the unifier instance and its
configuration. The cache is not persistent across processes.

## Resource ownership

When `PyJevUnifier` creates its own pyjev client, `close()` closes it. An injected `jev=` client is
caller-owned and is not closed by the unifier.

Use the async context manager when the unifier owns its client:

```python
async with PyJevUnifier() as unifier:
    ...
```
