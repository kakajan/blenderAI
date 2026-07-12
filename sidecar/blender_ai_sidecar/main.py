from __future__ import annotations

import argparse
import socket
import sys
from contextlib import asynccontextmanager


def _ensure_port_available(host: str, port: int) -> None:
    """Fail fast if another sidecar already owns the port (avoids split-brain empty replies)."""
    probe_host = "127.0.0.1" if host in ("0.0.0.0", "::", "") else host
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
        try:
            sock.bind((probe_host, port))
        except OSError:
            print(
                f"BlenderAI: port {probe_host}:{port} is already in use.\n"
                "Another sidecar is running — stop it from the N-Panel (Stop) or close that terminal,\n"
                "then start only one instance.",
                file=sys.stderr,
            )
            raise SystemExit(1) from None


def create_app():
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    from blender_ai_sidecar import __version__
    from blender_ai_sidecar import app_log
    from blender_ai_sidecar.api.routes import router
    from blender_ai_sidecar.auth import ensure_token
    from blender_ai_sidecar.chat.agent import ChatAgent
    from blender_ai_sidecar.config import get_settings
    from blender_ai_sidecar.orchestration import get_run_registry
    from blender_ai_sidecar.providers.router import ProviderRouter
    from blender_ai_sidecar.skills.engine import SkillEngine
    from blender_ai_sidecar.store.db import Database

    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        db = Database(settings.resolved_db())
        await db.connect()
        token = await ensure_token(db)
        skills = SkillEngine()
        skills.load()
        prov = ProviderRouter(db)
        agent = ChatAgent(db, prov, skills)
        app.state.db = db
        app.state.skills = skills
        app.state.provider_router = prov
        app.state.agent = agent
        app.state.run_registry = get_run_registry()
        app.state.auth_token = token
        await app_log.emit(
            db,
            "info",
            "sidecar",
            f"Sidecar started v{__version__}",
            component="main",
        )
        yield
        await app_log.emit(db, "info", "sidecar", "Sidecar shutting down", component="main")
        await db.close()

    app = FastAPI(title="BlenderAI Sidecar", version=__version__, lifespan=lifespan)
    # Same-origin WebUI + explicit localhost origins only (never "*").
    origins = [
        f"http://127.0.0.1:{settings.port}",
        f"http://localhost:{settings.port}",
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)

    @app.exception_handler(Exception)
    async def unhandled_exception(request, exc):  # type: ignore[no-untyped-def]
        from fastapi import HTTPException
        from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
        from fastapi.exceptions import RequestValidationError
        from fastapi.responses import JSONResponse
        from starlette.exceptions import HTTPException as StarletteHTTPException

        if isinstance(exc, StarletteHTTPException):
            return await http_exception_handler(request, exc)
        if isinstance(exc, RequestValidationError):
            return await request_validation_exception_handler(request, exc)
        if isinstance(exc, HTTPException):
            return await http_exception_handler(request, exc)

        db = getattr(request.app.state, "db", None)
        try:
            await app_log.emit(
                db,
                "error",
                "sidecar",
                str(exc),
                component="http",
                detail={
                    "path": str(request.url.path),
                    "traceback": app_log.format_exception(exc),
                },
            )
        except Exception:
            pass
        return JSONResponse(status_code=500, content={"detail": str(exc)})

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
    import uvicorn

    from blender_ai_sidecar.config import get_settings

    settings = get_settings()
    bind_host = host or settings.host
    bind_port = port or settings.port
    _ensure_port_available(bind_host, bind_port)
    uvicorn.run(
        "blender_ai_sidecar.main:create_app",
        factory=True,
        host=bind_host,
        port=bind_port,
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
