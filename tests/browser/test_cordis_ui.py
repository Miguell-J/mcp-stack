"""Real Chromium + isolated source HTTP app, sanitized synthetic export only."""

import copy
import json
import os
import socket
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from tests.cordis_fixture import snapshot

playwright = pytest.importorskip("playwright.sync_api")


@pytest.fixture(scope="module")
def live_cordis(tmp_path_factory):
    directory = tmp_path_factory.mktemp("cordis-ui-export")
    document = snapshot()
    second = copy.deepcopy(document["runs"][0])
    second["run_id"] = "second-run"
    second["tasks"] = []
    document["runs"].append(second)
    document.update(total_runs=2, exported_runs=2)
    path = directory / "snapshot.json"
    path.write_text(json.dumps(document))
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    endpoint = f"http://127.0.0.1:{port}"
    with (directory / "server.log").open("w") as log:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "tests.browser.cordis_app:fixture_app",
                "--factory",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--no-access-log",
            ],
            env={**os.environ, "CORDIS_TEST_EXPORT": str(directory)},
            stdout=log,
            stderr=log,
        )
        try:
            deadline = time.monotonic() + 15
            with httpx.Client(trust_env=False) as client:
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        pytest.fail(
                            "isolated dashboard fixture failed: "
                            + (directory / "server.log").read_text()
                        )
                    try:
                        response = client.get(endpoint + "/api/cordis")
                        if response.status_code == 200 and response.json()["available"]:
                            break
                    except httpx.TransportError:
                        pass
                    time.sleep(0.1)
                else:
                    pytest.fail("isolated dashboard did not become ready")
            yield endpoint, path, document
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


@pytest.fixture
def page():
    with playwright.sync_playwright() as runner:
        browser = runner.chromium.launch(
            executable_path=os.getenv("BROWSER_EXECUTABLE_PATH", "/usr/bin/chromium"), headless=True
        )
        context = browser.new_context(viewport={"width": 1440, "height": 1100})
        try:
            yield context.new_page()
        finally:
            context.close()
            browser.close()


def test_live_cordis_graph_details_evidence_and_preserved_contract(page, live_cordis, tmp_path):
    endpoint, _, _ = live_cordis
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    assert page.goto(endpoint).ok
    playwright.expect(page.locator("#cordis-state")).to_have_text("Atual")
    playwright.expect(page.locator("#cordis-graph .cordis-task")).to_have_count(2)
    page.get_by_role("button", name="Inspecionar tarefa validate", exact=True).click()
    playwright.expect(page.locator("#cordis-task-detail")).to_contain_text(
        "Dependências: implement"
    )
    playwright.expect(page.locator("#cordis-summary")).to_contain_text("Desconhecido")
    playwright.expect(page.locator("#cordis-attempts")).to_contain_text("codex")
    playwright.expect(page.locator("#cordis-failures")).to_contain_text("TEST_FAILED")
    playwright.expect(page.locator("#cordis-gates")).to_contain_text("independent-reviewer")
    playwright.expect(page.locator("#cordis-history")).to_contain_text("transition")
    playwright.expect(page.locator("#cordis-calls")).to_contain_text("catalog.read")
    page.locator("#cordis-evidence a").click()
    playwright.expect(page.locator("#cordis-evidence-detail")).to_contain_text("registration_only")
    metadata = json.loads(page.locator("#cordis-evidence-detail").inner_text())
    assert metadata["bytes"] == 42 and "content" not in metadata
    page.locator("#cordis-run").select_option("second-run")
    playwright.expect(page.locator("#cordis-graph")).to_contain_text("Nenhuma tarefa")
    page.locator("#cordis-run").select_option("example-run")
    page.get_by_role("button", name="Ver contrato de demo.fixture", exact=True).click()
    playwright.expect(page.locator("#contract-dialog")).to_be_visible()
    assert json.loads(page.locator("#contract-json").inner_text())["properties"]["count"] == {
        "type": "integer"
    }
    page.keyboard.press("Escape")
    page.get_by_role("button", name="Ativar modo escuro").click()
    page.reload()
    playwright.expect(page.locator("html")).to_have_attribute("data-theme", "dark")
    screenshots = Path(os.getenv("DASHBOARD_SCREENSHOT_DIR", str(tmp_path)))
    screenshots.mkdir(parents=True, exist_ok=True)
    page.locator("#cordis").scroll_into_view_if_needed()
    page.screenshot(path=str(screenshots / "cordis-desktop.png"), full_page=True)
    page.locator("#cordis").screenshot(path=str(screenshots / "cordis-panel-desktop.png"))
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.screenshot(path=str(screenshots / "cordis-mobile.png"), full_page=True)
    page.locator("#cordis").screenshot(path=str(screenshots / "cordis-panel-mobile.png"))
    assert errors == []


