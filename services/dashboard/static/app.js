"use strict";
const $ = (id) => document.getElementById(id);
const number = (value, digits = 0) => value == null ? "—" : new Intl.NumberFormat("pt-BR", {maximumFractionDigits: digits}).format(value);
const clock = (value) => value ? new Date(value).toLocaleTimeString("pt-BR") : "—";
const age = (seconds) => seconds == null ? "—" : seconds < 60 ? `${number(seconds)} s` : `${number(seconds / 60)} min`;
const node = (tag, text, cls) => { const el = document.createElement(tag); if (text != null) el.textContent = text; if (cls) el.className = cls; return el; };
let data = null, paused = false, busy = false, disconnected = false, timer = null;
let contractView = null, contractSide = "outputSchema", contractRequest = null, contractOpener = null;

function themeButton() {
  const dark = document.documentElement.dataset.theme === "dark";
  text("theme-label", dark ? "Claro" : "Escuro");
  $("theme").setAttribute("aria-label", dark ? "Ativar modo claro" : "Ativar modo escuro");
}

function contractStatus() {
  if (!contractView) return;
  const current = contractView.available && !disconnected && data?.status_available && data?.catalog.available && data.catalog.tools.some((tool) => tool.name === contractView.tool.name);
  text("contract-status", current ? "Schema completo publicado pelo servidor." : "Último contrato conhecido. A observação atual está indisponível.");
}

function showContractSchema(side) {
  contractSide = side;
  for (const [id, key] of [["tab-output", "outputSchema"], ["tab-input", "inputSchema"]]) {
    const selected = key === side;
    $(id).setAttribute("aria-selected", String(selected));
    $(id).tabIndex = selected ? 0 : -1;
  }
  $("schema-panel").setAttribute("aria-labelledby", side === "outputSchema" ? "tab-output" : "tab-input");
  const schema = contractView?.tool[side];
  text("contract-json", !contractView ? "Carregando…" : schema == null ? "Esta ferramenta não publica um outputSchema." : JSON.stringify(schema, null, 2));
  $("schema-panel").scrollTop = 0;
  $("contract-copy").disabled = schema == null;
  text("contract-copy", "Copiar JSON");
  text("contract-help", side === "outputSchema" ? "outputSchema descreve structuredContent de respostas bem-sucedidas. Erros usam isError; content e _meta fazem parte do envelope MCP." : "inputSchema descreve os argumentos aceitos por tools/call. O modal exibe o schema original, incluindo definições e referências locais.");
}

async function openContract(tool) {
  contractRequest?.abort(); contractRequest = new AbortController();
  const request = contractRequest;
  contractOpener = tool.name; contractView = null;
  text("contract-title", tool.name);
  text("contract-description", tool.description || "Schemas publicados pelo servidor MCP.");
  text("contract-status", "Carregando contrato…"); text("contract-observed", "—");
  showContractSchema("outputSchema");
  $("contract-dialog").showModal();
  try {
    const response = await fetch(`/api/contracts/${encodeURIComponent(tool.name)}`, {cache: "no-store", signal: AbortSignal.any([request.signal, AbortSignal.timeout(5000)])});
    if (!response.ok) throw new Error("Contract unavailable");
    const view = await response.json();
    if (request.signal.aborted) return;
    contractView = view;
    text("contract-description", view.tool.description || "Schemas publicados pelo servidor MCP.");
    text("contract-observed", `Contrato observado às ${clock(view.observed_at)}`);
    contractStatus(); showContractSchema(contractSide);
  } catch {
    if (!request.signal.aborted) { text("contract-status", "Não foi possível obter o contrato. Feche e abra o modal para tentar novamente."); text("contract-json", "Contrato indisponível."); }
  }
}

