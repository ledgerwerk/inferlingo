from __future__ import annotations

from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

ROOT = Path(__file__).parents[1]


def test_documentation_tree_is_present() -> None:
    expected = {
        "index.md",
        "getting-started.md",
        "concepts.md",
        "patterns.md",
        "language.md",
        "python-api.md",
        "cli.md",
        "semantic-unification.md",
        "proofs-and-provenance.md",
        "examples.md",
        "debugging.md",
        "development.md",
        "changelog.md",
    }
    assert expected <= {path.name for path in (ROOT / "docs").iterdir()}
    assert {"index.md", "api.md", "engine.md", "models.md", "parser.md", "unifier.md"} <= {
        path.name for path in (ROOT / "docs" / "api").iterdir()
    }


def test_docs_root_has_navigation() -> None:
    index = (ROOT / "docs" / "index.md").read_text(encoding="utf-8")
    assert "```{toctree}" in index
    assert ":hidden:" in index
    for page in ("getting-started", "concepts", "patterns", "language", "python-api", "api/index"):
        assert page in index


def test_readme_has_release_install_and_exact_quickstart() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "pip install inferlingo" in readme
    assert "--exact-only" in readme
    assert "inferlingo[jev]" in readme
    assert ".[dev,docs]" in readme


def test_docs_extra_is_not_a_runtime_dependency() -> None:
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = metadata["project"]
    assert project["optional-dependencies"]["docs"]
    assert not any(name.startswith(("sphinx", "myst-parser")) for name in project["dependencies"])
