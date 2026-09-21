# Python API

Use `KnowledgeBase` for normal application embedding. It owns a parsed collection of clauses and
uses exact unification by default.

## `KnowledgeBase`

```python
from inferlingo import KnowledgeBase

kb = KnowledgeBase.from_file("rules.nl")
result = await kb.ask("{person} may deploy?")
```

`KnowledgeBase.from_text()` and `from_file()` create a knowledge base, parse input in strict mode
by default, and accept an optional custom unifier. The default is `ExactUnifier`, so no network or
semantic backend is used unless one is supplied explicitly.

Use `add_text()` to parse and append more facts or rules. The read-only `program` property returns
the current `Program` view.

## Safe fact injection

Use `add_fact()` when an application has a value to inject into a sentence template:

```python
from inferlingo import KnowledgeBase, Provenance

kb = KnowledgeBase.from_text("URL {url} is approved if URL {url} is reachable.")
kb.add_fact(
    "URL {url} is reachable",
    url="https://example.com/a?x=1&y=2",
    provenance=Provenance(source="scanner.py", line=41, kind="http-check"),
)
```

Injected values become quoted opaque atoms. The application does not need to escape NL syntax in
the value. If a template variable has no supplied value, `add_fact()` raises `ValueError`. The
template must represent a fact, not a rule.

## Async and sync queries

Use the async API in an async application:

```python
result = await kb.ask("{person} may deploy?")
```

For synchronous application code, use:

```python
result = kb.ask_sync("{person} may deploy?")
```

`ask_sync()` runs the async query outside an active event loop. Calling it from a running event
loop raises `RuntimeError`; use `await ask()` there.

## Search limits

Pass positive bounds when a rule graph needs explicit limits:

```python
result = await kb.ask(
    query,
    max_depth=25,
    max_steps=2000,
    max_solutions=50,
)
```

Inspect `result.truncated` before treating a result set as complete.

## Results

A `RunResult` exposes:

- `solutions`: successful answers;
- `steps`: the global resolver trace;
- `stats`: aggregate counters;
- `truncated`: whether a search limit stopped exploration.

Each `Solution` exposes:

- `bindings`: query variable values;
- `answer`: the rendered answer;
- `proof`: the successful branch-local proof;
- `semantic_confidences`: confidence signals from semantic proof steps;
- `minimum_semantic_confidence`: the lowest such signal, or `None`.

Semantic confidence is backend diagnostic metadata, not theorem probability.

## Lower-level API

Tooling that needs explicit parsed models or a custom unifier can use the lower-level API:

```python
from inferlingo import ExactUnifier, NLEngine, parse_program, parse_query

program = parse_program("Alice is known.")
query = parse_query("Alice is known?")
result = await NLEngine(program, ExactUnifier()).run(query)
```

See the [API reference](api/index.md) for signatures and model details.
