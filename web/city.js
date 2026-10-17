/* Prepared population coverage; no personal coordinates or live routing requests. */
(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  let report = null;
  const population = (value) => Math.round(value).toLocaleString(globalThis.GoodsortI18n?.locale || "en-GB");
  const percent = (value) => value === null ? "Unavailable" : `${value.toFixed(1)}%`;
  function node(tag, text) {
    const element = document.createElement(tag);
    element.textContent = text;
    return element;
  }
  function renderChart(selected, available) {
    const chart = $("municipality-chart");
    chart.replaceChildren();
    if (!available) {
      chart.append(node("p", "Coverage unavailable for this material."));
      return;
    }
    const floor = report.equity_floor_percent;
    chart.style.setProperty("--coverage-floor", `${floor}%`);
    const key = node("div", ""); key.className = "chart-key";
    for (const [label, className] of [["Meets floor", "meets"], ["Below floor", "below"]]) {
      const entry = node("span", label); entry.className = className; key.append(entry);
    }
    chart.append(key);
    const axis = node("div", ""); axis.className = "chart-axis"; axis.setAttribute("aria-hidden", "true");
    axis.append(node("span", "0%"), node("span", "100%"));
    const target = node("span", `${floor}% floor`); target.className = "chart-floor-label";
    axis.append(target); chart.append(axis);
    const list = node("ol", ""); list.className = "chart-rows";
    const sorted = [...selected.municipalities].sort((a, b) =>
      (b.coverage_percent ?? -1) - (a.coverage_percent ?? -1) || a.name.localeCompare(b.name));
    for (const municipality of sorted) {
      const value = municipality.population === 0 ? null : municipality.coverage_percent;
      const row = node("li", ""); row.className = "chart-row";
      const label = node("div", ""); label.className = "chart-row-label";
      label.append(node("span", municipality.name), node("strong", municipality.population === 0
        ? "No modeled population" : percent(value)));
      row.append(label);
      if (value !== null) {
        const below = value < floor;
        row.classList.add(below ? "below" : "meets");
        row.setAttribute("aria-label", `${municipality.name}: ${percent(value)}, ${below
          ? `${(floor - value).toFixed(1)} percentage points below the project floor` : "meets the project floor"}`);
        const track = node("div", ""); track.className = "chart-track";
        track.setAttribute("aria-hidden", "true");
        const bar = node("span", ""); bar.className = "chart-bar";
        bar.style.width = `${value}%`;
        track.append(bar); row.append(track);
      }
      list.append(row);
    }
    chart.append(list);
  }
  function render() {
    if (!report) return;
    const selected = report.materials.find((row) => row.material === $("coverage-material").value);
    const available = selected.status === "approximation";
    $("coverage-scope").textContent = available
      ? "Counts sites with an asset accepting every listed reviewed type: " + selected.required_item_kinds.map((kind) => kind.replaceAll("_", " ")).join(", ") + "."
      : selected.reason;
    const summary = $("coverage-summary");
    summary.replaceChildren();
    for (const [title, value] of [
      ["Population coverage", percent(selected.city.coverage_percent)],
      ["Residents covered", available ? population(selected.city.covered_population) : "Unavailable"],
      ["Compatible sites", String(selected.compatible_site_count)],
    ]) {
      const card = node("div", ""); card.className = "card";
      card.classList.toggle("unavailable", value === "Unavailable");
      card.append(node("p", title), node("strong", value)); summary.append(card);
    }
    $("coverage-population").textContent = available
      ? `Estimated from ${population(selected.city.population)} modeled residents. ${selected.connected_site_count} compatible sites have a candidate street connection.`
      : "";
    $("coverage-availability").textContent = available ? ""
      : "Coverage is unavailable, not zero. No general-waste acceptance is inferred from a container label.";
    $("equity-note").textContent = "Population within a 10-minute walk";
    renderChart(selected, available);
  }
  document.addEventListener("languagechange", render);
  async function load() {
    $("retry-coverage").hidden = true; $("city-results").hidden = true;
    $("city-status").textContent = "Loading population coverage...";
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 12000);
    try {
      const response = await fetch("/api/v1/coverage", { signal: controller.signal, cache: "no-store" });
      if (!response.ok) throw new Error("Unavailable");
      const body = await response.json();
      if (body.schema_version !== 1 || body.method !== "population_weighted_walking_network_approximation"
          || body.threshold_seconds !== 600 || !Array.isArray(body.materials)
          || ["glass", "plastic_metal", "paper_tetrapak", "general"].some((key) => body.materials.filter((row) => row.material === key).length !== 1)) throw new Error("Invalid report");
      report = body;
      $("coverage-sources").textContent = `${report.population_product}, ${report.population_year}. Network: ${report.network_timestamp}. Site snapshot: ${report.source_as_of}. Walk speed: ${report.walking_speed_kmh} km/h; both access gaps included in the 10-minute budget. Population NoData area: ${report.nodata_area_km2.toFixed(2)} km2 (unknown, not zero).`;
      $("coverage-limits").replaceChildren(...report.limitations.map((text) => node("li", text)));
      $("coverage-attribution").textContent = report.attribution.join(" | ");
      render(); $("city-results").hidden = false;
      $("city-status").textContent = "";
    } catch {
      report = null;
      $("city-status").textContent = "Coverage is unavailable. The prepared population/network report could not be loaded. No substitute metric is shown.";
      $("retry-coverage").hidden = false;
    } finally { clearTimeout(timer); }
  }
  $("coverage-material").addEventListener("change", render);
  $("retry-coverage").addEventListener("click", load);
  load();
})();
