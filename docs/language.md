# Language reference

InferLingo programs contain facts and rules. Use one or more lines for a statement and end each
statement with `.`. Queries conventionally end with `?`. The parser strips a terminal `.`, `?`, or
`!` outside quotes. A final pending statement can be consumed without a period, but delimiters are
recommended when several statements are present.

## Facts

Facts must be ground in strict mode:

```text
Tweety is a canary.
Alice completed deployment training.
"database" is unavailable.
```

## Variables

Prefer descriptive braced variables:

```text
{person}
{service}
{dependency}
{function_name}
```

Compatibility variables use single capital letters, optionally followed by digits:

```text
X
Y
Z
X1
Y3
```

`A` and `I` are ordinary English words, not variables. Braced variables are clearer in new rules
and queries.

## Rule forms

The following forms parse to the same clause model:

```text
{bird} can fly if {bird} is a bird.
If X is a canary then X is a bird.
{person} may deploy when {person} is approved.
```

## Conjunction

Use `and`, commas, or semicolons between conditions:

```text
{person} may deploy if
    {person} is an employee and
    {person} completed deployment training.
```

## Alternatives

`or` creates alternative rule clauses, each with the same head:

```text
X may enter if X has a badge or X is escorted.
```

Queries can also contain alternatives.

## Negation

Use `not` before a condition:

```text
{person} is trusted if
    {person} is known and
    not {person} is blocked.
```

Strict safety requires variables in negative conditions to also occur in a positive body condition.
An unbound negative query such as `not X is blocked?` is rejected at execution with
`UnsafeNegationError`. A rule head cannot be negated.

## Quoted atoms

Use quoted atoms for opaque application values:

```text
Artifact "https://example.com/a" is reachable.
User "john@example.com" is active.
Version "3.14.2" is deployed.
Path "/srv/app/config.yaml" exists.
```

Punctuation and spaces are preserved. Keywords and comment markers inside quotes are ordinary data.
The escapes `\"` and `\\` are supported.

## Comments

Outside quoted values, comments begin with any of:

```text
# comment
% comment
// comment
```

## Strict safety rules

Strict mode is the default for `parse_program()` and `KnowledgeBase`:

1. Facts must be ground.
2. Every variable in a rule head must occur in a positive body condition.
3. Every variable in a negative body condition must occur in a positive body condition.

Invalid fact:

```text
{person} is active.
```

Correct fact:

```text
Alice is active.
```

Invalid head-only variable:

```text
{person} can access production if system is online.
```

Correct rule:

```text
{person} can access production if
    {person} is approved and
    system is online.
```

Invalid negative-only variable:

```text
{person} is trusted if not {resource} is blocked.
```

Correct rule:

```text
{person} is trusted if
    {person} is known and
    not {person} is blocked.
```

Use `strict=False` only when a caller explicitly needs the parser's less restrictive mode. It is
not the normal solution for unsafe rules.
