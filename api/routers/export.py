# api/routers/export.py
from __future__ import annotations

import json
import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse, PlainTextResponse
from starlette.concurrency import run_in_threadpool

from lacuna.pipeline.distill import distill_score_export

router = APIRouter(prefix="/projects/{project_id}", tags=["export"])


@router.get("/export")
async def export_pack(project_id: uuid.UUID, format: str = Query("json"),
                      scope: str = Query("category_sweep")):
    """Regenerate the Context Pack for THIS project via the (id-aware) distiller ($0).
    The distiller is sync/IO-heavy → run it off the event loop. Scoped by project_id
    so two projects export their own packs (Frontend PRD §9 isolation)."""
    with tempfile.TemporaryDirectory() as d:
        out = str(Path(d) / "pack.json")
        await run_in_threadpool(_distill_sync, out, scope, str(project_id))
        if format == "md":
            md = Path(out).with_suffix(".md").read_text(encoding="utf-8")
            return PlainTextResponse(md, media_type="text/markdown")
        pack = json.loads(Path(out).read_text(encoding="utf-8"))
        return JSONResponse(pack)


def _distill_sync(out: str, mode: str, project_id: str) -> None:
    import asyncio
    asyncio.run(distill_score_export(out=out, mode=mode, project_id=project_id))
