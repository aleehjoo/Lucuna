# app/cli.py
"""Lacuna CLI. G0 ships `validate-hardcover`; later workstreams add seed/analyze/sweep/export."""
from __future__ import annotations

import asyncio

import typer

from lacuna.config import get_settings
from lacuna.adapters.hardcover import HardcoverClient
from lacuna.pipeline.validation import (
    ValidationResult, make_db_recorder, validate_hardcover,
)

app = typer.Typer(help="Lacuna — reader-dissatisfaction gap engine", no_args_is_help=True)


@app.callback()
def _cli() -> None:
    """Lacuna CLI. Keeps the app a multi-command group so subcommands keep their
    names (seed/analyze/sweep/export are added in Workstream I)."""


def _run_validation() -> ValidationResult:
    """Build the live client + DB recorder and run the gate. Patched in tests."""
    settings = get_settings()
    if not settings.hardcover_api_token:
        return ValidationResult(False, "(none)", 0, error="HARDCOVER_API_TOKEN not set in .env")

    async def _go() -> ValidationResult:
        client = HardcoverClient(token=settings.hardcover_api_token)
        try:
            return await validate_hardcover(client, recorder=make_db_recorder())
        finally:
            await client.aclose()

    return asyncio.run(_go())


@app.command("validate-hardcover")
def validate_hardcover_cmd() -> None:
    """G0 gate: confirm the Hardcover API returns live reviews for a real title."""
    result = _run_validation()
    if result.passed:
        typer.secho(f"PASS — {result.title!r}: {result.review_count} live reviews", fg=typer.colors.GREEN)
        raise typer.Exit(code=0)
    typer.secho(f"FAIL — {result.error}", fg=typer.colors.RED)
    raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
