"use strict";
let cordisView = null, cordisDisconnected = false, cordisRunId = null, cordisTaskId = null;

const known = (value) => value == null ? "Desconhecido" : String(value);
const revision = (plan, work) => `plano ${known(plan)} · trabalho ${known(work)}`;
const duration = (value) => value == null ? "Desconhecida" : `${number(value, 1)} ms`;

function cordisTable(targetId, headers, rows, empty) {
  const target = $(targetId); target.replaceChildren();
  if (!rows.length) { target.append(node("p", empty, "empty")); return; }
  const table = node("table"), head = node("thead"), heading = node("tr"), body = node("tbody");
  headers.forEach((label) => { const cell = node("th", label); cell.scope = "col"; heading.append(cell); });
  head.append(heading);
  rows.forEach((values) => { const row = node("tr"); values.forEach((value) => row.append(node("td", value))); body.append(row); });
  table.append(head, body); target.append(table);
}

function renderCordisTask(run) {
  const task = run.tasks.find((item) => item.id === cordisTaskId);
  const target = $("cordis-task-detail"); target.replaceChildren();
  if (!task) { target.append(node("p", "Selecione uma tarefa.")); return; }
  target.append(node("h4", task.id), node("p", `Responsável: ${task.owner_role}`), node("p", `Estado: ${task.status}`));
  target.append(node("p", `Dependências: ${task.dependencies.length ? task.dependencies.join(", ") : "Nenhuma"}`), node("strong", "Escopo de escrita"));
  const scopes = node("ul"); task.write_scope.forEach((scope) => scopes.append(node("li", scope)));
  target.append(scopes);
  $("cordis-graph").querySelectorAll("button").forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.task === task.id)));
}

function renderCordisRun() {
  const focusedTask = document.activeElement?.dataset?.task;
  const run = cordisView?.snapshot?.runs.find((item) => item.run_id === cordisRunId);
  $("cordis-content").hidden = !run;
  if (!run) return;
  const summary = $("cordis-summary"); summary.replaceChildren();
  const facts = [
    ["Etapa", known(run.state)], ["Estado", known(run.status)], ["Perfil", known(run.profile)],
    ["Revisões", revision(run.plan_revision, run.work_revision)],
    ["Tokens de entrada", run.usage.input_tokens == null ? "Desconhecidos" : number(run.usage.input_tokens)],
    ["Tokens de saída", run.usage.output_tokens == null ? "Desconhecidos" : number(run.usage.output_tokens)],
    ["Custo observado", run.usage.cost_usd == null ? "Desconhecido" : `US$ ${number(run.usage.cost_usd, 6)}`],
    ["Duração observada", duration(run.usage.duration_ms)],
  ];
  facts.forEach(([label, value]) => { const item = node("div"); item.append(node("span", label), node("strong", value)); summary.append(item); });
  const notices = [];
  if (!run.available) notices.push(`Run sem observação válida (${run.error || "UNAVAILABLE"}).`);
  if (run.truncated) notices.push(`Exibição limitada; itens omitidos: ${Object.entries(run.truncated_counts).map(([key, count]) => `${key}: ${number(count)}`).join(" · ")}.`);
  text("cordis-run-notice", notices.join(" ")); $("cordis-run-notice").hidden = !notices.length;
  const graph = $("cordis-graph"); graph.replaceChildren();
  run.tasks.forEach((task) => {
    const card = node("button", null, "cordis-task"); card.type = "button"; card.dataset.task = task.id;
    card.setAttribute("aria-label", `Inspecionar tarefa ${task.id}`);
    card.append(node("strong", task.id), node("span", `${task.owner_role} · ${task.status}`, "badge muted"), node("small", task.dependencies.length ? `← ${task.dependencies.join(", ")}` : "Início · sem dependências"));
    card.addEventListener("click", () => { cordisTaskId = task.id; renderCordisTask(run); }); graph.append(card);
  });
  if (!run.tasks.length) graph.append(node("p", "Nenhuma tarefa disponível.", "empty"));
  if (!run.tasks.some((task) => task.id === cordisTaskId)) cordisTaskId = run.tasks[0]?.id || null;
  renderCordisTask(run);
  if (focusedTask) Array.from(graph.querySelectorAll("button")).find((button) => button.dataset.task === focusedTask)?.focus({preventScroll: true});
  cordisTable("cordis-attempts", ["Tentativa / tarefa", "Provider", "Estado", "Revisões", "Início / fim", "Duração"], run.attempts.map((item) => [
    `${item.id} / ${item.task_id}`, known(item.provider), item.status, revision(item.plan_revision, item.work_revision), `${clock(item.started_at)} / ${clock(item.ended_at)}`, duration(item.duration_ms),
  ]), "Nenhuma tentativa observada.");
  cordisTable("cordis-failures", ["Falha / tarefa", "Código", "Categoria", "Encaminhamento", "Retry autorizado"], run.failures.map((item) => [
    `${item.id} / ${known(item.task_id)}`, item.code, item.category, item.route, item.retry_authorized ? "Sim" : "Não",
  ]), "Nenhuma falha registrada.");
  cordisTable("cordis-gates", ["Gate", "Estado", "Validade", "Ator", "Revisões", "Evidências"], run.gates.map((item) => [
    item.name, item.status === "missing" ? "Pendente" : item.status, item.status === "missing" ? "Pendente" : item.current ? "Atual" : "Anterior / inválido", item.actor_id ? `${item.actor_id} · ${item.actor_role}` : "—", revision(item.plan_revision, item.work_revision), item.evidence.join(", ") || "—",
  ]), "Nenhum gate registrado; aprovações pendentes.");
  cordisTable("cordis-calls", ["Tarefa / tentativa", "Capacidade", "Resultado", "Duração", "Revisões"], run.tool_calls.map((item) => [
    `${item.task_id} / ${known(item.attempt_id)}`, item.capability, item.outcome, duration(item.duration_ms), revision(item.plan_revision, item.work_revision),
  ]), "Nenhuma chamada observada; ausência de recibos não implica zero chamadas.");
  cordisTable("cordis-history", ["Seq.", "Horário", "Evento", "Ator", "Evidências"], run.history.map((item) => [
    item.sequence, clock(item.at), item.type, `${item.actor_id} · ${item.actor_role}`, item.evidence.join(", ") || "—",
  ]), "Nenhum evento disponível.");
  const evidence = $("cordis-evidence"); evidence.replaceChildren();
  run.evidence.forEach((item) => {
    const row = node("div", null, "cordis-evidence-row");
    const link = node("a", item.ref, "contract-button");
    link.href = `/api/cordis/runs/${encodeURIComponent(run.run_id)}/evidence/${encodeURIComponent(item.key)}`;
    link.addEventListener("click", async (event) => {
      event.preventDefault(); const detail = $("cordis-evidence-detail"); detail.hidden = false; detail.textContent = "Consultando metadados…";
      try { const response = await fetch(link.href, {cache: "no-store", signal: AbortSignal.timeout(5000)}); if (!response.ok) throw new Error(); detail.textContent = JSON.stringify(await response.json(), null, 2); }
      catch { detail.textContent = "Metadados indisponíveis. Atualize a observação."; }
      detail.focus();
    });
    row.append(link, node("small", `${item.kind} · ${number(item.bytes)} bytes · ${item.verification} · ${item.available ? "Disponível" : "Disponibilidade não confirmada"}`)); evidence.append(row);
  });
  if (!run.evidence.length) evidence.append(node("p", "Nenhuma evidência registrada.", "empty"));
}

