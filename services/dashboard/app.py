"""Local UI and snapshot API. No tool calls, config writes or generic proxy routes."""

import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from urllib.parse import urlsplit

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, Response
from starlette.routing import Route
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from mcp_stack.config import StackConfig, load_config
from services.dashboard.monitor import ContractView, Monitor

STATIC = Path(__file__).parent / "static"


class LocalOnly:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = {k.decode().lower(): v.decode() for k, v in scope["headers"]}
        host = headers.get("host", "")
        try:
            hostname = urlsplit("http://" + host).hostname
        except ValueError:
            hostname = None
        origin = headers.get("origin")
        if (
            hostname not in {"localhost", "127.0.0.1", "::1", "dashboard"}
            or (origin is not None and origin != "http://" + host)
            or headers.get("sec-fetch-site") == "cross-site"
        ):
            await Response("Local access only", status_code=403)(scope, receive, send)
            return

        async def secured(message: Message) -> None:
            if message["type"] == "http.response.start":
                message["headers"] = list(message.get("headers", [])) + [
                    (
                        b"content-security-policy",
                        b"default-src 'self'; script-src 'self'; "
                        b"style-src 'self'; img-src 'self'; connect-src 'self'; "
                        b"frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
                    ),
                    (b"x-content-type-options", b"nosniff"),
                    (b"referrer-policy", b"no-referrer"),
                    (b"cache-control", b"no-store"),
                ]
            await send(message)

        await self.app(scope, receive, secured)


def create_app(config: StackConfig | None = None, monitor: Monitor | None = None) -> Starlette:
    config = config or load_config(Path(os.getenv("STACK_CONFIG", "config/stack.yaml")))
    observer = monitor or Monitor(config)
    task: asyncio.Task[None] | None = None

    @asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        nonlocal task
        task = asyncio.create_task(observer.run(), name="dashboard-observer")
        try:
            yield
        finally:
            task.cancel()
            try:
                with suppress(asyncio.CancelledError):
                    await task
            finally:
                await observer.close()

    async def overview(request: Request) -> Response:
        return JSONResponse(observer.overview().model_dump(mode="json"))

    async def health(request: Request) -> Response:
        alive = task is not None and not task.done()
        return JSONResponse({"alive": alive}, status_code=200 if alive else 503)

    async def contract(request: Request) -> Response:
        tool = observer.contracts.get(request.path_params["name"])
        if tool is None:
            return JSONResponse({"error": "TOOL_NOT_FOUND"}, status_code=404)
        view = ContractView(
            tool=tool,
            observed_at=observer.catalog.observed_at,
            available=observer.catalog.available and observer.status_error is None,
        )
        return JSONResponse(view.model_dump(mode="json"))

    async def index(request: Request) -> Response:
        return FileResponse(STATIC / "index.html")

    async def asset(request: Request) -> Response:
        name = request.path_params["name"]
        if name not in {"app.js", "theme.js", "style.css", "mark.svg"}:
            return Response(status_code=404)
        return FileResponse(STATIC / name)

    app = Starlette(
        routes=[
            Route("/", index),
            Route("/health", health),
            Route("/api/overview", overview),
            Route("/api/contracts/{name}", contract),
            Route("/assets/{name}", asset),
        ],
        lifespan=lifespan,
    )
    app.add_middleware(LocalOnly)
    return app
