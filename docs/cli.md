# CLI guide

The `inferlingo` command validates programs and runs queries.

## `inferlingo validate FILE`

Validation parses a program with strict safety checks and never contacts Jev:

```bash
inferlingo validate examples/access_policy.nl
```

A valid result reports fact and rule-clause counts, for example:

```text
ok: 5 facts, 1 rule clauses
```

File, syntax, and rule-safety errors exit with code 2.

## `inferlingo run FILE QUERY`

Run a query against a program:

```bash
inferlingo run examples/birds.nl "{bird} can fly?" --exact-only
```

The CLI backend defaults to `PyJevUnifier`. Pass `--exact-only` to select deterministic
`ExactUnifier`, which is available in the base installation and never contacts a semantic backend.

The Python `KnowledgeBase` API has a different default: it uses `ExactUnifier` unless a caller
supplies another unifier.

## Output modes

Default human output is:

- `Yes.` or `No.` for a ground query;
- `SOLUTIONS` and bindings for a variable query;
- `No solutions.` when a variable query has no solutions.

Options:

- `--explain` prints the successful proof for each solution.
- `--trace` prints every resolver and unification attempt, including failures and cutoffs.
- `--debug` is a compatibility alias for `--trace`.
- `--stats` prints aggregate counters.
- `--json` returns stable structured `solutions`, `trace`, `truncated`, and `stats` data. Each
  solution contains `bindings`, `answer`, and `proof`; JSON is preferred for automation.

## Semantic options

When semantic mode is enabled, configure:

- `--model` for the Jev model override;
- `--concurrency`, default 8;
- `--semantic-batch-size`, default 32;
- `--cache-size`, default 2048.

## Search limits

The resolver options are:

- `--max-depth`, default 25;
- `--max-steps`, default 2000;
- `--max-solutions`, default 50.

A warning is printed when search is truncated. No proof found is not itself a CLI failure.

## Exit codes

| Exit | Meaning                                                          |
| ---: | ---------------------------------------------------------------- |
|    0 | The command completed, including a valid query with no solutions |
|    1 | Semantic backend or execution/runtime failure                    |
|    2 | Invalid file, parse error, or rule-safety error                  |
|  130 | Interrupted by the user                                          |