function renderCordis() {
  if (!cordisView) return;
  const view = cordisView, snapshot = view.snapshot;
  const stale = cordisDisconnected || view.stale;
  text("cordis-state", !view.configured ? "Não configurado" : stale ? "Desatualizado" : "Atual", `badge ${stale ? "warn" : "good"}`);
  const messages = [];
  if (!view.configured) messages.push("Configure uma pasta de exportação Cordis para acompanhar runs neste painel.");
  else if (cordisDisconnected) messages.push("Conexão com a observação Cordis interrompida. Exibindo metadados anteriores.");
  else if (!view.available) messages.push(`Exportação indisponível (${view.error}).${snapshot ? " Exibindo a última exportação válida." : " Aguardando uma exportação válida."}`);
  else if (stale) messages.push("Exportação desatualizada. Gere uma nova observação no Cordis para refletir mudanças recentes.");
  else messages.push("Metadados exportados pelo Cordis. Este painel não executa tarefas nem aprova gates.");
  if (snapshot?.truncated) messages.push(`Runs exibidos: ${snapshot.exported_runs} de ${snapshot.total_runs}; exportação limitada.`);
  text("cordis-notice", messages.join(" "));
  text("cordis-time", snapshot ? `Exportação ${clock(view.source_generated_at)} · leitura ${clock(view.observed_at)}` : "Sem exportação");
  const selector = $("cordis-run"); selector.replaceChildren();
  const runs = snapshot?.runs || [];
  runs.forEach((run) => { const option = node("option", `${run.run_id} · ${known(run.state)}${run.available ? "" : " · indisponível"}`); option.value = run.run_id; selector.append(option); });
  selector.disabled = !runs.length;
  if (!runs.length) selector.append(node("option", "Nenhum run observado"));
  if (!runs.some((run) => run.run_id === cordisRunId)) cordisRunId = runs[0]?.run_id || null;
  if (cordisRunId) selector.value = cordisRunId;
  renderCordisRun();
}

async function refreshCordis() {
  try {
    const response = await fetch("/api/cordis", {cache: "no-store", signal: AbortSignal.timeout(5000)});
    if (!response.ok) throw new Error();
    cordisView = await response.json(); cordisDisconnected = false;
  } catch { cordisDisconnected = true; }
  if (cordisView) renderCordis();
  else { text("cordis-state", "Sem conexão", "badge warn"); text("cordis-notice", "Não foi possível consultar a observação Cordis."); }
}

document.addEventListener("DOMContentLoaded", () => {
  $("cordis-run").addEventListener("change", () => { cordisRunId = $("cordis-run").value; cordisTaskId = null; $("cordis-evidence-detail").hidden = true; renderCordisRun(); });
});
