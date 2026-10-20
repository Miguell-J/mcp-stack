"""Read bounded, sanitized Cordis exports without importing or executing Cordis."""

import asyncio
import json
import math
import os
import stat
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from mcp_stack.config import Dashboard

MAX_BYTES = 2 * 1024 * 1024
SCHEMA = Path(__file__).parent / "schemas" / "cordis-snapshot.schema.json"


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON property")
        result[key] = value
    return result


def _finite(value: object, depth: int = 0) -> None:
    if depth > 24:
        raise ValueError("snapshot nesting exceeds limit")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("nonfinite observation")
    if isinstance(value, dict):
        for item in value.values():
            _finite(item, depth + 1)
    elif isinstance(value, list):
        for item in value:
            _finite(item, depth + 1)


class CordisObserver:
    def __init__(self, config: Dashboard):
        self.config = config
        self.directory = (
            os.environ.get("CORDIS_SNAPSHOT_DIR", config.cordis_snapshot_dir)
            if config.cordis_snapshot_dir is not None
            else None
        )
        self.snapshot: dict[str, Any] | None = None
        self.observed_at: str | None = None
        self._pending: asyncio.Task[dict[str, Any]] | None = None
        self.error: str | None = "STARTING" if self.directory else "DISABLED"
        self.validator = Draft202012Validator(
            json.loads(SCHEMA.read_bytes()), format_checker=FormatChecker()
        )

    def _read(self) -> dict[str, Any]:
        if self.directory is None:
            raise ValueError("unconfigured observer")
        directory = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            descriptor = os.open(
                "snapshot.json",
                os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                dir_fd=directory,
            )
        finally:
            os.close(directory)
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > MAX_BYTES:
                raise ValueError("unsafe snapshot")
            with os.fdopen(descriptor, "rb", closefd=False) as source:
                raw = source.read(MAX_BYTES + 1)
        finally:
            os.close(descriptor)
        if len(raw) > MAX_BYTES:
            raise ValueError("snapshot too large")
        document: dict[str, Any] = json.loads(raw, object_pairs_hook=_unique_object)
        _finite(document)
        self.validator.validate(document)
        generated = datetime.fromisoformat(document["generated_at"].replace("Z", "+00:00"))
        if generated.utcoffset() is None or (generated - datetime.now(UTC)).total_seconds() > 30:
            raise ValueError("invalid snapshot timestamp")
        if document["exported_runs"] != len(document["runs"]):
            raise ValueError("inconsistent exported count")
        if document["total_runs"] < document["exported_runs"]:
            raise ValueError("inconsistent total count")
        if document["truncated"] != (document["total_runs"] > document["exported_runs"]):
            raise ValueError("inconsistent truncation marker")
        ids = [run["run_id"] for run in document["runs"]]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate run")
        for run in document["runs"]:
            if not run["available"] and (
                any(
                    run[key] is not None
                    for key in ("state", "status", "profile", "plan_revision", "work_revision")
                )
                or any(
                    run[key]
                    for key in (
                        "tasks",
                        "attempts",
                        "gates",
                        "history",
                        "evidence",
                        "tool_calls",
                        "failures",
                    )
                )
                or any(value is not None for value in run["usage"].values())
                or not run["error"]
            ):
                raise ValueError("unavailable run contains partial observations")
            for collection, key in (("tasks", "id"), ("attempts", "id"), ("evidence", "key")):
                keys = [item[key] for item in run[collection]]
                if len(set(keys)) != len(keys):
                    raise ValueError("duplicate metadata identity")
        return document

    async def refresh(self) -> None:
        if self.directory is None:
            return
        try:
            if self._pending is None:
                self._pending = asyncio.create_task(
                    asyncio.to_thread(self._read), name="dashboard-cordis-read"
                )
            async with asyncio.timeout(self.config.timeout_seconds):
                document = await asyncio.shield(self._pending)
            self.snapshot = document
            self.observed_at = datetime.now(UTC).isoformat()
            self.error = None
        except FileNotFoundError:
            self.error = "SNAPSHOT_MISSING"
        except TimeoutError:
            self.error = "TIMEOUT"
        except OSError:
            self.error = "SNAPSHOT_UNAVAILABLE"
        except Exception:
            # Source paths, raw JSON and exception text never reach browser/logs.
            self.error = "INVALID_SNAPSHOT"
        finally:
            if self._pending is not None and self._pending.done():
                self._pending = None

    async def close(self) -> None:
        pending, self._pending = self._pending, None
        if pending is not None:
            pending.cancel()
            try:
                await pending
            except asyncio.CancelledError:
                pass
            except Exception:
                # A completed read can fail concurrently with shutdown.
                pass

    async def run(self) -> None:
        while True:
            await self.refresh()
            await asyncio.sleep(self.config.poll_seconds)

    def overview(self) -> dict[str, Any]:
        generated = self.snapshot["generated_at"] if self.snapshot else None
        age = (
            (
                datetime.now(UTC) - datetime.fromisoformat(generated.replace("Z", "+00:00"))
            ).total_seconds()
            if generated
            else None
        )
        return {
            "configured": self.directory is not None,
            "available": self.error is None,
            "observed_at": self.observed_at,
            "source_generated_at": generated,
            "stale": self.error is not None
            or age is None
            or age > self.config.cordis_stale_seconds,
            "error": self.error,
            "snapshot": self.snapshot,
        }

    def find_run(self, run_id: str) -> dict[str, Any] | None:
        return (
            next((run for run in self.snapshot["runs"] if run["run_id"] == run_id), None)
            if self.snapshot
            else None
        )
