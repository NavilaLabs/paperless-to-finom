"""Optional HTTP trigger, so the sync can also run as a public-ish API.

Secured by a bearer token (FINOM_TRIGGER_TOKEN). Keep it behind your
reverse proxy / Cloudflare and only expose it if you actually need a
webhook. For most setups the cron `sync` command is enough.
"""
from __future__ import annotations

import logging

from .config import Config
from .sync import SyncService

log = logging.getLogger("paperless_finom.server")


def create_app(cfg: Config):
    from fastapi import FastAPI, Header, HTTPException

    app = FastAPI(title="paperless-finom", version="1.0.0")

    def _check(authorization: str | None) -> None:
        if not cfg.trigger_token:
            raise HTTPException(503, "Trigger token not configured.")
        expected = f"Bearer {cfg.trigger_token}"
        if authorization != expected:
            raise HTTPException(401, "Unauthorized")

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.post("/trigger")
    def trigger(authorization: str | None = Header(default=None)) -> dict:
        _check(authorization)
        svc = SyncService(cfg)
        try:
            result = svc.run()
        finally:
            svc.close()
        return result.as_dict()

    @app.get("/history")
    def history(limit: int = 20,
                authorization: str | None = Header(default=None)) -> dict:
        _check(authorization)
        from .store import Store
        store = Store(cfg.db_path)
        rows = [dict(r) for r in store.recent(limit)]
        store.close()
        return {"items": rows}

    return app


def run_server(cfg: Config, host: str = "127.0.0.1", port: int = 8080) -> None:
    import uvicorn
    app = create_app(cfg)
    uvicorn.run(app, host=host, port=port)
