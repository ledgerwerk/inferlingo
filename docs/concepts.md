# Concepts

InferLingo is a bounded derivation and policy engine over facts supplied by your application. Python,
scanners, APIs, and other deterministic systems establish observations; explicit rules derive
consequences; proofs can retain links to the input evidence. InferLingo does not fetch facts, perform
arithmetic, interpret arbitrary prose, or choose actions.

```text
trusted fact collection -> explicit rules -> derived result + proof -> application decision
```

## Separate rules from runtime facts

`RuleSet` represents reusable, parsed rules. Each call to `RuleSet.ask()` evaluates against a fresh
fact set, so evidence from one build, service, or request does not leak into another. `Fact` is a
structured, safely quoted application observation and may carry `Provenance`. Use `rules.session()`
when several queries should share facts for one evaluation context.

`KnowledgeBase` remains supported as a mutable collection of rules and facts. It is convenient for
small programs and backwards compatibility; `RuleSet` plus `Fact` makes the application lifecycle
explicit. See the [Python API](python-api.md).

## Facts

A fact is a ground sentence with no variables:

```text
Alice is an employee.
"database" is unavailable.
```

Strict mode rejects variables in facts. Applications can inject structured ground values with
`Fact` or `KnowledgeBase.add_fact()`; values are encoded as opaque quoted atoms rather than parsed as
rule-language syntax.

## Rules

A rule derives its head when every body condition succeeds:

```text
{bird} can fly if {bird} is a bird.
```

Rules encode explicit logical relationships. Rule packs can have stable identities and human-readable
descriptions using comment directives:

```text
# @rule release-ready
# @description Require passing CI, approval, acceptable security status, and no release freeze.
{service} is release-ready if
    {service} has passing tests and
    {service} has an approved change and
    {service} has acceptable vulnerability status and
    not {service} is frozen.
```

Names and descriptions appear in proof explanations; ordinary comments remain comments. Semantic
unification may recognize two differently worded statements as the same fact, but it does not create
missing implications.

## Queries

A ground query asks for a yes/no result:

```text
Alice is known?
```

A variable query returns bindings:

```text
{person} is known?
```

Conjunctive queries require all conditions; alternatives accept either branch:

```text
{person} is known and {person} has a badge?
{person} has a badge or {person} is escorted?
```

## Exact unification

Exact unification is deterministic and offline. It matches the same fixed wording while binding
variables. A variable can bind a multi-word phrase:

```text
X is the father of Bart
```

matches `Homer Simpson is the father of Bart`, with `X = Homer Simpson`. Exact does not mean
byte-for-byte equality; it means structural matching of the same wording. It does not guess that
different fixed words are equivalent.

## Semantic unification

Optional semantic mode is a fallback for differently worded candidate facts. For example, `Lisa's dad is Homer` may match `Homer is the father of Lisa`. It must not turn that statement into `Homer is a parent of Lisa`; that relation requires an explicit rule. See [Semantic unification](semantic-unification.md).

## Negation as failure

A negative condition succeeds when the corresponding positive goal cannot be proved for the current
bindings:

```text
{person} is trusted if
    {person} is known and
    not {person} is blocked.
```

This is not classical logic negation and does not store a negative fact. Variables in a negative goal
must already be bound by a positive condition. The resolver selects safe positive goals before
negation; an unsafe unbound negative query raises `UnsafeNegationError`.

For operational decisions, do not rely on a missing success as a friendly explanation of failure.
Model actionable failure reasons as positive derived facts instead:

```text
{service} has blocker "release freeze" if
    {service} is frozen.
```

Then query `{service} has blocker {reason}?` to get explicit, auditable reasons. More patterns are in
[Rule modeling patterns](patterns.md).

## Recursion

Rules can refer to consequences derived through other rules. The service outage example propagates an
unavailable dependency through the catalog, deriving the downstream blast radius. Variant recursion is
cut off when the same goal shape is already active, preventing simple self-recursive loops from
expanding forever.

## Proof versus trace

Each `Solution` contains a branch-local `Proof` for its successful answer. `solution.explain()` renders
an instantiated explanation with rule identity, supporting conditions, and evidence provenance. A
successful negative condition is described explicitly as negation-as-failure. The `RunResult` also
contains `steps`, a global trace of resolver and unification attempts; it can include failed candidates
and cutoffs that are not part of the final proof.

## Bounded search

Resolution is deliberately bounded:

- `max_depth` defaults to 25.
- `max_steps` defaults to 2000.
- `max_solutions` defaults to 50.
- `RunResult.truncated` reports that a bound stopped exploration.

Once a bound is reached, do not assume the search was complete. Inspect the trace and increase a limit
only when the rule graph legitimately needs it.
