# api/app.py
"""FastAPI app factory (Frontend PRD §2/§4). Wraps the lacuna engine. Models warm
once in the lifespan; CORS is restricted to the local frontend; secrets never leave
the backend. The factory takes injectable runtime/sessionmaker so tests run with
fakes and no model download."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.runtime import EngineRuntime

ALLOWED_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]


def create_app(*, runtime: EngineRuntime | None = None, sessionmaker=None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Warm models once at startup unless one was injected (tests/dev).
        if app.state.runtime is None:
            app.state.runtime = EngineRuntime.warm()
        yield

    app = FastAPI(title="Lacuna API", lifespan=lifespan)
    app.state.runtime = runtime
    app.state.sessionmaker = sessionmaker

    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health() -> dict:
        ready = app.state.runtime is not None
        return {"status": "ok" if ready else "warming", "models_ready": ready}

    from api.routers import export, projects, reads
    for r in (projects, reads, export):
        app.include_router(r.router)

    return app
