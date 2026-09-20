"""Command-line interface for InferLingo."""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer

from . import __version__
from .engine import NLEngine
from .parser import ParseError, parse_program, parse_query
from .terms import variables_in
from .unifier import ExactUnifier, PyJevUnifier

app = typer.Typer(no_args_is_help=True, add_completion=False, help="Natural-language logic with pluggable semantic unification.")


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
def validate(program: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True)) -> None:
    """Parse a program without contacting Jev."""
    try:
        parsed = parse_program(program.read_text(encoding="utf-8"))
    except (OSError, ParseError) as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(2) from exc
    facts = sum(clause.is_fact for clause in parsed.clauses)
    rules = len(parsed.clauses) - facts
    typer.echo(f"ok: {facts} facts, {rules} rule clauses")


@app.command("run")
def run_program(
    program: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    query: str = typer.Argument(..., help='Goal syntax, e.g. "X is a grandfather of Bart?"'),
    exact_only: bool = typer.Option(False, "--exact-only", help="Never contact Jev; differently worded terms do not unify."),
    debug: bool = typer.Option(False, "--debug", help="Print every proof/unification step."),
    model: str | None = typer.Option(None, "--model", help="Optional Jev model override for the built-in pyjev backend."),
    concurrency: int = typer.Option(8, min=1, help="Maximum simultaneous semantic-backend calls."),
    max_depth: int = typer.Option(25, min=1),
    max_steps: int = typer.Option(2000, min=1),
    max_solutions: int = typer.Option(50, min=1),
) -> None:
    """Run a goal against a natural-language logic program."""

    async def execute() -> int:
        try:
            parsed_program = parse_program(program.read_text(encoding="utf-8"))
            parsed_query = parse_query(query)
        except (OSError, ParseError) as exc:
            typer.echo(f"error: {exc}", err=True)
            return 2

        unifier = ExactUnifier() if exact_only else PyJevUnifier(model=model, concurrency=concurrency)
        try:
            result = await NLEngine(parsed_program, unifier).run(
                parsed_query,
                max_depth=max_depth,
                max_steps=max_steps,
                max_solutions=max_solutions,
            )
        finally:
            if isinstance(unifier, PyJevUnifier):
                await unifier.close()

        if debug:
            typer.echo("PROOF TRACE")
            for index, step in enumerate(result.steps, start=1):
                indent = "  " * step.depth
                if step.clause:
                    detail = f" -> {step.clause}"
                else:
                    detail = ""
                meta = []
                if step.method:
                    meta.append(step.method)
                if step.confidence is not None:
                    meta.append(f"p={step.confidence:.2f}")
                if step.bindings:
                    meta.append(str(step.bindings))
                suffix = f" [{', '.join(meta)}]" if meta else ""
                typer.echo(f"{index:04d} {indent}{step.kind.upper()}: {step.goal}{detail}{suffix}")
                if step.note:
                    typer.echo(f"     {indent}{step.note}")
            typer.echo("")

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
        if debug:
            typer.echo(
                f"stats: semantic_calls={result.unification_calls} cached_unifications={result.cached_unifications} "
                f"proof_steps={len(result.steps)}"
            )
        return 0

    try:
        code = asyncio.run(execute())
    except KeyboardInterrupt as exc:
        raise typer.Exit(130) from exc
    except Exception as exc:  # API/auth/runtime failures should be concise at the CLI boundary.
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(1) from exc
    raise typer.Exit(code)
