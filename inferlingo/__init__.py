"""InferLingo public API."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version

from .engine import NLEngine
from .models import Clause, Literal, Program, Query, RunResult, Solution, Unification
from .parser import ParseError, parse_program, parse_query
from .unifier import ExactUnifier, PyJevUnifier, Unifier

try:
    from ._version import __version__
except ImportError:  # source checkout without generated setuptools-scm output
    try:
        __version__ = package_version("inferlingo")
    except PackageNotFoundError:
        __version__ = "0.0.0"

__all__ = [
    "Clause",
    "ExactUnifier",
    "Literal",
    "NLEngine",
    "ParseError",
    "Program",
    "PyJevUnifier",
    "Query",
    "RunResult",
    "Solution",
    "Unification",
    "Unifier",
    "__version__",
    "parse_program",
    "parse_query",
]
