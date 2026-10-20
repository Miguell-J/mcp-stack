import asyncio
import copy
import json
import time
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from pydantic import ValidationError

from mcp_stack.config import Dashboard, StackConfig, load_config
from mcp_stack.render import compose_config
from services.dashboard.app import create_app
from services.dashboard.cordis import MAX_BYTES, CordisObserver
from services.dashboard.monitor import Monitor
from tests.cordis_fixture import snapshot


@pytest.fixture
def source(tmp_path, monkeypatch):
    monkeypatch.delenv("CORDIS_SNAPSHOT_DIR", raising=False)
    path = tmp_path / "snapshot.json"
    document = snapshot()
    path.write_text(json.dumps(document))
    return CordisObserver(Dashboard(cordis_snapshot_dir=str(tmp_path))), path, document


async def test_disabled_missing_valid_stale_recovery_and_atomic_replace(source):
    observer, path, document = source
    disabled = CordisObserver(Dashboard())
    await disabled.refresh()
    assert disabled.overview()["error"] == "DISABLED"
    assert disabled.overview()["snapshot"] is None
    await observer.refresh()
    assert observer.overview()["available"] and not observer.overview()["stale"]
    previous = observer.snapshot
    path.unlink()
    await observer.refresh()
    assert observer.overview()["error"] == "SNAPSHOT_MISSING"
    assert observer.overview()["stale"] and observer.snapshot == previous
    document["generated_at"] = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
    replacement = path.with_suffix(".new")
    replacement.write_text(json.dumps(document))
    replacement.replace(path)
    await observer.refresh()
    assert observer.overview()["available"] and observer.overview()["stale"]
    path.write_text(json.dumps(snapshot()))
    await observer.refresh()
    assert observer.overview()["available"] and not observer.overview()["stale"]


@pytest.mark.parametrize(
    "mutation",
    [
        lambda d: d.update(schema_version="2"),
        lambda d: d.update(raw_output="NEVER_EXPOSE_SECRET"),
        lambda d: d["runs"][0]["tasks"][0].update(prompt="NEVER_EXPOSE_SECRET"),
        lambda d: d["runs"][0]["usage"].update(cost_usd=float("nan")),
        lambda d: d["runs"][0]["usage"].update(input_tokens=-1),
        lambda d: d["runs"][0]["tasks"].extend(d["runs"][0]["tasks"] * 100),
        lambda d: d.update(exported_runs=2),
        lambda d: d["runs"][0].update(available=False, error="RUN_BUSY"),
        lambda d: d["runs"].append(copy.deepcopy(d["runs"][0])),
    ],
)
async def test_invalid_metadata_retains_last_valid_never_exposes_raw_values(source, mutation):
    observer, path, document = source
    await observer.refresh()
    previous = copy.deepcopy(observer.snapshot)
    mutation(document)
    path.write_text(json.dumps(document))
    await observer.refresh()
    assert observer.error == "INVALID_SNAPSHOT"
    assert observer.snapshot == previous
    assert "NEVER_EXPOSE_SECRET" not in json.dumps(observer.overview())


async def test_bounded_no_follow_regular_file_and_duplicate_keys(source, tmp_path):
    observer, path, _ = source
    path.write_bytes(b"x" * (MAX_BYTES + 1))
    await observer.refresh()
    assert observer.error == "INVALID_SNAPSHOT"
    path.write_text('{"schema_version":"1","schema_version":"2"}')
    await observer.refresh()
    assert observer.error == "INVALID_SNAPSHOT"
    path.unlink()
    private = tmp_path / "private.json"
    private.write_text("NEVER_EXPOSE_SECRET")
    path.symlink_to(private)
    await observer.refresh()
    assert observer.error == "SNAPSHOT_UNAVAILABLE"
    path.unlink()
    path.mkdir()
    await observer.refresh()
    assert observer.error == "INVALID_SNAPSHOT"


async def test_timeout_keeps_one_pending_reader(source, monkeypatch):
    observer, _, document = source
    observer.config.timeout_seconds = 0.1
    reads = []

    def delayed_read():
        reads.append(True)
        time.sleep(0.35)
        return document

    monkeypatch.setattr(observer, "_read", delayed_read)
    await observer.refresh()
    assert observer.error == "TIMEOUT"
    await observer.refresh()
    assert observer.error == "TIMEOUT" and len(reads) == 1
    await asyncio.sleep(0.2)
    await observer.refresh()
    assert observer.error is None and len(reads) == 1


