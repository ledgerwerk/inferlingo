"""Command-line interface for InferLingo."""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict
from pathlib import Path

import typer

from . import __version__
from .engine import NLEngine
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


@app.command("run")
def run_program(
    program: Path = PROGRAM_ARGUMENT,
    query: str = QUERY_ARGUMENT,
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
            parsed_program = parse_program(program.read_text(encoding="utf-8"), source=str(program))
            parsed_query = parse_query(query, source="<query>")
        except (OSError, ParseError) as exc:
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
        rendered = solution.proof.render()
        if rendered:
            typer.echo(rendered)


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
