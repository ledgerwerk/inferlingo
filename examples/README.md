# InferLingo examples

Run the deterministic examples without credentials:

```bash
inferlingo run examples/birds.nl "{bird} can fly?" --exact-only --explain
inferlingo run examples/access_policy.nl "{person} may deploy?" --exact-only --explain
inferlingo run examples/dependency_impact.nl "{service} is affected?" --exact-only --explain
```

`family.nl` demonstrates the semantic boundary. The explicit rule says that a father is a parent; only the paraphrase `Lisa's dad is Homer` may need a semantic unifier. `python_linter.py` shows how Python and the AST produce exact facts before InferLingo derives findings.