async def test_shutdown_cleans_pending_observer_task(source, monkeypatch):
    observer, _, document = source
    observer.config.timeout_seconds = 0.1

    def delayed_read():
        time.sleep(0.3)
        return document

    async def idle():
        await asyncio.sleep(60)

    monkeypatch.setattr(observer, "_read", delayed_read)
    monitor = Monitor(load_config())
    monkeypatch.setattr(monitor, "run", idle)
    app = create_app(monitor.config, monitor, observer)
    async with app.router.lifespan_context(app):
        await asyncio.sleep(0.15)
        assert observer._pending is not None and not observer._pending.done()
    assert observer._pending is None
    assert not any(task.get_name().startswith("dashboard-") for task in asyncio.all_tasks())
    assert monitor.http.is_closed and monitor.mcp_http.is_closed


async def test_unavailable_run_keeps_unknown_values_and_truncation_counts(source):
    observer, path, document = source
    run = document["runs"][0]
    run.update(available=False, error="RUN_BUSY")
    for key in ["state", "status", "profile", "plan_revision", "work_revision"]:
        run[key] = None
    for key in ["tasks", "attempts", "gates", "history", "evidence", "tool_calls", "failures"]:
        run[key] = []
    run["usage"] = dict.fromkeys(run["usage"])
    document.update(total_runs=3, exported_runs=1, truncated=True)
    path.write_text(json.dumps(document))
    await observer.refresh()
    assert observer.error is None
    assert observer.snapshot["runs"][0]["plan_revision"] is None
    assert observer.snapshot["runs"][0]["usage"]["cost_usd"] is None
    document["truncated"] = False
    path.write_text(json.dumps(document))
    await observer.refresh()
    assert observer.error == "INVALID_SNAPSHOT"


async def test_get_only_cached_metadata_routes_and_local_protections(source):
    observer, path, document = source
    await observer.refresh()
    monitor = Monitor(load_config())
    app = create_app(monitor.config, monitor=monitor, cordis=observer)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://localhost"
        ) as client:
            response = await client.get("/api/cordis")
            assert response.json()["snapshot"] == document
            assert response.headers["cache-control"] == "no-store"
            assert "script-src 'self'" in response.headers["content-security-policy"]
            path.unlink()  # viewer routes use cache, never filesystem reads
            run_path = "/api/cordis/runs/example-run"
            assert (await client.get(run_path)).json() == document["runs"][0]
            evidence_path = run_path + "/evidence/" + "a" * 64
            evidence = (await client.get(evidence_path)).json()
            assert evidence == document["runs"][0]["evidence"][0]
            assert "content" not in evidence and "path" not in evidence
            for route in ["/api/cordis", run_path, evidence_path]:
                for method in ["POST", "PUT", "DELETE"]:
                    assert (await client.request(method, route)).status_code == 405
                assert (
                    await client.get(route, headers={"Origin": "http://evil.example"})
                ).status_code == 403
            assert (await client.get(run_path + "/evidence/no-such-key")).status_code == 404
            assert (await client.get("/api/cordis/runs/no-such-run")).status_code == 404
            assert (
                await client.get(run_path + "/evidence/..%2f..%2fprivate.json")
            ).status_code == 404
            assert (await client.get("/api/cordis?path=/etc/passwd")).json()["snapshot"] == document
    finally:
        await monitor.close()


def test_snapshot_config_readonly_export_mount_and_bounds():
    config = load_config()
    assert config.dashboard.cordis_snapshot_dir is None
    assert compose_config(config)["services"]["dashboard"]["volumes"] == ["./config:/app/config:ro"]
    data = config.model_dump()
    data["dashboard"]["cordis_snapshot_dir"] = "/tmp/cordis-export"
    config = StackConfig.model_validate(data)
    service = compose_config(config)["services"]["dashboard"]
    assert service["environment"]["CORDIS_SNAPSHOT_DIR"] == "/app/cordis"
    assert service["volumes"][-1] == {
        "type": "bind",
        "source": "/tmp/cordis-export",
        "target": "/app/cordis",
        "read_only": True,
        "bind": {"create_host_path": False},
    }
    for directory in ["relative", "/tmp/../runs", "/tmp/${SECRET}", "/tmp/a\nb"]:
        with pytest.raises(ValidationError):
            Dashboard(cordis_snapshot_dir=directory)
    for interval in [4, 3601]:
        with pytest.raises(ValidationError):
            Dashboard(cordis_stale_seconds=interval)
