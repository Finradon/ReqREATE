const state = {
  rules: [],
  actions: [],
  busy: false,
  graphNetwork: null,
  graphNodes: new Map(),
  graphEdges: new Map(),
};

const el = {
  actionList: document.querySelector("#actionList"),
  applyRuleBtn: document.querySelector("#applyRuleBtn"),
  bridgeHeight: document.querySelector("#bridgeHeight"),
  bridgeLength: document.querySelector("#bridgeLength"),
  bridgeWidth: document.querySelector("#bridgeWidth"),
  buildingCount: document.querySelector("#buildingCount"),
  busyBadge: document.querySelector("#busyBadge"),
  configPill: document.querySelector("#configPill"),
  emptyState: document.querySelector("#emptyState"),
  graphDetailBody: document.querySelector("#graphDetailBody"),
  graphDetailTitle: document.querySelector("#graphDetailTitle"),
  graphEmpty: document.querySelector("#graphEmpty"),
  graphNetwork: document.querySelector("#graphNetwork"),
  graphSummary: document.querySelector("#graphSummary"),
  historyList: document.querySelector("#historyList"),
  loader: document.querySelector("#loader"),
  loaderText: document.querySelector("#loaderText"),
  modelViewer: document.querySelector("#modelViewer"),
  moduleCount: document.querySelector("#moduleCount"),
  nodeCount: document.querySelector("#nodeCount"),
  previewBadge: document.querySelector("#previewBadge"),
  previewBtn: document.querySelector("#previewBtn"),
  previewComponents: document.querySelector("#previewComponents"),
  previewDetail: document.querySelector("#previewDetail"),
  previewDetailText: document.querySelector("#previewDetailText"),
  previewReason: document.querySelector("#previewReason"),
  previewRoot: document.querySelector("#previewRoot"),
  refreshGraphBtn: document.querySelector("#refreshGraphBtn"),
  repeatInput: document.querySelector("#repeatInput"),
  resetBtn: document.querySelector("#resetBtn"),
  ruleSelect: document.querySelector("#ruleSelect"),
  statusText: document.querySelector("#statusText"),
  stepBadge: document.querySelector("#stepBadge"),
  toast: document.querySelector("#toast"),
};

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const payload = await response.json();
  if (!response.ok || payload.ok === false) {
    throw new Error(payload.error || `Request failed: ${response.status}`);
  }
  return payload;
}

function payload(extra = {}) {
  return JSON.stringify({
    preview_detail: el.previewDetail.value,
    bridge_parameters: bridgeParameters(),
    ...extra,
  });
}

function bridgeParameters() {
  return {
    length: numericValue(el.bridgeLength),
    width: numericValue(el.bridgeWidth),
    height: numericValue(el.bridgeHeight),
  };
}

function numericValue(input) {
  return input.value === "" ? null : Number.parseFloat(input.value);
}

function setBusy(isBusy, text = "Running rule execution...") {
  state.busy = isBusy;
  document.body.classList.toggle("is-busy", isBusy);
  el.loader.classList.toggle("hidden", !isBusy);
  el.loaderText.textContent = text;
  el.busyBadge.textContent = isBusy ? "Running" : "Idle";
  el.busyBadge.classList.toggle("badge-soft", !isBusy);

  [
    el.applyRuleBtn,
    el.previewBtn,
    el.refreshGraphBtn,
    el.resetBtn,
    el.ruleSelect,
    el.repeatInput,
    el.previewDetail,
    el.bridgeLength,
    el.bridgeWidth,
    el.bridgeHeight,
    ...document.querySelectorAll(".action-button"),
  ].forEach((node) => {
    node.disabled = isBusy;
  });
}

function showToast(message, isError = false) {
  el.toast.textContent = message;
  el.toast.style.background = isError ? "#8c2f20" : "";
  el.toast.classList.remove("hidden");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => {
    el.toast.classList.add("hidden");
  }, 4200);
}

