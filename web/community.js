/* Community reports are separate from the dated collection-point dataset. */
(function () {
  "use strict";
  const labels = { available: "Available", full: "Full", inaccessible: "Inaccessible", damaged: "Damaged", unknown: "Unknown" };
  const materialLabels = {glass: "Glass", plastic_bottles: "Plastic bottles", metal_cans: "Metal cans",
    paper: "Paper", mixed_municipal_waste: "General waste", electronics: "Electronics", wearable_clothes: "Clothes"};
  let statuses = {}, catalog = null, refreshPending = null, statusWrites = 0;
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
    if (!response.ok) {
      const error = new Error(typeof data.detail === "string" ? data.detail : data.detail?.message || "Could not save. Please retry.");
      error.status = response.status; throw error;
    }
    return data;
  }
  async function assets() {
    if (!catalog) catalog = request("/api/v1/sites?scope=citizen").then(data =>
      new Map(data.sites.flatMap(site => site.assets.map(asset => [asset.id, asset])))).catch(error => { catalog = null; throw error; });
    return catalog;
  }
  async function refresh() {
    if (refreshPending) return refreshPending;
    const beforeWrites = statusWrites;
    refreshPending = request("/api/v1/container-statuses").then(data => {
      // A read started before a successful report must not erase that local update.
      if (beforeWrites === statusWrites) applyStatuses(data.statuses);
      return data;
    }).finally(() => { refreshPending = null; });
    return refreshPending;
  }
  function applyStatuses(values) {
    const previous = statuses;
    statuses = values;
    for (const control of controls) {
      if (!control.node.isConnected) controls.delete(control);
      else control.update();
    }
    const changed = [...new Set([...Object.keys(previous), ...Object.keys(statuses)])]
      .filter(id => JSON.stringify(previous[id]) !== JSON.stringify(statuses[id]));
    if (changed.length) document.dispatchEvent(new CustomEvent("container-status-change", { detail: changed }));
  }
  function containerRow(asset, checkIn = false) {
    const id = asset.id;
    const name = asset.name.endsWith(id) ? `Container in ${asset.municipality_name}` : asset.name;
    const row = el("div", "", "condition-row"); row.dataset.assetId = id;
    row.append(el("strong", name));
    const materials = el("span", "", "condition-material");
    asset.source_materials.forEach((material, index) => {
      if (index) materials.append(document.createTextNode(" / "));
      materials.append(el("span", materialLabels[material] || material.replaceAll("_", " ")));
    });
    row.append(materials);
    if (checkIn) row.append(el("p", asset.address || `Map location: ${asset.latitude.toFixed(5)}, ${asset.longitude.toFixed(5)}`, "condition-location"));
    const badge = el("span", "", "condition-badge"); row.append(badge);
    const freshness = el("p", "", "condition-freshness"); row.append(freshness);
    const update = () => {
      const value = statuses[id];
      const sourceClosed = !["unknown", "open", "operational"].includes(asset.operational_status);
      const condition = sourceClosed ? asset.operational_status : value?.condition || "unknown";
      badge.textContent = labels[condition] || condition;
      badge.dataset.condition = condition;
      freshness.replaceChildren();
      if (sourceClosed) freshness.append(el("span", "Unavailable in source data"));
      else if (!value) freshness.append(el("span", "No current condition report"));
      else {
        const source = value.source === "reviewed_community" ? "Reviewed community report"
          : value.source === "community_report" ? "Community report · not yet reviewed" : "Your report · awaiting review";
        freshness.append(el("span", source), document.createTextNode(" · "));
        const time = el("time", new Date(value.reported_at * 1000).toLocaleString(globalThis.GoodsortI18n?.locale || "en-GB"));
        time.dateTime = new Date(value.reported_at * 1000).toISOString();
        time.setAttribute("translate", "no"); freshness.append(time);
      }
    };
    update(); controls.add({node: row, update});
    const form = el("form", "", "condition-form");
    const select = el("select"); select.setAttribute("aria-label", `Condition of ${name}`);
    const placeholder = el("option", checkIn ? "Didn't check / skip" : "Choose a condition"); placeholder.value = ""; select.append(placeholder);
    for (const [key, name] of Object.entries(labels)) if (key !== "unknown") {
      const option = el("option", name); option.value = key; select.append(option);
    }
    const submit = el("button", checkIn ? "Send report" : "Report condition", "secondary");
    submit.type = "submit"; submit.disabled = true;
    const message = el("p"); message.setAttribute("role", "status");
    let saving = false, saved = false;
    select.addEventListener("change", () => { submit.disabled = !select.value || saving || saved; });
    form.append(select, submit); row.append(form, message);
    form.addEventListener("submit", async event => {
      event.preventDefault();
      if (!select.value || saving || saved) return;
      const condition = select.value;
      saving = true; submit.disabled = true; select.disabled = true;
      form.setAttribute("aria-busy", "true"); message.textContent = "Sending report…";
      try {
        const report = await request("/api/v1/container-reports", { method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({asset_id: id, condition}) });
        saved = true;
        statusWrites += 1;
        // Reflect the successful write even if the follow-up refresh is offline.
        if (condition !== "available" && report.created >= (statuses[id]?.reported_at || 0)) {
          applyStatuses({...statuses, [id]: {condition, reported_at: report.created, expires: report.expires,
            source: condition === "full" ? "community_report" : "your_report"}});
        }
        submit.textContent = "Report sent";
        message.textContent = condition === "full" ? "Reported full · excluded from everyone's routes for up to 12 hours."
          : "Saved · awaiting review";
        // Await any older read before requesting fresh state after this write.
        if (refreshPending) await refreshPending.catch(() => {});
        await refresh().catch(() => {});
      } catch (error) {
        message.textContent = error.status === 429 ? error.message
          : "Could not send your report. Your choice is kept. Please retry.";
      } finally {
        saving = false; form.setAttribute("aria-busy", "false");
        submit.disabled = saved || !select.value; select.disabled = saved;
      }
    });
    return row;
  }
  function checkIn(ids) {
    const root = el("div", "", "checkin-containers");
    async function load() {
      root.replaceChildren(el("p", "Loading containers…"));
      try {
        const index = await assets();
        if (!root.isConnected) return;
        root.replaceChildren();
        for (const id of new Set(ids)) {
          const asset = index.get(id);
          if (asset) root.append(containerRow(asset, true));
        }
        if (!root.children.length) root.append(el("p", "Container details are unavailable. You can skip this check-in."));
      } catch {
        root.replaceChildren(el("p", "Could not load containers. Retry or skip this check-in."));
        const retry = el("button", "Retry", "secondary"); retry.type = "button";
        retry.addEventListener("click", load); root.append(retry);
      }
    }
    // Allow the caller to attach the panel before an already-cached catalog resolves.
    queueMicrotask(load);
    return root;
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
          body.append(containerRow(asset));
        }
        loaded = true;
      } catch (error) { body.replaceChildren(el("p", error.message)); }
    });
    return root;
  }
  globalThis.CommunityUI = { containerControl, checkIn, refresh, request, el };
  document.addEventListener("languagechange", () => {
    for (const control of controls) if (control.node.isConnected) control.update();
  });
  // No background provider calls: this only checks the local report database.
  setInterval(() => { if (!document.hidden) refresh().catch(() => {}); }, 30000);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) refresh().catch(() => {}); });
  refresh().catch(() => {});
})();
