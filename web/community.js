/* Community reports are separate from the dated collection-point dataset. */
(function () {
  "use strict";
  const labels = { available: "Available", full: "Full", inaccessible: "Inaccessible", damaged: "Damaged", unknown: "Unknown" };
  let statuses = {}, catalog = null, refreshPending = null;
  const controls = new Set();
  const el = (tag, text, className) => {
    const node = document.createElement(tag);
    if (text) node.textContent = text;
    if (className) node.className = className;
    return node;
  };
  async function request(url, options = {}) {
    const response = await (globalThis.GoodsortI18n?.fetch || fetch)(url, { ...options, signal: options.signal || AbortSignal.timeout(15000), cache: "no-store" });
    const data = response.status === 204 ? {} : await response.json();
    if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : data.detail?.message || "Could not save. Please retry.");
    return data;
  }
  async function assets() {
    if (!catalog) catalog = request("/api/v1/sites?scope=citizen").then(data =>
      new Map(data.sites.flatMap(site => site.assets.map(asset => [asset.id, asset])))).catch(error => { catalog = null; throw error; });
    return catalog;
  }
  async function refresh() {
    if (refreshPending) return refreshPending;
    refreshPending = request("/api/v1/container-statuses").then(data => {
      const previous = statuses;
      statuses = data.statuses;
      for (const control of controls) {
        if (!control.node.isConnected) controls.delete(control);
        else control.update();
      }
      const changed = [...new Set([...Object.keys(previous), ...Object.keys(statuses)])]
        .filter(id => JSON.stringify(previous[id]) !== JSON.stringify(statuses[id]));
      if (changed.length) document.dispatchEvent(new CustomEvent("container-status-change", { detail: changed }));
      return data;
    }).finally(() => { refreshPending = null; });
    return refreshPending;
  }
  function containerControl(ids) {
    const root = el("details", "", "container-condition");
    const summary = el("summary", "Container conditions ");
    const overall = el("span", "", "condition-badge"); summary.append(overall); root.append(summary);
    const updateSummary = () => {
      const values = ids.map(id => statuses[id]?.condition || "unknown");
      const condition = ["damaged", "inaccessible", "full", "unknown", "available"].find(value => values.includes(value)) || "unknown";
      overall.textContent = labels[condition]; overall.dataset.condition = condition;
    };
    updateSummary(); controls.add({node: root, update: updateSummary});
    const body = el("div"); root.append(body);
    let loaded = false;
    root.addEventListener("toggle", async () => {
      if (!root.open || loaded) return;
      body.replaceChildren(el("p", "Loading…"));
      try {
        const [index] = await Promise.all([assets(), refresh()]);
        if (!root.isConnected) return;
        body.replaceChildren();
        for (const id of ids) {
          const asset = index.get(id);
          if (!asset) continue;
          const row = el("div", "", "condition-row");
          row.append(el("strong", asset.name));
          row.append(el("span", asset.source_materials.join(" / ").replaceAll("_", " "), "condition-material"));
          const badge = el("span", "", "condition-badge"); row.append(badge);
          const update = () => {
            const value = statuses[id];
            const sourceClosed = !["unknown", "open", "operational"].includes(asset.operational_status);
            const condition = sourceClosed ? asset.operational_status : value?.condition || "unknown";
            badge.textContent = labels[condition] || condition;
            badge.dataset.condition = condition;
            badge.title = sourceClosed ? "Unavailable in source data" : value
              ? `${value.source === "your_report" ? "Your report · awaiting review" : "Reviewed community report"} · ${new Date(value.reported_at * 1000).toLocaleString(globalThis.GoodsortI18n?.locale || "en-GB")}`
              : "No current condition report";
          };
          update(); controls.add({ node: row, update });
          const form = el("form", "", "condition-form");
          const select = el("select"); select.setAttribute("aria-label", `Condition of ${asset.name} (${id})`);
          for (const [key, name] of Object.entries(labels)) if (key !== "unknown") {
            const option = el("option", name); option.value = key; select.append(option);
          }
          select.value = "full";
          const submit = el("button", "Report condition", "secondary"); submit.type = "submit";
          const message = el("p"); message.setAttribute("role", "status");
          form.append(select, submit); row.append(form, message);
          form.addEventListener("submit", async event => {
            event.preventDefault(); submit.disabled = true;
            try {
              await request("/api/v1/container-reports", { method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({asset_id: id, condition: select.value}) });
              await refresh();
              message.textContent = "Saved · awaiting review";
            } catch (error) { message.textContent = error.message; }
            finally { submit.disabled = false; }
          });
          body.append(row);
        }
        loaded = true;
      } catch (error) { body.replaceChildren(el("p", error.message)); }
    });
    return root;
  }
  globalThis.CommunityUI = { containerControl, refresh, request, el };
  // No background provider calls: this only checks the local report database.
  setInterval(() => { if (!document.hidden) refresh().catch(() => {}); }, 30000);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) refresh().catch(() => {}); });
  refresh().catch(() => {});
})();
