"""Real browser against the running Compose dashboard; optional browser dependency group."""

import asyncio
import copy
import json
import os
from pathlib import Path

import httpx
import httpx2
import pytest
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

playwright = pytest.importorskip("playwright.sync_api")
# Locator assertions have their own timeout, independent of Page actions. Allow
# one catalog refresh (30 s), its bounded request and a browser polling interval.
playwright.expect.set_options(timeout=45000)
URL = os.environ.get("DASHBOARD_ENDPOINT")
pytestmark = pytest.mark.skipif(not URL, reason="set DASHBOARD_ENDPOINT to a running dashboard")


@pytest.fixture(scope="module")
def observed_traffic():
    async def seed():
        async with asyncio.timeout(45), httpx.AsyncClient(trust_env=False) as http:
            while True:
                snapshot = (await http.get(URL + "/api/overview")).json()
                if (
                    snapshot["metrics_available"]
                    and snapshot["status_available"]
                    and snapshot["gateway"]["ready"]
                ):
                    break
                await asyncio.sleep(0.2)
            token = os.getenv("MCP_STACK_TOKEN")
            headers = {"Authorization": "Bearer " + token} if token else {}
            async with httpx2.AsyncClient(headers=headers, trust_env=False) as mcp_http:
                async with Client(
                    streamable_http_client(
                        os.getenv("STACK_ENDPOINT", snapshot["endpoint"]), http_client=mcp_http
                    ),
                    cache=None,
                ) as client:
                    assert not (
                        await client.call_tool("demo.identity_matrix", {"size": 2})
                    ).is_error
                    assert (await client.call_tool("demo.contract_error", {})).is_error

    # Seed after the observer's baseline, independently of image/browser install
    # speed. These are native fixture calls made by tests, never by the dashboard.
    asyncio.run(seed())


@pytest.fixture
def page(observed_traffic):
    with playwright.sync_playwright() as runner:
        browser = runner.chromium.launch(
            executable_path=os.getenv("BROWSER_EXECUTABLE_PATH"), headless=True
        )
        context = browser.new_context(
            viewport={"width": 1440, "height": 1100}, color_scheme="light"
        )
        page = context.new_page()
        page.set_default_timeout(45000)
        try:
            yield page
        finally:
            context.close()
            browser.close()


def test_live_dashboard_navigation_search_pause_and_mobile(page, tmp_path):
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    response = page.goto(URL)
    assert response.ok
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    playwright.expect(page.locator("#gateway-value")).to_have_text("Pronto")
    playwright.expect(page.locator("#tools-value")).to_have_text("5")
    playwright.expect(page.locator("#tool-list .tool-card")).to_have_count(5)
    playwright.expect(page.locator("#server-rows .badge.good")).to_have_count(1)
    playwright.expect(page.locator("#server-rows")).to_contain_text("Desabilitado")
    # No synthetic chart data: both series must contain actual gateway samples.
    playwright.expect(page.locator("#latency-chart circle")).not_to_have_count(0)
    playwright.expect(page.locator("#errors-chart circle")).not_to_have_count(0)
    playwright.expect(page.locator("#p95-value")).to_contain_text("≤")
    page.get_by_role("link", name="Catálogo MCP").click()
    page.get_by_role("searchbox").fill("identity_matrix")
    playwright.expect(page.locator(".tool-card")).to_have_count(1)
    playwright.expect(page.locator(".tool-card")).to_contain_text("outputSchema")
    page.get_by_role("searchbox").fill("no-such-tool")
    playwright.expect(page.locator("#tool-list")).to_contain_text("Nenhuma ferramenta")
    page.get_by_role("searchbox").fill("")
    page.get_by_role("button", name="Pausar", exact=True).click()
    playwright.expect(page.locator("#notice")).to_contain_text("pausada")
    playwright.expect(page.locator("#pause")).to_have_attribute("aria-pressed", "true")
    with page.expect_response("**/api/overview"):
        page.get_by_role("button", name="Atualizar", exact=False).click()
    playwright.expect(page.locator("#pause")).to_have_text("Retomar")
    page.get_by_role("button", name="Retomar").click()
    playwright.expect(page.locator("#notice")).to_be_hidden()

    page.get_by_role("link", name="Visão geral").click()
    screenshots = Path(os.getenv("DASHBOARD_SCREENSHOT_DIR", str(tmp_path)))
    screenshots.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(screenshots / "dashboard-desktop.png"), full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    page.get_by_role("searchbox").fill("artifact")
    playwright.expect(page.locator(".tool-card")).to_have_count(1)
    page.evaluate("window.scrollTo(0, 0)")
    page.screenshot(path=str(screenshots / "dashboard-mobile.png"), full_page=True)
    assert errors == []


