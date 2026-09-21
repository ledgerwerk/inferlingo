"""InferLingo public API."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version

from .api import KnowledgeBase
from .engine import NLEngine
from .errors import InferLingoError, RuleSafetyError, UnsafeNegationError
from .models import (
    BackendUsage,
    Check,
    Clause,
    Literal,
    Program,
    Proof,
    ProofStep,
    Provenance,
    Query,
    RunResult,
    RunStats,
    Solution,
    Unification,
)
from .parser import ParseError, parse_program, parse_query
from .terms import Atom, Sentence, Variable
from .unifier import ExactUnifier, PyJevUnifier, Unifier

try:
    from ._version import __version__
except ImportError:  # source checkout without generated setuptools-scm output
    try:
        __version__ = package_version("inferlingo")
    except PackageNotFoundError:
        __version__ = "0.0.0"

__all__ = [
    "Atom",
    "BackendUsage",
    "Check",
    "Clause",
    "ExactUnifier",
    "InferLingoError",
    "KnowledgeBase",
    "Literal",
    "NLEngine",
    "ParseError",
    "Program",
    "Proof",
    "ProofStep",
    "Provenance",
    "PyJevUnifier",
    "Query",
    "RunResult",
    "RunStats",
    "Sentence",
    "Solution",
    "Unification",
    "Unifier",
    "UnsafeNegationError",
    "Variable",
    "RuleSafetyError",
    "__version__",
    "parse_program",
    "parse_query",
]
