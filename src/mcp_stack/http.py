"""HTTP policy only. MCP framing and protocol validation belong to the SDK."""

import hmac
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from mcp_stack.config import ServerManifest


class LimitedStream(httpx2.AsyncByteStream):
    def __init__(self, stream: httpx2.AsyncByteStream, limit: int) -> None:
        self.stream = stream
        self.limit = limit

    async def __aiter__(self) -> AsyncIterator[bytes]:
        consumed = 0
        async for chunk in self.stream:
            consumed += len(chunk)
            if consumed > self.limit:
                raise ValueError("downstream response exceeds configured limit")
            yield chunk

    async def aclose(self) -> None:
        await self.stream.aclose()


class LimitedTransport(httpx2.AsyncBaseTransport):
    def __init__(self, limit: int) -> None:
        self.transport = httpx2.AsyncHTTPTransport()
        self.limit = limit

    async def handle_async_request(self, request: httpx2.Request) -> httpx2.Response:
        response = await self.transport.handle_async_request(request)
        if response.headers.get("content-encoding", "identity") != "identity":
            await response.aclose()
            raise ValueError("compressed downstream responses are not accepted")
        assert isinstance(response.stream, httpx2.AsyncByteStream)
        response.stream = LimitedStream(response.stream, self.limit)
        return response

    async def aclose(self) -> None:
        await self.transport.aclose()


class RequestPolicy:
    def __init__(self, app: ASGIApp, max_bytes: int, token_env: str | None = None) -> None:
        self.app = app
        self.max_bytes = max_bytes
        self.token_env = token_env

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = dict(scope["headers"])
        token = os.getenv(self.token_env, "") if self.token_env else ""
        if token and scope["path"] not in {"/live"}:
            actual = headers.get(b"authorization", b"")
            if not hmac.compare_digest(actual, f"Bearer {token}".encode()):
                await JSONResponse({"error": "unauthorized"}, status_code=401)(scope, receive, send)
                return
        # Buffer a bounded request, including chunked bodies, before application parsing.
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > self.max_bytes:
                await JSONResponse({"error": "payload_too_large"}, status_code=413)(
                    scope, receive, send
                )
                return
            if not message.get("more_body", False):
                break
        delivered = False

        async def bounded_receive() -> Any:
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, bounded_receive, send)


def bearer_headers(env_name: str | None) -> dict[str, str]:
    if not env_name:
        return {}
    value = os.environ.get(env_name)
    if not value:
        raise ValueError(f"required token environment variable is missing: {env_name}")
    return {"Authorization": f"Bearer {value}"}


@asynccontextmanager
async def downstream_client(
    server: ServerManifest, max_bytes: int = 1048576
) -> AsyncIterator[Client]:
    async with httpx2.AsyncClient(
        headers={"Accept-Encoding": "identity", **bearer_headers(server.transport.token_env)},
        transport=LimitedTransport(max_bytes),
        timeout=server.transport.timeout_seconds,
        follow_redirects=False,
        trust_env=False,
    ) as http:
        async with Client(
            streamable_http_client(server.transport.url, http_client=http),
            read_timeout_seconds=server.transport.timeout_seconds,
            cache=None,
        ) as client:
            yield client


async def read_json(
    client: httpx.AsyncClient, method: str, url: str, *, max_bytes: int, **kwargs: Any
) -> Any:
    async with client.stream(method, url, **kwargs) as response:
        response.raise_for_status()
        data = bytearray()
        async for chunk in response.aiter_bytes():
            data.extend(chunk)
            if len(data) > max_bytes:
                raise ValueError("HTTP response exceeds configured size limit")
    import json

    return json.loads(data)
