from __future__ import annotations

import argparse
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from blender_ai_sidecar import __version__
from blender_ai_sidecar.api.routes import router
from blender_ai_sidecar.chat.agent import ChatAgent
from blender_ai_sidecar.config import get_settings
from blender_ai_sidecar.providers.router import ProviderRouter
from blender_ai_sidecar.skills.engine import SkillEngine
from blender_ai_sidecar.store.db import Database


def create_app() -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        db = Database(settings.resolved_db())
        await db.connect()
        skills = SkillEngine()
        skills.load()
        prov = ProviderRouter(db)
        agent = ChatAgent(db, prov, skills)
        app.state.db = db
        app.state.skills = skills
        app.state.provider_router = prov
        app.state.agent = agent
        yield
        await db.close()

    app = FastAPI(title="BlenderAI Sidecar", version=__version__, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)

    dist = settings.webui_dist
    if dist.exists():
        assets = dist / "assets"
        if assets.exists():
            app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

        @app.get("/")
        async def spa_index():
            return FileResponse(dist / "index.html")

        @app.get("/{full_path:path}")
        async def spa_fallback(full_path: str):
            candidate = dist / full_path
            if candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(dist / "index.html")

    return app


def serve(host: str | None = None, port: int | None = None) -> None:
    settings = get_settings()
    uvicorn.run(
        "blender_ai_sidecar.main:create_app",
        factory=True,
        host=host or settings.host,
        port=port or settings.port,
        reload=False,
        log_level="info",
    )


def cli() -> None:
    parser = argparse.ArgumentParser(prog="blender-ai-sidecar")
    sub = parser.add_subparsers(dest="cmd")
    serve_p = sub.add_parser("serve", help="Run HTTP/WS server")
    serve_p.add_argument("--host", default=None)
    serve_p.add_argument("--port", type=int, default=None)
    mcp_p = sub.add_parser("mcp", help="Run MCP server")
    mcp_p.add_argument("--stdio", action="store_true", default=True)
    args = parser.parse_args()
    if args.cmd == "mcp":
        from blender_ai_sidecar.mcp.server import main_mcp

        main_mcp()
    else:
        serve(host=getattr(args, "host", None), port=getattr(args, "port", None))


if __name__ == "__main__":
    cli()
