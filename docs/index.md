# InferLingo

**Readable rules over facts your application already knows.**

InferLingo is a small Python logic engine whose facts and rules look like ordinary sentences. Use
Python or another deterministic subsystem to establish facts, let InferLingo derive consequences
from explicit rules, and optionally use semantic unification when two differently worded sentences
may express the same fact.

```text
Python computes facts
        |
        v
InferLingo applies explicit rules
        |
        v
optional semantic unifier compares wording
        |
        v
your application decides what to do
```

InferLingo is not a general natural-language interpreter, chatbot, planner, source-code analyzer,
arithmetic engine, or action runner. Semantic unification compares candidate statements as a
possible same fact. It does not invent rules or implications.

## First exact workflow

Install the base package and run the deterministic birds example:

```bash
python -m pip install inferlingo
inferlingo run examples/birds.nl "{bird} can fly?" --exact-only --explain
```

The result includes the binding `bird = Tweety`. InferLingo used only the fact and rules in the
program. The `--explain` option exposes the successful proof path.

For a practical policy example, see [Getting started](getting-started.md). For the language
syntax, see the [Language reference](language.md).

## Choose a guide

- [Getting started](getting-started.md): install, validate, and run an access policy.
- [Concepts](concepts.md): facts, rules, queries, resolution, and bounded search.
- [Language reference](language.md): statements, variables, rules, conjunction, alternatives,
  negation, quoted atoms, comments, and strict safety.
- [Python API](python-api.md): embed `KnowledgeBase`, inject facts, and inspect results.
- [CLI guide](cli.md): commands, output modes, backend options, limits, and exit codes.
- [Semantic unification](semantic-unification.md): optional same-fact matching through pyjev.
- [Proofs and provenance](proofs-and-provenance.md): inspect why a result exists.
- [Examples](examples.md): runnable examples and the Python linter architecture.
- [Debugging](debugging.md): parse errors, traces, truncation, and semantic diagnostics.
- [API reference](api/index.md): generated signatures and docstrings.
- [Development](development.md): contributor setup, checks, tests, and versioning.

```{toctree}
:maxdepth: 2
:hidden:

getting-started
concepts
language
python-api
cli
semantic-unification
proofs-and-provenance
examples
debugging
api/index
development
changelog
```
