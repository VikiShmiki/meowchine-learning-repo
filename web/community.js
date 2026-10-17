/* Community reports are separate from the dated collection-point dataset. */
(function () {
  "use strict";
  const labels = { available: "Available", full: "Full", inaccessible: "Inaccessible", damaged: "Damaged", unknown: "Unknown" };
  const materialLabels = {glass: "Glass", plastic_bottles: "Plastic bottles", metal_cans: "Metal cans",
    paper: "Paper", mixed_municipal_waste: "General waste", electronics: "Electronics", wearable_clothes: "Clothes"};
  let statuses = {}, rechecks = {}, catalog = null, refreshPending = null, statusWrites = 0;
  const controls = new Set();
  const el = (tag, text, className) => {
    const node = document.createElement(tag);
    if (text) node.textContent = text;
    if (className) node.className = className;
    return node;
  };
  async function request(url, options = {}) {
    const response = await (globalThis.NajdiFrliI18n?.fetch || fetch)(url, { ...options, signal: options.signal || AbortSignal.timeout(15000), cache: "no-store" });
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
      if (beforeWrites === statusWrites) applyStatuses(data.statuses, data.rechecks || {});
      return data;
    }).finally(() => { refreshPending = null; });
    return refreshPending;
  }
  function applyStatuses(values, stale = rechecks) {
    const previous = statuses;
    statuses = values;
    rechecks = {...stale};
    for (const id of Object.keys(statuses)) delete rechecks[id];
    for (const control of controls) {
      if (!control.node.isConnected) controls.delete(control);
      else control.update();
    }
    const changed = [...new Set([...Object.keys(previous), ...Object.keys(statuses)])]
      .filter(id => JSON.stringify(previous[id]) !== JSON.stringify(statuses[id]));
    if (changed.length) document.dispatchEvent(new CustomEvent("container-status-change", { detail: changed }));
  }
  function containerRow(asset) {
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
    const badge = el("span", "", "condition-badge"); row.append(badge);
    const freshness = el("p", "", "condition-freshness"); row.append(freshness);
    const reportDetails = el("details", "", "condition-report-details");
    const reportHistory = el("p", "", "condition-history");
    reportDetails.append(el("summary", "Report details"), reportHistory);
    const update = () => {
      const value = statuses[id];
      const stale = rechecks[id];
      const sourceClosed = !["unknown", "open", "operational"].includes(asset.operational_status);
      const condition = sourceClosed ? asset.operational_status : value?.condition || "unknown";
      badge.textContent = !sourceClosed && !value && stale ? "Needs a fresh check" : labels[condition] || condition;
      badge.dataset.condition = condition;
      freshness.replaceChildren();
      reportHistory.replaceChildren();
      reportDetails.hidden = sourceClosed || (!value && !stale);
      if (sourceClosed) freshness.append(el("span", "Unavailable in source data"));
      else if (!value && stale) {
        freshness.append(el("span", "Report expired · condition unknown."));
        const previous = el("span", `Last observation: ${labels[stale.condition] || stale.condition}`);
        const time = el("time", new Date(stale.reported_at * 1000).toLocaleString(globalThis.NajdiFrliI18n?.locale || "en-GB"));
        time.dateTime = new Date(stale.reported_at * 1000).toISOString(); time.setAttribute("translate", "no");
        reportHistory.append(previous, document.createTextNode(" · "), time);
      } else if (!value) freshness.append(el("span", "No current condition report"));
      else {
        const source = value.source === "reviewed_community" ? "Reviewed community report"
          : value.source === "community_report" ? "Community report · not yet reviewed" : "Your report · awaiting review";
        freshness.append(el("span", source));
        const time = el("time", new Date(value.reported_at * 1000).toLocaleString(globalThis.NajdiFrliI18n?.locale || "en-GB"));
        time.dateTime = new Date(value.reported_at * 1000).toISOString();
        time.setAttribute("translate", "no"); reportHistory.append(time);
        const expiry = el("time", new Date(value.expires * 1000).toLocaleString(globalThis.NajdiFrliI18n?.locale || "en-GB"));
        expiry.dateTime = new Date(value.expires * 1000).toISOString(); expiry.setAttribute("translate", "no");
        reportHistory.append(document.createElement("br"), el("span", "Report valid until"), document.createTextNode(" · "), expiry,
          document.createElement("br"), el("span", "Expiry does not mean the container was emptied."));
      }
      if (saved && savedExpires <= Date.now() / 1000) {
        saved = false; select.disabled = false; select.value = ""; submit.disabled = true;
        submit.textContent = "Report condition";
        message.textContent = "You can send a fresh report.";
      }
    };
    const form = el("form", "", "condition-form");
    const select = el("select"); select.setAttribute("aria-label", `Condition of ${name}`);
    const placeholder = el("option", "Choose a condition"); placeholder.value = ""; select.append(placeholder);
    for (const [key, name] of Object.entries(labels)) if (key !== "unknown") {
      const option = el("option", name); option.value = key; select.append(option);
    }
    const submit = el("button", "Report condition", "secondary");
    submit.type = "submit"; submit.disabled = true;
    const message = el("p"); message.setAttribute("role", "status");
    let saving = false, saved = false, savedExpires = Infinity;
    select.addEventListener("change", () => { submit.disabled = !select.value || saving || saved; });
    form.append(select, submit); row.append(form, message,
      el("p", "Available reports need review.", "condition-freshness"), reportDetails);
    form.addEventListener("submit", async event => {
      event.preventDefault();
      if (!select.value || saving || saved) return;
      const condition = select.value;
      saving = true; submit.disabled = true; select.disabled = true;
      form.setAttribute("aria-busy", "true"); message.textContent = "Sending report…";
      try {
        const report = await submitObservation(id, condition);
        saved = true;
        savedExpires = report.expires;
        submit.textContent = "Report sent";
        message.textContent = condition === "full" ? "Reported full · excluded from everyone's routes for up to 12 hours."
          : "Saved · awaiting review";
      } catch (error) {
        message.textContent = error.status === 429 ? error.message
          : "Could not send your report. Your choice is kept. Please retry.";
      } finally {
        saving = false; form.setAttribute("aria-busy", "false");
        submit.disabled = saved || !select.value; select.disabled = saved;
      }
    });
    update(); controls.add({node: row, update});
    return row;
  }
  async function submitObservation(id, condition) {
    const report = await request("/api/v1/container-reports", { method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({asset_id: id, condition}) });
    statusWrites += 1;
    // Keep the successful write even when an older read or a failed refresh follows it.
    if (condition !== "available" && report.created >= (statuses[id]?.reported_at || 0)) {
      applyStatuses({...statuses, [id]: {condition, reported_at: report.created, expires: report.expires,
        source: condition === "full" ? "community_report" : "your_report"}});
    }
    const older = refreshPending;
    Promise.resolve(older).catch(() => {}).then(() => refresh()).catch(() => {});
    return report;
  }
  function reportStop(ids, { problem = false, number, appearance, opener } = {}) {
    if (document.getElementById("stop-report-dialog")) return;
    const dialog = el("dialog", "", "stop-report-dialog"); dialog.id = "stop-report-dialog";
    dialog.setAttribute("aria-labelledby", "stop-report-title");
    const heading = el("h2", problem ? "Report a problem" : "Still space here?"); heading.id = "stop-report-title";
    const badge = el("span", String(number), "stop-card-number"); badge.setAttribute("aria-hidden", "true");
    dialog.style.setProperty("--stop-fill", appearance.background);
    dialog.style.setProperty("--stop-ink", appearance.color);
    const header = el("div", "", "stop-report-heading"); header.append(badge, heading);
    const body = el("div");
    const message = el("p"); message.setAttribute("role", "status");
    const close = el("button", "Skip", "secondary"); close.type = "button";
    close.addEventListener("click", () => dialog.close());
    dialog.addEventListener("close", () => {
      dialog.remove();
      if (opener?.isConnected && !opener.disabled) opener.focus({preventScroll: true});
      else document.getElementById("checkin-heading")?.focus({preventScroll: true});
    });
    dialog.append(header, body, message, close); document.body.append(dialog); dialog.showModal();
    let position = 0, saving = false;
    const unique = [...new Set(ids)];
    async function load() {
      body.replaceChildren(el("p", "Loading containers…"));
      try {
        const index = await assets();
        if (!dialog.isConnected) return;
        // Never silently turn an incomplete catalog into a report for another asset.
        if (!unique.length || unique.some(id => !index.has(id))) throw new Error("Missing container");
        function render() {
          if (!dialog.isConnected) return;
          if (position === unique.length) { dialog.close(); return; }
          const asset = index.get(unique[position]);
          body.replaceChildren(); message.textContent = "";
          const row = el("div", "", "stop-report-container"); row.dataset.assetId = asset.id;
          const materials = el("p", "", "stop-report-materials");
          asset.source_materials.forEach((material, i) => {
            if (i) materials.append(document.createTextNode(" / "));
            materials.append(el("span", materialLabels[material] || material.replaceAll("_", " ")));
          });
          row.append(materials);
          if (unique.length > 1) {
            const count = el("p", `${position + 1} / ${unique.length}`, "stop-report-progress");
            count.setAttribute("translate", "no");
            row.append(count, el("p", asset.name), el("p", asset.address || ""));
          }
          const choices = el("div", "", "stop-report-choices");
          const options = problem ? [["full", "Full"], ["damaged", "Damaged"], ["inaccessible", "Blocked"]]
            : [["available", "Still space"], ["full", "Full"]];
          for (const [condition, label] of options) {
            const button = el("button", label); button.type = "button"; button.dataset.condition = condition;
            button.addEventListener("click", async () => {
              if (saving) return;
              saving = true; message.textContent = "Sending report…";
              for (const choice of choices.children) choice.disabled = true;
              try {
                await submitObservation(asset.id, condition);
                position += 1; render();
              } catch (error) {
                if (!dialog.isConnected) return;
                message.textContent = error.status === 429 ? error.message : "Could not send. Try again.";
                for (const choice of choices.children) choice.disabled = false;
                button.focus();
              } finally { saving = false; }
            });
            choices.append(button);
          }
          row.append(choices); body.append(row);
          close.textContent = "Skip";
          choices.firstElementChild.focus();
        }
        render();
      } catch {
        if (!dialog.isConnected) return;
        body.replaceChildren(el("p", "Could not load containers."));
        const retry = el("button", "Retry", "secondary"); retry.type = "button";
        retry.addEventListener("click", load); body.append(retry); retry.focus();
      }
    }
    load();
  }
  function containerControl(ids) {
    const root = el("details", "", "container-condition");
    const summary = el("summary", "Container conditions ");
    const overall = el("span", "", "condition-badge"); summary.append(overall); root.append(summary);
    const updateSummary = () => {
      const values = ids.map(id => statuses[id]?.condition || "unknown");
      const condition = ["damaged", "inaccessible", "full", "unknown", "available"].find(value => values.includes(value)) || "unknown";
      overall.textContent = condition === "unknown" && ids.some(id => rechecks[id]) ? "Needs a fresh check" : labels[condition]; overall.dataset.condition = condition;
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
  globalThis.CommunityUI = { containerControl, reportStop, refresh, request, el };
  document.addEventListener("languagechange", () => {
    for (const control of controls) if (control.node.isConnected) control.update();
  });
  // No background provider calls: this only checks the local report database.
  setInterval(() => { if (!document.hidden) refresh().catch(() => {}); }, 30000);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) refresh().catch(() => {}); });
  refresh().catch(() => {});
})();