function renderRules(payloadData) {
  state.rules = payloadData.rules || [];
  state.actions = payloadData.actions || [];

  const groups = new Map();
  for (const rule of state.rules) {
    const group = rule.group || "Other Rules";
    if (!groups.has(group)) {
      groups.set(group, []);
    }
    groups.get(group).push(rule);
  }

  el.ruleSelect.innerHTML = "";
  for (const [group, rules] of groups.entries()) {
    const optgroup = document.createElement("optgroup");
    optgroup.label = group;
    for (const rule of rules) {
      const option = document.createElement("option");
      option.value = rule.id;
      option.textContent = `${rule.id} · ${rule.label}`;
      option.title = rule.description;
      optgroup.appendChild(option);
    }
    el.ruleSelect.appendChild(optgroup);
  }

  el.actionList.innerHTML = "";
  for (const action of state.actions) {
    const button = document.createElement("button");
    button.className = "action-button";
    button.dataset.actionId = action.id;
    button.innerHTML = `<strong>${escapeHtml(action.label)}</strong><span>${escapeHtml(
      action.description || ""
    )}</span>`;
    button.addEventListener("click", () => runAction(action));
    el.actionList.appendChild(button);
  }
}

function renderStatus(data) {
  const stats = data.stats || {};
  el.nodeCount.textContent = numberOrDash(stats.nodes);
  el.buildingCount.textContent = numberOrDash(stats.building_elements);
  el.moduleCount.textContent = numberOrDash(stats.d2_modules);
  el.stepBadge.textContent = `Step ${data.step_index || 0}`;

  if (data.config) {
    el.configPill.textContent =
      `Neo4j: ${data.config.neo4j_uri} · Compute: ${data.config.compute_url}`;
    renderBridgeParameters(data.config.bridge_parameters);
  }

  if (data.stats_error) {
    el.statusText.textContent = data.stats_error;
  } else if (!data.initialized) {
    el.statusText.textContent = "Graph not initialized. Start with Reset From Gaphor.";
  } else {
    el.statusText.textContent = data.message || "Ready for the next rule.";
  }

  renderPreview(data.preview);
  renderHistory(data.history || []);
}

function renderBridgeParameters(params) {
  if (!params) {
    return;
  }
  if (document.activeElement !== el.bridgeLength) {
    el.bridgeLength.value = params.length ?? "";
  }
  if (document.activeElement !== el.bridgeWidth) {
    el.bridgeWidth.value = params.width ?? "";
  }
  if (document.activeElement !== el.bridgeHeight) {
    el.bridgeHeight.value = params.height ?? "";
  }
}

function renderPreview(preview) {
  if (!preview) {
    el.previewBadge.textContent = "No GLB";
    el.previewDetailText.textContent = "-";
    el.previewComponents.textContent = "-";
    el.previewRoot.textContent = "-";
    el.previewReason.textContent = "";
    el.emptyState.classList.remove("hidden");
    el.modelViewer.removeAttribute("src");
    return;
  }

  el.previewDetailText.textContent = preview.detail_level || "-";
  el.previewComponents.textContent = numberOrDash(preview.component_count);
  el.previewRoot.textContent = preview.root_id || "-";

  if (preview.connected && preview.model_url) {
    const bust = `v=${Date.now()}`;
    el.modelViewer.src = `${preview.model_url}?${bust}`;
    el.emptyState.classList.add("hidden");
    el.previewBadge.textContent = "GLB Ready";
    el.previewReason.textContent = preview.missing_definitions?.length
      ? `Missing definitions: ${preview.missing_definitions.join(", ")}`
      : "Color materials are exported with the model.";
  } else {
    el.modelViewer.removeAttribute("src");
    el.emptyState.classList.remove("hidden");
    el.previewBadge.textContent = "No GLB";
    el.previewReason.textContent = preview.reason || "No assembled geometry yet.";
  }
}