def test_dark_theme_persistence_contract_modal_keyboard_and_copy(page, tmp_path):
    page.emulate_media(color_scheme="dark")
    page.goto(URL)
    playwright.expect(page.locator("html")).to_have_attribute("data-theme", "dark")
    page.get_by_role("button", name="Ativar modo claro").click()
    playwright.expect(page.locator("html")).to_have_attribute("data-theme", "light")
    page.reload()
    playwright.expect(page.locator("html")).to_have_attribute("data-theme", "light")
    page.get_by_role("button", name="Ativar modo escuro").click()
    playwright.expect(page.locator("#tool-list .tool-card")).to_have_count(5)
    screenshots = Path(os.getenv("DASHBOARD_SCREENSHOT_DIR", str(tmp_path)))
    screenshots.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(screenshots / "dashboard-dark.png"), full_page=True)
    button = page.get_by_role("button", name="Ver contrato de demo.identity_matrix", exact=True)
    expected = page.request.get(URL + "/api/contracts/demo.identity_matrix").json()["tool"]
    button.click()
    dialog = page.get_by_role("dialog", name="demo.identity_matrix", exact=True)
    playwright.expect(dialog).to_be_visible()
    playwright.expect(page.locator("#contract-status")).to_have_text(
        "Schema completo publicado pelo servidor."
    )
    assert json.loads(page.locator("#contract-json").inner_text()) == expected["outputSchema"]
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    page.get_by_role("button", name="Copiar JSON", exact=True).click()
    playwright.expect(page.locator("#contract-copy")).to_have_text("JSON copiado ✓")
    assert json.loads(page.evaluate("navigator.clipboard.readText()")) == expected["outputSchema"]
    page.get_by_role("tab", name="Resposta", exact=True).focus()
    page.keyboard.press("ArrowRight")
    playwright.expect(page.get_by_role("tab", name="Entrada", exact=True)).to_have_attribute(
        "aria-selected", "true"
    )
    assert json.loads(page.locator("#contract-json").inner_text()) == expected["inputSchema"]
    page.keyboard.press("ArrowLeft")
    assert json.loads(page.locator("#contract-json").inner_text()) == expected["outputSchema"]
    page.screenshot(path=str(screenshots / "dashboard-contract-dark.png"))
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate(
        "document.querySelector('dialog').getBoundingClientRect().right <= window.innerWidth"
    )
    page.screenshot(path=str(screenshots / "dashboard-contract-mobile.png"))
    page.keyboard.press("Escape")
    playwright.expect(dialog).not_to_be_visible()
    playwright.expect(button).to_be_focused()


def test_missing_output_schema_and_contract_text_injection(page):
    page.goto(URL)
    playwright.expect(page.locator("#tool-list .tool-card")).to_have_count(5)
    original = page.request.get(URL + "/api/contracts/demo.echo").json()
    original["tool"]["outputSchema"] = None
    original["tool"]["inputSchema"] = {
        "description": '<img src=x onerror="window.INJECTED=true">',
        "type": "object",
    }
    page.route("**/api/contracts/demo.echo", lambda route: route.fulfill(json=original))
    page.get_by_role("button", name="Ver contrato de demo.echo", exact=True).click()
    playwright.expect(page.locator("#contract-json")).to_contain_text("não publica um outputSchema")
    playwright.expect(page.locator("#contract-copy")).to_be_disabled()
    page.get_by_role("tab", name="Entrada", exact=True).click()
    assert (
        json.loads(page.locator("#contract-json").inner_text()) == original["tool"]["inputSchema"]
    )
    assert page.locator("#contract-json img").count() == 0
    assert page.evaluate("window.INJECTED === undefined")
    page.get_by_role("button", name="Fechar contrato").click()
    playwright.expect(page.locator("#contract-dialog")).not_to_be_visible()


def test_browser_staleness_recovery_and_untrusted_catalog_text(page):
    page.goto(URL)
    playwright.expect(page.locator("#gateway-value")).to_have_text("Pronto")
    snapshot = page.request.get(URL + "/api/overview").json()
    stale = copy.deepcopy(snapshot)
    stale.update(
        status_available=False,
        metrics_available=False,
        status_error="UNREACHABLE",
        metrics_error="TIMEOUT",
    )
    stale["catalog"]["available"] = False
    stale["servers"][0]["display_name"] = '<img src=x onerror="window.INJECTED=true">'
    stale["catalog"]["tools"][0]["description"] = "<script>window.INJECTED=true</script>"
    page.route("**/api/overview", lambda route: route.fulfill(json=stale))
    page.get_by_role("button", name="Atualizar", exact=False).click()
    playwright.expect(page.locator("#gateway-value")).to_have_text("Sem conexão")
    playwright.expect(page.locator("#server-rows .badge.good")).to_have_count(0)
    playwright.expect(page.locator("#notice")).to_contain_text("desatualizados")
    playwright.expect(page.locator("#server-rows")).to_contain_text("<img")
    assert page.evaluate("window.INJECTED === undefined")
    assert page.locator("#server-rows img").count() == 0
    page.unroute("**/api/overview")
    page.get_by_role("button", name="Atualizar", exact=False).click()
    playwright.expect(page.locator("#gateway-value")).to_have_text("Pronto")
    playwright.expect(page.locator("#notice")).to_be_hidden()