function text(id, value, cls) { $(id).textContent = value; if (cls) $(id).className = cls; }
function chart(samples, id = "chart", field = "calls_per_minute", color = "#639f72") {
  const svg = $(id), ns = "http://www.w3.org/2000/svg";
  svg.replaceChildren();
  const width = Math.max(280, svg.clientWidth);
  svg.setAttribute("viewBox", `0 0 ${width} 160`);
  const draw = (tag, attributes, label) => { const el = document.createElementNS(ns, tag); for (const [key, value] of Object.entries(attributes)) el.setAttribute(key, String(value)); if (label) el.textContent = label; svg.append(el); };
  const values = samples.map((sample) => sample[field]);
  const max = field === "error_percent" ? 100 : Math.max(1, ...values.filter((value) => value != null));
  const dark = document.documentElement.dataset.theme === "dark";
  for (let i = 0; i < 4; i++) {
    const y = 12 + i * 43;
    draw("line", {x1: 32, x2: width, y1: y, y2: y, stroke: dark ? "#304237" : "#e7eee8", "stroke-dasharray": "3 5"});
    draw("text", {x: 0, y: y + 3, fill: dark ? "#a9beb0" : "#718574", "font-size": 9}, number(max * (1 - i / 3), 1));
  }
  let segment = [];
  const flush = () => { if (segment.length > 1) draw("polyline", {points: segment.join(" "), fill: "none", stroke: color, "stroke-width": 2.2, "stroke-linejoin": "round"}); segment = []; };
  values.forEach((value, i) => {
    if (value == null) { flush(); return; }
    const x = 32 + (width - 34) * i / Math.max(1, values.length - 1), y = 141 - 129 * value / max;
    segment.push(`${x},${y}`);
    draw("circle", {cx: x, cy: y, r: 2.3, fill: color});
  });
  flush();
  $(`${id}-empty`).hidden = values.some((value) => value != null);
  text(`${id}-start`, samples.length ? clock(samples[0].at) : "—");
  text(`${id}-end`, samples.length ? clock(samples.at(-1).at) : "Agora");
}

function charts() {
  if (!data) return;
  chart(data.history);
  chart(data.history, "latency-chart", "average_ms", "#699db5");
  chart(data.history, "errors-chart", "error_percent", "#bc8876");
}

function renderCatalog() {
  if (!data) return;
  const catalog = data.catalog;
  const query = $("search").value.toLocaleLowerCase("pt-BR").trim();
  const tools = catalog.tools.filter((tool) => `${tool.name} ${tool.description || ""}`.toLocaleLowerCase("pt-BR").includes(query));
  const target = $("tool-list"); target.replaceChildren();
  const stale = disconnected || !data.status_available || !catalog.available;
  text("catalog-note", `${stale ? "Último catálogo conhecido" : "tools/list via SDK oficial"} · coleta ${clock(catalog.observed_at)} · intervalo 30 s`);
  for (const tool of tools) {
    const card = node("article", null, "tool-card");
    const description = node("p", tool.description || "Sem descrição publicada.");
    description.title = tool.description || "";
    const tags = node("div", null, "schema-tags");
    if (tool.input_schema) tags.append(node("span", "inputSchema"));
    if (tool.output_schema) tags.append(node("span", "outputSchema"));
    const button = node("button", "Ver contrato de resposta ↗", "contract-button");
    button.dataset.tool = tool.name;
    button.setAttribute("aria-label", `Ver contrato de ${tool.name}`);
    button.addEventListener("click", () => openContract(tool));
    card.append(node("h3", tool.name), description, tags, button); target.append(card);
  }
  if (!tools.length) target.append(node("p", query ? "Nenhuma ferramenta corresponde à busca." : catalog.observed_at ? "Nenhuma ferramenta no catálogo observado." : "Catálogo ainda indisponível. Aguardando o gateway MCP.", "empty"));
}

