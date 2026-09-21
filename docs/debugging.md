# Debugging

## Parse and safety errors

Start with validation:

```bash
inferlingo validate rules.nl
```

Errors include the source and line where available. Common causes include:

- unterminated quotes;
- invalid named variables;
- non-ground facts in strict mode;
- head-only variables;
- negative-only variables;
- a negated rule head;
- an empty program.

Strict mode requires ground facts, range-restricted rule heads, and range-restricted negative body
conditions. Fix the program rather than making unsafe parsing the normal workflow.

## `No.` versus runtime failure

A query with no solution is a valid result and exits 0. A semantic backend or other runtime failure
exits 1. Invalid files, syntax errors, and safety errors exit 2. This distinction is important for
automation.

## Trace

Use the exact backend while investigating deterministic resolution:

```bash
inferlingo run rules.nl "..." --exact-only --trace
```

The trace shows attempts, bindings, methods, confidence where applicable, notes, and cutoffs. Use
`--debug` as the compatibility alias for `--trace`.

## Truncation

If `result.truncated` is true or the CLI prints its truncation warning, a configured search limit
stopped exploration. Inspect the trace and increase the relevant bound only when the rule graph
legitimately needs it. Fix accidental recursion instead of blindly increasing limits.

## Semantic debugging

When semantic mode behaves unexpectedly:

1. Confirm the logical implication is represented by an explicit rule.
2. Inspect whether the disputed proof step is exact or `jev`.
3. Inspect individual semantic checks and confidence values.
4. Verify that participant roles were not swapped.
5. Inspect the configured model and thresholds.
6. Remember that the cache is local to the unifier instance.
