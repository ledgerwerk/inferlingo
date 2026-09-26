"""Command-line interface for InferLingo."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib
import json
from dataclasses import asdict
from pathlib import Path

import typer

from . import __version__
from .engine import NLEngine
from .models import Clause, Program
from .parser import ParseError, parse_program, parse_query
from .terms import variables_in
from .unifier import ExactUnifier, PyJevUnifier

app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    help="Natural-language logic with pluggable semantic unification.",
)
PROGRAM_ARGUMENT = typer.Argument(..., exists=True, dir_okay=False, readable=True)
QUERY_ARGUMENT = typer.Argument(..., help='Goal syntax, e.g. "X is a grandfather of Bart?"')
CASES_ARGUMENT = typer.Argument(..., exists=True, dir_okay=False, readable=True)


def _load_input_program(rule_paths: Iterable[Path], fact_paths: Iterable[Path]) -> Program:
    clauses: list[Clause] = []
    rule_files = tuple(rule_paths)
    if not rule_files:
        raise ValueError("at least one rule file is required")
    for path in rule_files:
        clauses.extend(parse_program(path.read_text(encoding="utf-8"), source=str(path)).clauses)
    for path in fact_paths:
        parsed = parse_program(path.read_text(encoding="utf-8"), source=str(path))
        if any(not clause.is_fact for clause in parsed.clauses):
            raise ValueError(f"fact file {path} may contain facts only")
        clauses.extend(parsed.clauses)
    return Program(tuple(clauses))


def _scenario_facts(raw_facts: object, *, source: str) -> tuple[Clause, ...]:
    if not isinstance(raw_facts, list) or any(not isinstance(fact, str) for fact in raw_facts):
        raise ValueError(f"{source}: facts must be an array of sentence strings")
    clauses: list[Clause] = []
    for fact in raw_facts:
        parsed = parse_program(fact, source=source)
        if len(parsed.clauses) != 1 or not parsed.clauses[0].is_fact:
            raise ValueError(f"{source}: each scenario fact must be one ground fact")
        clauses.extend(parsed.clauses)
    return tuple(clauses)


def _load_scenarios(path: Path) -> list[dict[str, object]]:
    payload = tomllib.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != 1:
        raise ValueError(f"{path}: expected schema = 1")
    raw_cases = payload.get("case")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ValueError(f"{path}: expected at least one [[case]]")
    cases: list[dict[str, object]] = []
    for index, raw_case in enumerate(raw_cases, start=1):
        if not isinstance(raw_case, dict):
            raise ValueError(f"{path}: case {index} must be a table")
        name = raw_case.get("name")
        query = raw_case.get("query")
        facts = raw_case.get("facts", [])
        has_truth = "expect" in raw_case
        has_bindings = "expect_bindings" in raw_case
        if not isinstance(name, str) or not name.strip() or not isinstance(query, str) or not query.strip():
            raise ValueError(f"{path}: case {index} requires non-empty name and query strings")
        if not isinstance(facts, list) or any(not isinstance(fact, str) for fact in facts):
            raise ValueError(f"{path}: case {name!r} facts must be an array of sentence strings")
        if has_truth == has_bindings:
            raise ValueError(f"{path}: case {name!r} must set exactly one of expect or expect_bindings")
        if has_truth and not isinstance(raw_case["expect"], bool):
            raise ValueError(f"{path}: case {name!r} expect must be true or false")
        if has_bindings:
            expected_bindings = raw_case["expect_bindings"]
            if not isinstance(expected_bindings, list) or any(
                not isinstance(binding, dict)
                or any(not isinstance(key, str) or not isinstance(value, str) for key, value in binding.items())
                for binding in expected_bindings
            ):
                raise ValueError(f"{path}: case {name!r} expect_bindings must be an array of string maps")
        cases.append(dict(raw_case))
    return cases


async def _run_scenarios(program: Program, cases: list[dict[str, object]], *, source: str) -> tuple[int, int]:
    passed = 0
    failed = 0
    for case in cases:
        name = str(case["name"])
        query = str(case["query"])
        facts = _scenario_facts(case.get("facts", []), source=f"{source} [{name}]")
        case_program = Program((*program.clauses, *facts))
        result = await NLEngine(case_program, ExactUnifier()).run(parse_query(query))
        if "expect" in case:
            expected = case["expect"]
            succeeded = result.matched is expected
            detail = f"expected {expected}, got {result.matched}"
        else:
            expected_bindings = case["expect_bindings"]
            expected = tuple(sorted(tuple(sorted(binding.items())) for binding in expected_bindings))
            actual = tuple(sorted(tuple(sorted(solution.bindings.items())) for solution in result.solutions))
            succeeded = actual == expected
            detail = f"expected bindings {expected}, got {actual}"
        if succeeded:
            passed += 1
            typer.echo(f"PASS {name}")
        else:
            failed += 1
            typer.echo(f"FAIL {name}: {detail}")
    return passed, failed


def _version(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(False, "--version", callback=_version, is_eager=True, help="Show version and exit."),
) -> None:
    del version


@app.command("validate")
def validate(program: Path = PROGRAM_ARGUMENT) -> None:
    """Parse and validate a program without contacting Jev."""
    try:
        parsed = parse_program(program.read_text(encoding="utf-8"), source=str(program))
    except (OSError, ParseError) as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(2) from exc
    facts = sum(clause.is_fact for clause in parsed.clauses)
    rules = len(parsed.clauses) - facts
    typer.echo(f"ok: {facts} facts, {rules} rule clauses")


@app.command("test")
def test_scenarios(
    program: Path = PROGRAM_ARGUMENT,
    cases: Path = CASES_ARGUMENT,
    additional_rules: list[Path] | None = typer.Option(  # noqa: B008
        None,
        "--rules",
        exists=True,
        dir_okay=False,
        readable=True,
        help="Additional rule file; repeat to compose a rule pack.",
    ),
) -> None:
    """Run an exact/offline TOML scenario suite against one or more rule files."""
    try:
        parsed_program = _load_input_program([program, *(additional_rules or [])], [])
        scenarios = _load_scenarios(cases)
        passed, failed = asyncio.run(_run_scenarios(parsed_program, scenarios, source=str(cases)))
    except (OSError, ParseError, ValueError) as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(2) from exc
    typer.echo(f"{passed} passed, {failed} failed")
    if failed:
        raise typer.Exit(1)


@app.command("run")
def run_program(
    program: Path = PROGRAM_ARGUMENT,
    query: str = QUERY_ARGUMENT,
    additional_rules: list[Path] | None = typer.Option(  # noqa: B008
        None,
        "--rules",
        exists=True,
        dir_okay=False,
        readable=True,
        help="Additional rule file; repeat to compose a rule pack.",
    ),
    fact_files: list[Path] | None = typer.Option(  # noqa: B008
        None,
        "--facts",
        exists=True,
        dir_okay=False,
        readable=True,
        help="Runtime fact file; repeat to combine evidence sources.",
    ),
    exact_only: bool = typer.Option(
        False,
        "--exact-only",
        help="Never contact Jev; differently worded terms do not unify.",
    ),
    explain: bool = typer.Option(False, "--explain", help="Print the proof for each successful solution."),
    trace: bool = typer.Option(False, "--trace", help="Print every proof and unification attempt."),
    debug: bool = typer.Option(False, "--debug", help="Compatibility alias for --trace."),
    json_output: bool = typer.Option(False, "--json", help="Emit stable machine-readable JSON."),
    stats: bool = typer.Option(False, "--stats", help="Print aggregate run statistics."),
    model: str | None = typer.Option(None, "--model", help="Optional Jev model override."),
    concurrency: int = typer.Option(8, min=1, help="Maximum simultaneous semantic-backend calls."),
    semantic_batch_size: int = typer.Option(32, min=1, help="Maximum semantic candidates per backend batch."),
    cache_size: int = typer.Option(2048, min=1, help="Maximum semantic cache entries."),
    max_depth: int = typer.Option(25, min=1),
    max_steps: int = typer.Option(2000, min=1),
    max_solutions: int = typer.Option(50, min=1),
) -> None:
    """Run a goal against a natural-language logic program."""

    async def execute() -> int:
        try:
            parsed_program = _load_input_program([program, *(additional_rules or [])], fact_files or [])
            parsed_query = parse_query(query, source="<query>")
        except (OSError, ValueError) as exc:
            typer.echo(f"error: {exc}", err=True)
            return 2

        unifier = None
        try:
            unifier = (
                ExactUnifier()
                if exact_only
                else PyJevUnifier(
                    model=model,
                    concurrency=concurrency,
                    semantic_batch_size=semantic_batch_size,
                    cache_size=cache_size,
                )
            )
            result = await NLEngine(parsed_program, unifier).run(
                parsed_query,
                max_depth=max_depth,
                max_steps=max_steps,
                max_solutions=max_solutions,
            )
        except Exception as exc:  # Runtime/backend failures are concise CLI errors.
            typer.echo(f"error: semantic backend or execution failed: {exc}", err=True)
            return 1
        finally:
            if isinstance(unifier, PyJevUnifier):
                await unifier.close()

        if json_output:
            typer.echo(json.dumps(_json_result(result), sort_keys=True, indent=2))
            return 0

        if trace or debug:
            _print_trace(result)
        if explain:
            _print_explanations(result)

        query_vars: list[str] = []
        for alternative in parsed_query.alternatives:
            for literal in alternative:
                for variable in variables_in(literal.sentence):
                    if variable not in query_vars:
                        query_vars.append(variable)
        if query_vars:
            if not result.solutions:
                typer.echo("No solutions.")
            else:
                typer.echo("SOLUTIONS")
                for number, solution in enumerate(result.solutions, start=1):
                    rendered = ", ".join(f"{key} = {value}" for key, value in solution.bindings.items())
                    typer.echo(f"{number}. {rendered}")
        else:
            typer.echo("Yes." if result.solutions else "No.")
        if result.truncated:
            typer.echo("warning: search was truncated by a configured limit", err=True)
        if stats or trace or debug:
            typer.echo(_stats_line(result))
        return 0

    try:
        code = asyncio.run(execute())
    except KeyboardInterrupt as exc:
        raise typer.Exit(130) from exc
    raise typer.Exit(code)


def _print_trace(result) -> None:
    typer.echo("PROOF TRACE")
    for index, step in enumerate(result.steps, start=1):
        indent = "  " * step.depth
        detail = f" -> {step.clause}" if step.clause else ""
        meta = [
            value
            for value in (step.method, f"p={step.confidence:.2f}" if step.confidence is not None else None)
            if value
        ]
        if step.bindings:
            meta.append(str(step.bindings))
        suffix = f" [{', '.join(meta)}]" if meta else ""
        typer.echo(f"{index:04d} {indent}{step.kind.upper()}: {step.goal}{detail}{suffix}")
        if step.note:
            typer.echo(f"     {indent}{step.note}")
    typer.echo("")


def _print_explanations(result) -> None:
    if not result.solutions:
        return
    typer.echo("EXPLANATIONS")
    for number, solution in enumerate(result.solutions, start=1):
        typer.echo(f"{number}. {solution.answer}")
        proof_lines = solution.explain().splitlines()
        if proof_lines and proof_lines[0] == solution.answer:
            proof_lines = proof_lines[1:]
        if proof_lines:
            typer.echo("\n".join(proof_lines))


def _stats_line(result) -> str:
    stats = result.stats
    return (
        "stats: "
        f"backend_requests={stats.backend_requests} semantic_questions={stats.semantic_questions} "
        f"cache_hits={stats.cache_hits} clauses_considered={stats.clauses_considered} "
        f"proof_steps={stats.proof_steps}"
    )


def _json_result(result) -> dict[str, object]:
    return {
        "solutions": [
            {
                "bindings": solution.bindings,
                "answer": solution.answer,
                "proof": [asdict(step) for step in solution.proof.steps],
            }
            for solution in result.solutions
        ],
        "trace": [asdict(step) for step in result.steps],
        "truncated": result.truncated,
        "stats": asdict(result.stats),
    }