function render() {
  if (!data) return;
  const fresh = !disconnected && data.status_available;
  const metricsFresh = !disconnected && data.metrics_available;
  const gateway = data.gateway, totals = data.totals;
  const enabled = data.servers.filter((server) => server.enabled);
  const ready = enabled.filter((server) => server.status?.readyToRoute).length;
  const fullyHealthy = fresh && enabled.every((server) => server.status?.state === "ONLINE" && !server.status?.stale);
  const healthy = fresh && gateway?.ready;
  const status = !fresh ? "Sem conexão" : healthy ? fullyHealthy ? "Pronto" : "Degradado" : "Não pronto";
  const color = !fresh ? "muted" : healthy ? fullyHealthy ? "good" : "warn" : "bad";
  text("gateway-value", status, `summary-value word ${color}`);
  text("gateway-note", gateway ? `MCP One ${gateway.version}${fresh ? "" : " · última observação"}` : "Aguardando observação");
  text("servers-value", fresh ? `${ready} / ${enabled.length}` : "—");
  text("servers-note", `${data.servers.length - enabled.length} desabilitado(s) nos manifestos`);
  text("tools-value", gateway ? number(gateway.tools) : "—");
  text("tools-note", gateway ? `${fresh ? "Geração" : "Última geração"} ${gateway.generation}` : "Catálogo indisponível");
  text("calls-value", number(totals?.calls));
  text("nav-count", enabled.length); text("server-count", data.servers.length);
  text("stack-version", `v${data.stack_version} · MCP ${data.protocol}`);
  text("topology-servers", `${enabled.length} servidor(es) habilitado(s)`);
  text("topology-tools", `${number(gateway?.tools)} tools no catálogo`);
  $("topology-dot").className = `dot ${color}`;
  text("endpoint", data.endpoint);
  const errors = [];
  if (disconnected) errors.push("Conexão com o painel interrompida. Exibindo as últimas observações recebidas.");
  else if (!data.status_available) errors.push(`Gateway sem observação atual (${data.status_error}). Os dados anteriores estão desatualizados.`);
  else if (!gateway?.ready) errors.push("O gateway responde, mas ainda não está pronto para atender chamadas úteis.");
  else if (!fullyHealthy) errors.push("Operação parcial: consulte os servidores degradados ou catálogos desatualizados abaixo.");
  if (!data.metrics_available) errors.push(`Métricas indisponíveis (${data.metrics_error}); valores anteriores não são atuais.`);
  if (!data.catalog.available) errors.push("Discovery do catálogo indisponível; próxima tentativa automática em até 30 segundos após a coleta anterior.");
  if (paused) errors.push("Atualização da tela pausada. Use Atualizar ou Retomar para obter novas observações.");
  $("notice").hidden = errors.length === 0;
  text("notice", errors.join(" "));
  $("live").replaceChildren(node("span", null, `dot ${disconnected ? "bad" : paused ? "warn" : ""}`), document.createTextNode(disconnected ? "Desconectado" : paused ? "Pausado" : "Ao vivo"));
  $("live").className = `live ${disconnected ? "bad" : paused ? "warn" : ""}`;
  text("updated", `Gateway observado às ${clock(data.observed_at)}`);
  text("metrics-time", `${metricsFresh ? "Coleta" : "Última coleta"} ${clock(data.metrics_at)}`);
  text("latency-value", data.average_ms == null ? "—" : `${number(data.average_ms, 1)} ms`);
  text("p95-value", data.p95_upper_ms == null ? data.p95_overflow ? "Fora da escala" : "—" : `≤ ${number(data.p95_upper_ms, 1)} ms`);
  const interval = metricsFresh ? data.history.at(-1) : null;
  text("interval-latency", number(interval?.average_ms, 1));
  text("interval-p95", interval?.p95_upper_ms == null ? "—" : `≤ ${number(interval.p95_upper_ms, 1)} ms`);
  text("error-rate-value", number(interval?.error_percent, 1));
  text("domain-value", number(totals?.domain_errors)); text("infra-value", number(totals?.infra_failures));
  text("timeout-value", `Timeouts: ${number(totals?.timeouts)} · circuitos abertos: ${number(totals?.circuit_opens)}`);
  text("refresh-value", number(totals?.refreshes));
  text("cache-value", `Catálogo: ${number(totals?.cache_hits)} hits / ${number(totals?.cache_misses)} misses`);
  text("rate-value", metricsFresh ? number(data.history.at(-1)?.calls_per_minute, 1) : "—");
  text("sample-count", `${data.history.length} / 120 amostras`);
  charts();
  const rows = $("server-rows"); rows.replaceChildren();
  for (const server of data.servers) {
    const state = server.status;
    let label = "Desabilitado", tone = "muted";
    if (server.enabled) {
      if (!fresh || !state) label = "Sem observação";
      else { label = ({ONLINE: "Online", DEGRADED: "Degradado", OFFLINE: "Offline", CIRCUIT_OPEN: "Circuito aberto", STARTING: "Iniciando", UNKNOWN: "Desconhecido"})[state.state]; tone = state.state === "ONLINE" ? "good" : state.state === "DEGRADED" ? "warn" : "bad"; }
    }
    const row = node("tr"), name = node("td");
    const title = node("span", server.display_name, "server-name"); title.title = server.display_name;
    name.append(title, node("span", `${server.id} · ${server.namespace}`, "server-id"));
    const statusCell = node("td"); statusCell.append(node("span", label, `badge ${tone}`));
    const circuit = !server.enabled || !state ? "—" : ({CLOSED: "Fechado", OPEN: "Aberto", HALF_OPEN: "Em recuperação"})[state.circuit];
    const catalog = !server.enabled ? "A integrar" : !state?.catalogAvailable ? "Indisponível" : `${!fresh || state.stale ? "Desatualizado" : "Atual"} · ${age(state.catalogAgeSeconds)}`;
    row.append(name, statusCell, node("td", state && server.enabled ? number(state.tools) : "—"), node("td", number(server.metrics?.calls)), node("td", server.average_ms == null ? "—" : `${number(server.average_ms, 1)} ms`), node("td", server.error_percent == null ? "—" : `${number(server.error_percent, 1)} %`), node("td", `${circuit}${!fresh && state && server.enabled ? " (anterior)" : ""}`), node("td", catalog));
    rows.append(row);
  }
  if (!data.servers.length) { const row = node("tr"), cell = node("td", "Nenhum servidor configurado. Adicione um manifesto em config/servers.d.", "empty"); cell.colSpan = 8; row.append(cell); rows.append(row); }
  renderCatalog();
  if ($("contract-dialog").open) contractStatus();
}

