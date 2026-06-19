# api/deps.py
from __future__ import annotations

from fastapi import Request

from api.runtime import EngineRuntime


def get_runtime(request: Request) -> EngineRuntime:
    return request.app.state.runtime


def get_sessionmaker(request: Request):
    sm = request.app.state.sessionmaker
    if sm is None:
        from lacuna.db.session import build_sessionmaker
        sm = build_sessionmaker()
        request.app.state.sessionmaker = sm
    return sm
