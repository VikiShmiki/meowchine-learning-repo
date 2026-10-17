(function () {
  "use strict";
  const $ = id => document.getElementById(id);
  let token = "", generation = 0;
  const photos = new Set();
  const node = (tag, text) => { const el = document.createElement(tag); el.textContent = text; return el; };
  async function call(url, options = {}) {
    const response = await (globalThis.GoodsortI18n?.fetch || fetch)(url, {...options, headers: {...options.headers, Authorization: `Bearer ${token}`}, cache: "no-store", signal: AbortSignal.timeout(15000)});
    if (!response.ok) throw new Error(response.status === 401 ? "Reviewer key not accepted." : "Request failed. Please retry.");
    return response;
  }
  function clear() { for (const url of photos) URL.revokeObjectURL(url); photos.clear(); $("review-reports").replaceChildren(); }
  async function load() {
    const current = ++generation;
    try {
      const data = await (await call("/api/v1/review/reports")).json();
      if (current !== generation) return;
      clear(); $("review-login").hidden = true; $("review-lock").hidden = false;
      $("review-status").textContent = data.reports.length ? "" : "No reports to review.";
      for (const report of data.reports) {
        const card = node("article", ""); card.className = "card review-card";
        card.append(node("h2", report.kind === "container" ? `${report.condition} · ${report.asset_id}` : "Illegal dumping"));
        card.append(node("p", `${report.state} · ${new Date(report.created * 1000).toLocaleString(globalThis.GoodsortI18n?.locale || "en-GB")}`));
        card.append(Object.assign(node("p", report.description), { translate: false }));
        if (report.kind === "dumping") card.append(node("p", `${report.latitude.toFixed(5)}, ${report.longitude.toFixed(5)}`));
        const actions = node("div", ""); actions.className = "button-row";
        for (const [state, label] of [["approved", "Approve"], ["rejected", "Reject"], ["duplicate", "Duplicate"], ...(report.kind === "dumping" ? [["cleared", "Mark cleared"]] : [])]) {
          const button = node("button", label); button.className = "secondary"; button.disabled = report.state === state;
          button.addEventListener("click", async () => {
            button.disabled = true;
            try { await call(`/api/v1/review/reports/${report.id}`, {method: "PATCH", headers: {"Content-Type": "application/json"}, body: JSON.stringify({state})}); await load(); }
            catch (error) { $("review-status").textContent = error.message; button.disabled = false; }
          }); actions.append(button);
        }
        if (report.has_photo) {
          const button = node("button", "View private photo"); button.className = "secondary";
          button.addEventListener("click", async () => {
            button.disabled = true;
            try {
              const image = await (await call(`/api/v1/review/reports/${report.id}/photo`)).blob();
              if (!card.isConnected || !token) return;
              const url = URL.createObjectURL(image); photos.add(url);
              const img = document.createElement("img"); img.src = url; img.alt = "Submitted dumping report photo"; card.append(img);
            } catch (error) { $("review-status").textContent = error.message; button.disabled = false; }
          }); actions.append(button);
        }
        card.append(actions); $("review-reports").append(card);
      }
    } catch (error) { if (current === generation) $("review-status").textContent = error.message; }
  }
  $("review-login").addEventListener("submit", event => { event.preventDefault(); token = $("review-key").value; $("review-key").value = ""; load(); });
  $("review-lock").addEventListener("click", () => { generation++; token = ""; clear(); $("review-login").hidden = false; $("review-lock").hidden = true; $("review-status").textContent = ""; });
})();