async function refreshGraph() {
  if (!window.vis) {
    showGraphEmpty("Graph viewer library is still loading.");
    return;
  }
  try {
    const data = await api("/api/graph");
    renderGraph(data);
  } catch (error) {
    el.graphSummary.textContent = error.message;
    showGraphEmpty(error.message);
  }
}

function renderGraph(data) {
  if (!data.nodes.length) {
    showGraphEmpty("No Neo4j nodes to display yet.");
  } else {
    hideGraphEmpty();
  }

  state.graphNodes = new Map(data.nodes.map((node) => [node.id, node]));
  state.graphEdges = new Map(data.relationships.map((edge) => [edge.id, edge]));

  const nodes = data.nodes.map((node) => ({
    id: node.id,
    label: String(nodeLabel(node)),
    title: nodeTitle(node),
    group: primaryLabel(node),
    shape: node.labels.includes("BuildingElement") ? "box" : "dot",
    size: node.labels.includes("Requirement") ? 22 : 18,
  }));
  const edges = data.relationships.map((edge) => ({
    id: edge.id,
    from: edge.source,
    to: edge.target,
    label: edge.type,
    arrows: "to",
    font: { align: "middle", size: 10 },
  }));

  const graphData = {
    nodes: new vis.DataSet(nodes),
    edges: new vis.DataSet(edges),
  };
  const options = {
    autoResize: true,
    interaction: {
      hover: true,
      multiselect: false,
      navigationButtons: true,
      zoomView: true,
    },
    layout: {
      improvedLayout: true,
    },
    physics: {
      stabilization: { iterations: 120 },
      barnesHut: {
        gravitationalConstant: -9000,
        springLength: 130,
        springConstant: 0.035,
      },
    },
    groups: {
      Requirement: { color: { background: "#b9efdc", border: "#13a6a0" } },
      BuildingElement: { color: { background: "#f0c3a8", border: "#c35f3f" } },
      Parameter: { color: { background: "#d9d2ff", border: "#595180" } },
    },
    nodes: {
      borderWidth: 2,
      color: { background: "#f4efe4", border: "#242720" },
      font: { face: "Space Grotesk", color: "#151713", size: 13 },
      margin: 10,
    },
    edges: {
      color: { color: "rgba(36, 39, 32, 0.42)", highlight: "#c35f3f" },
      smooth: { type: "dynamic" },
    },
  };

  if (!state.graphNetwork) {
    state.graphNetwork = new vis.Network(el.graphNetwork, graphData, options);
    state.graphNetwork.on("select", renderGraphSelection);
    state.graphNetwork.on("deselectNode", renderGraphSelection);
    state.graphNetwork.on("deselectEdge", renderGraphSelection);
  } else {
    state.graphNetwork.setData(graphData);
    state.graphNetwork.setOptions(options);
  }

  el.graphSummary.textContent = graphSummary(data);
  renderEmptyGraphDetail();
}

function renderGraphSelection() {
  const selection = state.graphNetwork.getSelection();
  if (selection.nodes.length) {
    renderGraphDetail("node", selection.nodes[0]);
    return;
  }
  if (selection.edges.length) {
    renderGraphDetail("edge", selection.edges[0]);
    return;
  }
  renderEmptyGraphDetail();
}

function showGraphEmpty(message) {
  el.graphEmpty.textContent = message;
  el.graphEmpty.classList.remove("hidden");
  renderEmptyGraphDetail();
}

function hideGraphEmpty() {
  el.graphEmpty.classList.add("hidden");
}

function renderGraphDetail(kind, id) {
  if (!id) {
    renderEmptyGraphDetail();
    return;
  }
  const item = kind === "node" ? state.graphNodes.get(id) : state.graphEdges.get(id);
  if (!item) {
    renderEmptyGraphDetail();
    return;
  }
  el.graphDetailTitle.textContent =
    kind === "node" ? nodeLabel(item) : `${item.type} relationship`;
  el.graphDetailBody.textContent = JSON.stringify(item, null, 2);
}