async function refresh() {
  if (busy) return;
  busy = true; $("refresh").disabled = true;
  clearTimeout(timer);
  try {
    const response = await fetch("/api/overview", {cache: "no-store", signal: AbortSignal.timeout(5000)});
    if (!response.ok) throw new Error("Observation unavailable");
    data = await response.json(); disconnected = false; render();
  } catch {
    disconnected = true;
    if (data) render();
    else { $("notice").hidden = false; text("notice", "Não foi possível conectar ao painel. Uma nova tentativa será feita automaticamente."); text("live", "Desconectado", "live bad"); }
  } finally {
    busy = false; $("refresh").disabled = false;
    if (!paused) timer = setTimeout(refresh, (data?.poll_seconds || 5) * 1000);
  }
}
$("refresh").addEventListener("click", refresh);
$("pause").addEventListener("click", () => { paused = !paused; $("pause").setAttribute("aria-pressed", String(paused)); text("pause", paused ? "Retomar" : "Pausar"); clearTimeout(timer); render(); if (!paused) refresh(); });
$("search").addEventListener("input", renderCatalog);
$("copy").addEventListener("click", async () => { if (!data) return; try { await navigator.clipboard.writeText(data.endpoint); text("copy", "✓"); } catch { text("copy", "!"); $("copy").title = "Selecione o endpoint para copiar"; } setTimeout(() => text("copy", "⧉"), 2000); });
document.querySelectorAll(".nav-link").forEach((link) => link.addEventListener("click", () => { document.querySelectorAll(".nav-link").forEach((item) => item.classList.remove("active")); link.classList.add("active"); }));
window.addEventListener("resize", charts);
$("theme").addEventListener("click", () => {
  const theme = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = theme;
  try { localStorage.setItem("mcp-stack-theme", theme); } catch { /* Theme still works without storage. */ }
  themeButton(); charts();
});
$("contract-close").addEventListener("click", () => $("contract-dialog").close());
$("contract-dialog").addEventListener("close", () => {
  contractRequest?.abort(); contractView = null;
  const opener = Array.from(document.querySelectorAll(".contract-button")).find((button) => button.dataset.tool === contractOpener);
  (opener || $("search")).focus();
});
$("contract-dialog").addEventListener("click", (event) => {
  if (event.target !== $("contract-dialog")) return;
  const box = $("contract-dialog").getBoundingClientRect();
  if (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom) $("contract-dialog").close();
});
for (const [id, side] of [["tab-output", "outputSchema"], ["tab-input", "inputSchema"]]) {
  $(id).addEventListener("click", () => showContractSchema(side));
  $(id).addEventListener("keydown", (event) => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const output = event.key === "Home" || event.key !== "End" && side !== "outputSchema";
    showContractSchema(output ? "outputSchema" : "inputSchema");
    $(output ? "tab-output" : "tab-input").focus();
  });
}
$("contract-copy").addEventListener("click", async () => {
  const schema = contractView?.tool[contractSide]; if (schema == null) return;
  try { await navigator.clipboard.writeText(JSON.stringify(schema, null, 2)); text("contract-copy", "JSON copiado ✓"); }
  catch { text("contract-copy", "Selecione o JSON para copiar"); }
});
themeButton();
refresh();
