# CLI guide

The CLI validates rule programs, evaluates exact or semantically assisted queries, composes separate
rule and runtime-fact files, and runs offline scenario suites.

## `inferlingo validate FILE`

Validation parses one program with strict safety checks and never contacts Jev:

```bash
inferlingo validate examples/release_policy.nl
```

A valid result reports fact and rule-clause counts, for example `ok: 5 facts, 1 rule clauses`. File,
syntax, and rule-safety errors exit with code 2.

## `inferlingo run FILE QUERY`

Run a query against a program, preserving the existing positional invocation:

```bash
inferlingo run examples/birds.nl "{bird} can fly?" --exact-only
```

Use `--rules FILE` to add rule files and `--facts FILE` to add runtime fact files. Repeat either flag
to compose multiple sources; fact files may contain facts only:

```bash
inferlingo run policies/release.nl "checkout is release-ready?" \
  --rules policies/security.nl \
  --facts build_facts.nl --facts scanner_facts.nl \
  --exact-only --explain
```

The primary positional file and `--rules` files make up the reusable program; `--facts` clauses are
runtime evidence for this run and are not persisted. Static facts are accepted in rule files for
compatibility.

The CLI `run` backend defaults to `PyJevUnifier`. Pass `--exact-only` to select deterministic
`ExactUnifier`, available in the base installation and guaranteed not to contact a semantic backend.
The Python `KnowledgeBase` and `RuleSet` APIs default to exact unification unless a caller supplies
another unifier.

## `inferlingo test PROGRAM CASES.toml`

Test a rule pack without Python collector code or semantic-backend calls:

```bash
inferlingo test examples/release_policy.nl examples/release_policy.cases.toml
```

Use `--rules FILE` one or more times to compose additional rule files. The scenario suite is always
exact/offline. TOML uses `schema = 1` and one or more `[[case]]` tables. Each case requires a `name`,
a `query`, and exactly one expected result:

```toml
schema = 1

[[case]]
name = "healthy service is ready"
query = "checkout is release-ready?"
expect = true
facts = [
  "checkout has passing tests.",
  "checkout has an approved change.",
  "checkout has acceptable vulnerability status.",
]

[[case]]
name = "collect blocker bindings"
query = "checkout has blocker {reason}?"
expect_bindings = [
  { reason = "critical vulnerabilities" },
]
facts = ["checkout has critical vulnerabilities."]
```

`expect` must be a boolean. `expect_bindings` is an array of string-to-string maps and is compared
without depending on solution order. Optional `facts` is an array of sentence strings; each entry
must parse as one ground fact. Cases are independent and do not share runtime facts.

Scenario command exit codes: 0 when all expectations pass, 1 when one or more expectations fail, and
2 for invalid input, TOML, or scenario structure. Failed cases print the expected and actual result.

## Output modes

Default human output reports `Yes.` or `No.` for a ground query, bindings for a variable query, and
`No solutions.` for an unmatched variable query. A valid query with no solutions is not a CLI failure.

Options:

- `--explain` prints an instantiated proof for each successful solution, including named rule
  identity, source evidence, provenance, and negation-as-failure details.
- `--trace` prints resolver and unification attempts, including failures and cutoffs.
- `--debug` is a compatibility alias for `--trace`.
- `--stats` prints aggregate counters.
- `--json` emits structured `solutions`, `trace`, `truncated`, and `stats` data. Each solution
  contains `bindings`, `answer`, and `proof`; JSON is preferred for automation.

## Semantic options

When semantic mode is enabled, configure `--model`, `--concurrency` (default 8),
`--semantic-batch-size` (default 32), and `--cache-size` (default 2048). These options are irrelevant
with `--exact-only` and to `inferlingo test`.

## Search limits

The resolver options are `--max-depth` (default 25), `--max-steps` (default 2000), and
`--max-solutions` (default 50). A warning is printed when search is truncated. No proof found is not
itself a CLI failure; inspect `--trace` and the truncation status.

## Exit codes

For `run`, exit 0 means the query completed (including no solutions), exit 1 indicates a semantic
backend or execution/runtime failure, exit 2 indicates invalid input or parse/safety failure, and
130 indicates interruption. `test` uses the separate expectation-failure code described above.