def test_live_source_staleness_missing_recovery_and_text_injection(page, live_cordis):
    endpoint, path, original = live_cordis
    document = copy.deepcopy(original)
    document["generated_at"] = (datetime.now(UTC) - timedelta(minutes=10)).isoformat()
    document["runs"][0]["tasks"][0]["owner_role"] = '<img src=x onerror="window.INJECTED=true">'
    document["runs"][0]["usage"] = dict.fromkeys(document["runs"][0]["usage"])
    document["runs"][0]["gates"][0]["current"] = False
    document["runs"][0]["tool_calls"][0].update(outcome="uncertain", duration_ms=None)
    try:
        replacement = path.with_suffix(".new")
        replacement.write_text(json.dumps(document))
        replacement.replace(path)
        page.goto(endpoint)
        playwright.expect(page.locator("#cordis-state")).to_have_text(
            "Desatualizado", timeout=10000
        )
        playwright.expect(page.locator("#cordis-graph")).to_contain_text("<img")
        playwright.expect(page.locator("#cordis-gates")).to_contain_text("Anterior / inválido")
        playwright.expect(page.locator("#cordis-calls")).to_contain_text("uncertain")
        assert page.locator("#cordis img").count() == 0
        assert page.evaluate("window.INJECTED === undefined")
        path.unlink()
        playwright.expect(page.locator("#cordis-notice")).to_contain_text(
            "SNAPSHOT_MISSING", timeout=10000
        )
        playwright.expect(page.locator("#cordis-graph .cordis-task")).to_have_count(2)
        fresh = copy.deepcopy(original)
        fresh["generated_at"] = datetime.now(UTC).isoformat()
        path.write_text(json.dumps(fresh))
        playwright.expect(page.locator("#cordis-state")).to_have_text("Atual", timeout=10000)
        playwright.expect(page.locator("#cordis-gates")).to_contain_text("Atual")
    finally:
        path.write_text(json.dumps(original))


def test_disabled_cordis_keeps_gateway_catalog_and_keyboard_navigation(page, live_cordis):
    endpoint, _, _ = live_cordis
    page.route(
        "**/api/cordis",
        lambda route: route.fulfill(
            json={
                "configured": False,
                "available": False,
                "stale": True,
                "observed_at": None,
                "source_generated_at": None,
                "error": "DISABLED",
                "snapshot": None,
            }
        ),
    )
    page.goto(endpoint)
    playwright.expect(page.locator("#cordis-state")).to_have_text("Não configurado")
    playwright.expect(page.locator("#cordis-run")).to_be_disabled()
    playwright.expect(page.locator("#cordis-content")).to_be_hidden()
    playwright.expect(page.locator("#gateway-value")).to_have_text("Pronto")
    playwright.expect(page.locator("#tool-list .tool-card")).to_have_count(1)
    page.unroute("**/api/cordis")
    page.get_by_role("button", name="Atualizar", exact=False).click()
    button = page.get_by_role("button", name="Inspecionar tarefa validate", exact=True)
    playwright.expect(button).to_be_visible()
    button.focus()
    page.keyboard.press("Enter")
    playwright.expect(page.locator("#cordis-task-detail")).to_contain_text(
        "Dependências: implement"
    )
