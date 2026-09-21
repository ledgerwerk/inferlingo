# Concepts

InferLingo resolves sentence-shaped goals against explicit facts and rules. The resolver is
bounded and produces both successful branch-local proofs and a global trace.

## Facts

A fact is a ground sentence with no variables:

```text
Alice is an employee.
"database" is unavailable.
```

Strict mode rejects variables in facts. Applications can inject ground values safely through
`KnowledgeBase.add_fact()`.

## Rules

A rule derives a head when every body condition succeeds:

```text
{bird} can fly if {bird} is a bird.
```

Rules are explicit logical relationships. Semantic unification may recognize that two sentences
say the same fact, but it does not create missing implications.

## Queries

A ground query asks for a yes/no result:

```text
Alice is known?
```

A variable query returns bindings:

```text
{person} is known?
```

A conjunctive query requires all conditions:

```text
{person} is known and {person} has a badge?
```

An alternative query accepts either branch:

```text
{person} has a badge or {person} is escorted?
```

## Exact unification

Exact unification is deterministic and offline. It matches the same fixed wording while binding
variables. A variable can bind a multi-word phrase:

```text
X is the father of Bart
```

matches:

```text
Homer Simpson is the father of Bart
```

with `X = Homer Simpson`. Exact does not mean byte-for-byte string equality. It means structural
matching of the same wording, with variable binding. It does not guess that different fixed words
are equivalent.

## Semantic unification

Semantic mode is a fallback for differently worded candidate facts. For example:

```text
Lisa's dad is Homer.
```

may match:

```text
Homer is the father of Lisa.
```

It must not turn the second statement into:

```text
Homer is a parent of Lisa.
```

That relation requires an explicit rule. See [Semantic unification](semantic-unification.md).

## Negation as failure

A negative condition succeeds when the corresponding positive goal cannot be proved for the current
bindings:

```text
{person} is trusted if
    {person} is known and
    not {person} is blocked.
```

This is not classical logic negation and does not store a negative fact. Variables in a negative
goal must already be bound by a positive condition. The resolver selects safe positive goals before
negation; an unsafe unbound negative query raises `UnsafeNegationError`.

## Recursion

Rules can refer to consequences derived through other rules. `examples/dependency_impact.nl` uses
quoted service names and recursive dependency propagation. Variant recursion is cut off when the
same goal shape is already active, preventing simple self-recursive loops from expanding forever.

## Proof versus trace

Each `Solution` contains a branch-local `Proof` showing the successful path for that answer. A
`RunResult` also contains `steps`, the global trace of resolver and unification attempts. The trace
can include failed candidates and cutoffs that are not part of the final proof.

## Bounded search

Resolution is deliberately bounded:

- `max_depth` defaults to 25.
- `max_steps` defaults to 2000.
- `max_solutions` defaults to 50.
- `RunResult.truncated` reports that a bound stopped exploration.

Once a bound is reached, do not assume the search was complete. Inspect the trace and increase a
limit only when the rule graph legitimately needs it.
