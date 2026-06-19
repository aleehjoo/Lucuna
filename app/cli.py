# app/cli.py
"""Lacuna CLI. G0 ships `validate-hardcover`; later workstreams add seed/analyze/sweep/export."""
from __future__ import annotations

import asyncio
import sys

import typer

from lacuna.config import get_settings
from lacuna.adapters.hardcover import HardcoverClient
from lacuna.pipeline.validation import (
    ValidationResult, make_db_recorder, validate_hardcover,
)

# Windows defaults stdout/stderr to cp1252; a redirected `lacuna seed > log.txt`
# then crashes encoding the seed's progress glyphs (→ · …) the moment Pass 1
# finishes. Force UTF-8 so long runs (PRD §6) survive redirection;
# errors="replace" is a belt-and-suspenders guard if reconfigure no-ops.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # not a reconfigurable TextIO (e.g. captured)
        pass

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
    max_works: int = typer.Option(25, help="Cap on works selected for the seed."),
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


@app.command("analyze")
def analyze_cmd(
    isbn: str = typer.Option(None, help="ISBN to resolve."),
    title: str = typer.Option(None, help="Title to resolve."),
    out: str = typer.Option("pack.json", help="Output Context Pack path."),
) -> None:
    """Single-Title Watchlist analysis (fresh Hardcover pull) -> Context Pack."""
    import asyncio

    from lacuna.pipeline.single_title import analyze
    asyncio.run(analyze(isbn=isbn, title=title, out=out))


@app.command("sweep")
def sweep_cmd(out: str = typer.Option("sweep_pack.json", help="Output Context Pack path.")) -> None:
    """Category Sweep over the seeded works -> ranked Context Pack ($0, corpus-only)."""
    import asyncio

    from lacuna.pipeline.category_sweep import sweep
    counts = asyncio.run(sweep(out=out))
    typer.secho(f"SWEEP OK — {counts}", fg=typer.colors.GREEN)


@app.command("export")
def export_cmd(out: str = typer.Option("pack.json", help="Output Context Pack path.")) -> None:
    """(Re)generate the Context Pack from the latest seeded data ($0)."""
    import asyncio

    from lacuna.pipeline.single_title import export_only
    counts = asyncio.run(export_only(out=out))
    typer.secho(f"EXPORT OK — {counts}", fg=typer.colors.GREEN)


if __name__ == "__main__":
    app()
