# Development

## Setup

Install the package with development and documentation dependencies:

```bash
python -m pip install -e '.[dev,docs]'
```

## Quality checks

```bash
python -m compileall inferlingo examples docs
pytest
ruff check .
python docs/make.py html
python -m build
twine check dist/*
```

`python docs/make.py linkcheck` is an additional connected-CI check. The ordinary test suite and
exact examples do not require a live semantic API.

## Tests

Exact inference tests are offline. Semantic-unifier tests use fake or injected clients; no test
should require a real API key. Executable documentation examples should prefer exact behavior.
Semantic documentation examples may be illustrative unless they use a fake backend.

## Versioning

Versions come from Git tags through setuptools-scm. v0.1.0 was released from tag `v0.1.0` on 2026-09-21, and the planned next release is `v0.1.1`.
`inferlingo/_version.py` is generated and must not be edited by hand. Development versions should resolve from the Git tag state.

## Changelog

Releaseledger owns `docs/changelog.md`. Add release records and entries through releaseledger, then
regenerate the file with its changelog build command. Do not paste release prose directly into the
generated file.
