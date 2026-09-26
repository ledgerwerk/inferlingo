# Python API

For application policy, use immutable `RuleSet` objects with structured `Fact` inputs and isolated
`Session` evaluations. `KnowledgeBase` remains public for mutable workflows and v0.1 compatibility.
Python APIs use `ExactUnifier` by default, so these examples are deterministic and offline.

## `Fact`: structured application evidence

A `Fact` contains a sentence template, a mapping of variable values, optional application-owned
provenance, and an optional source label:

```python
from inferlingo import Fact, Provenance

fact = Fact(
    "URL {url} is reachable",
    {"url": "https://example.com/a?x=1&y=2"},
    provenance=Provenance(source="scanner.json", line=41, kind="http-check"),
    source="runtime-scan",
)
print(fact.render())
```

Values are quoted as opaque atoms; URL punctuation, spaces, quotes, and NL comment characters cannot
become rule syntax. The fact's mapping is copied and read-only. Missing values or a template that
parses as a rule are rejected when the fact is added to an evaluation.

## Reusable rules with `RuleSet`

```python
from inferlingo import ExactUnifier, Fact, Provenance, RuleSet

rules = RuleSet.from_file("release_policy.nl", unifier=ExactUnifier())
facts = [
    Fact(
        "{service} has passing tests",
        {"service": "checkout"},
        provenance=Provenance(source="ci/test-results.json", line=1, kind="ci"),
    ),
    Fact("{service} has an approved change", {"service": "checkout"}),
    Fact("{service} has acceptable vulnerability status", {"service": "checkout"}),
]
result = rules.ask_sync("{service} is release-ready?", facts=facts)

if result.matched:
    print(result.values("service"))
    print(result.first().explain())
```

`RuleSet` is immutable. `from_text()` and `from_file()` parse one rules source; `from_files()` composes
multiple rule files while preserving each source path on its clauses. `RuleSet.ask()` and
`RuleSet.ask_sync()` accept runtime `facts` and create a fresh evaluation for every call. Facts from
one call are not retained by the rule set or visible to later calls.

```python
rules = RuleSet.from_files("base.nl", "security.nl", "release.nl")
```

Use `await rules.ask(query, facts=facts)` from async code. `ask_sync()` is for synchronous code outside
a running event loop; inside an event loop, await the async method.

## Multiple queries with `Session`

A `Session` holds runtime facts for one evaluation context and supports multiple queries over the same
facts:

```python
session = rules.session()
session.add_facts(facts)
ready = session.ask_sync("checkout is release-ready?")
blockers = session.ask_sync("checkout has blocker {reason}?")
```

Sessions are isolated from one another. `add_fact()` accepts one `Fact`; `add_facts()` accepts an
iterable. A session can be discarded when its request/build evaluation is complete. Its
`program` property shows the combined immutable view of static rules and runtime facts.

## `KnowledgeBase` compatibility API

`KnowledgeBase` is a mutable collection of rules and facts and remains supported:

```python
from inferlingo import KnowledgeBase, Provenance

kb = KnowledgeBase.from_text(
    """
    Alice is an employee.
    {person} may deploy if {person} is an employee.
    """
)
kb.add_fact(
    "URL {url} is reachable",
    url="https://example.com/a?x=1&y=2",
    provenance=Provenance(source="scanner.py", line=41, kind="http-check"),
)
result = kb.ask_sync("{person} may deploy?")
```

`from_text()` and `from_file()` parse in strict mode by default. Use `add_text()` to append more facts
or rules. `add_fact()` safely quotes each injected value and accepts keyword values corresponding to
template variables. The read-only `program` property returns the current `Program` view.

## Results and explanations

A `RunResult` provides:

- `matched`: whether at least one solution exists;
- `first()`: the first `Solution`, or `None`;
- `values(variable)`: values bound to a query variable, in solution order;
- `solutions`: all successful answers;
- `steps`: the global resolver trace;
- `stats`: aggregate counters;
- `truncated`: whether a search bound stopped exploration.

A `Solution` exposes `bindings`, rendered `answer`, branch-local `proof`, and `explain()`. The
explanation applies final query bindings and shows named rule applications, supporting evidence,
source provenance, and negation-as-failure. `Proof.render()` is retained as a compatibility entry
point to the same tree renderer.

Semantic confidence values on a `Solution` are backend diagnostics, not probabilities that the full
logical result is true. The application decides whether and how to gate on semantic evidence.

## Search limits

Pass positive bounds when a legitimate rule graph needs explicit limits:

```python
result = await rules.ask(
    query,
    facts=facts,
    max_depth=25,
    max_steps=2000,
    max_solutions=50,
)
```

Inspect `result.truncated` before treating a bounded search as complete.

## Lower-level API

Tooling that needs explicit parsed models or a custom unifier can use the lower-level API:

```python
from inferlingo import ExactUnifier, NLEngine, parse_program, parse_query

program = parse_program("Alice is known.")
query = parse_query("Alice is known?")
result = await NLEngine(program, ExactUnifier()).run(query)
```

See the [API reference](api/index.md) for signatures and model details.