function renderEmptyGraphDetail() {
  el.graphDetailTitle.textContent = "Select a node or edge";
  el.graphDetailBody.textContent = "No graph item selected.";
}

function graphSummary(data) {
  const totalNodes = data.counts?.nodes ?? data.nodes.length;
  const totalEdges = data.counts?.relationships ?? data.relationships.length;
  const suffix = data.truncated ? " · showing limited graph" : "";
  return (
    `${data.nodes.length}/${totalNodes} nodes · ` +
    `${data.relationships.length}/${totalEdges} relationships${suffix}`
  );
}

function nodeLabel(node) {
  const props = node.props || {};
  return (
    props.name ||
    props.external_id ||
    props.gaphor_id ||
    props.gh_file ||
    primaryLabel(node) ||
    node.id
  );
}

function nodeTitle(node) {
  const labels = node.labels?.join(":") || "Node";
  return `${labels} ${node.id}`;
}

function primaryLabel(node) {
  const labels = node.labels || [];
  if (labels.includes("BuildingElement")) {
    return "BuildingElement";
  }
  if (labels.includes("Requirement")) {
    return "Requirement";
  }
  if (labels.includes("Parameter")) {
    return "Parameter";
  }
  return labels[0] || "Node";
}

function renderHistory(history) {
  el.historyList.innerHTML = "";
  if (!history.length) {
    const item = document.createElement("li");
    item.innerHTML = "<span>No operations yet.</span>";
    el.historyList.appendChild(item);
    return;
  }

  for (const entry of [...history].reverse()) {
    const item = document.createElement("li");
    item.innerHTML = `
      <b>${escapeHtml(String(entry.step))}</b>
      <span>
        <strong>${escapeHtml(entry.label)}</strong>
        ${escapeHtml(entry.detail || "")}
      </span>
      <time>${escapeHtml(entry.time || "")}</time>
    `;
    el.historyList.appendChild(item);
  }
}

async function runOperation(label, request) {
  try {
    setBusy(true, label);
    const data = await request();
    renderStatus(data);
    await refreshGraph();
    showToast(data.message || "Operation complete.");
  } catch (error) {
    showToast(error.message, true);
    await refreshStatus();
  } finally {
    setBusy(false);
  }
}

async function resetGraph() {
  await runOperation("Importing requirements from Gaphor...", () =>
    api("/api/reset", { method: "POST", body: payload() })
  );
}

async function refreshPreview() {
  await runOperation("Assembling and exporting GLB preview...", () =>
    api("/api/preview", { method: "POST", body: payload() })
  );
}

async function applySelectedRule() {
  const ruleId = el.ruleSelect.value;
  const times = Number.parseInt(el.repeatInput.value, 10);
  await runOperation(`Applying ${ruleId}...`, () =>
    api("/api/apply-rule", {
      method: "POST",
      body: payload({ rule_id: ruleId, times }),
    })
  );
}

async function runAction(action) {
  await runOperation(`${action.label}...`, () =>
    api("/api/action", {
      method: "POST",
      body: payload({ action_id: action.id }),
    })
  );
}

async function refreshStatus() {
  const data = await api("/api/status");
  renderStatus(data);
  refreshGraph();
}

function numberOrDash(value) {
  return Number.isFinite(value) ? String(value) : "-";
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function boot() {
  el.resetBtn.addEventListener("click", resetGraph);
  el.previewBtn.addEventListener("click", refreshPreview);
  el.refreshGraphBtn.addEventListener("click", refreshGraph);
  el.applyRuleBtn.addEventListener("click", applySelectedRule);

  try {
    const [rulesData, statusData] = await Promise.all([
      api("/api/rules"),
      api("/api/status"),
    ]);
    renderRules(rulesData);
    renderStatus(statusData);
    refreshGraph();
  } catch (error) {
    showToast(error.message, true);
  }
}

boot();
