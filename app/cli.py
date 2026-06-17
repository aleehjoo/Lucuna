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


@app.command("seed")
def seed_cmd(
    rebuild: bool = typer.Option(True, help="Full recompute (only supported mode)."),
    max_works: int = typer.Option(60, help="Cap on works selected for the seed."),
    meta_limit: int = typer.Option(200_000, help="Max corpus meta rows to scan."),
    review_limit: int = typer.Option(1_000_000, help="Max corpus review rows to scan."),
) -> None:
    """Seed Supabase from the local corpus pipeline (PRD §6). Downloads pinned
    models on first run; all NLP is local — no raw text leaves the machine."""
    from lacuna.seed.seed import run_seed

    typer.secho("Seeding from local corpus (this downloads pinned models on first run)…",
                fg=typer.colors.CYAN)
    counts = run_seed(rebuild=rebuild, max_works=max_works,
                      meta_limit=meta_limit, review_limit=review_limit)
    typer.secho(f"SEED OK — {counts}", fg=typer.colors.GREEN)


if __name__ == "__main__":
    app()
