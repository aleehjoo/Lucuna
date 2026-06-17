# lacuna/pipeline/validation.py
"""G0 hard gate: confirm Hardcover returns live reviews for a real title."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import datetime as _dt

from lacuna.db.models import AnalysisRun
from lacuna.db.session import build_sessionmaker


@dataclass
class ValidationResult:
    passed: bool
    title: str
    review_count: int
    error: str | None = None


async def validate_hardcover(
    client,
    *,
    sample_title: str = "Atomic Habits",
    recorder: Callable[[ValidationResult], Awaitable[None]] | None = None,
) -> ValidationResult:
    """Fetch a real title and confirm >0 live reviews. Records via `recorder`."""
    try:
        book = await client.fetch_book_by_title(sample_title)
        if book is None:
            result = ValidationResult(False, sample_title, 0,
                                      error=f"title not found on Hardcover: {sample_title!r}")
        else:
            count = len(book.reviews)
            result = ValidationResult(
                passed=count > 0, title=book.title, review_count=count,
                error=None if count > 0 else "title found but no live reviews available",
            )
    except Exception as exc:  # noqa: BLE001  (gate must capture, not crash)
        result = ValidationResult(False, sample_title, 0, error=f"{type(exc).__name__}: {exc}")

    if recorder is not None:
        await recorder(result)
    return result


def make_db_recorder(sessionmaker=None):
    """Return an async recorder that writes a validation row to analysis_runs."""
    maker = sessionmaker or build_sessionmaker()

    async def _record(result: ValidationResult) -> None:
        run = AnalysisRun(
            project_id=None,
            mode="validation",
            target=result.title,
            sources_used=["hardcover"],
            finished_at=_dt.datetime.now(_dt.timezone.utc),
            status="ok" if result.passed else "error",
            counts={"review_count": result.review_count},
            error_detail=result.error,
        )
        async with maker() as session:
            session.add(run)
            await session.commit()

    return _record
