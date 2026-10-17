/* Prepared City scenarios. Changes cancel stale requests and clear old recommendations. */
(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  let active = null;
  let currentPlan = null, currentIndex = 0, map = null, marker = null, tiles = null;
  let mapLoading = null, tileErrors = false;
  const materialNames = { glass: "glass", plastic_metal: "plastic bottles and cans", paper_tetrapak: "paper and cartons" };
  const materialLabels = { glass: "Glass", plastic_metal: "Plastic & cans", paper_tetrapak: "Paper & cartons" };
  const materialPaths = {
    glass: "M10 3h4v5l3 5v7a1 1 0 0 1-1 1H8a1 1 0 0 1-1-1v-7l3-5V3ZM10 6h4M7 14h10",
    plastic_metal: "M5 3h4v4l2 3v10H3V10l2-3V3ZM3 13h8M3 17h8M15 8h6v12h-6zM15 11h6M17 8V6h2",
    paper_tetrapak: "M4 7h10v14H4zM7 3h13v14h-3M7 11h4M7 15h4",
  };
  const percent = (value) => Number.isFinite(value) ? `${value.toFixed(1)}%` : "Unavailable";
  function node(tag, text) {
    const element = document.createElement(tag); element.textContent = text; return element;
  }
  function icon(path, viewBox = "0 0 24 24") {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", viewBox); svg.setAttribute("aria-hidden", "true");
    const shape = document.createElementNS(svg.namespaceURI, "path");
    shape.setAttribute("d", path); svg.append(shape); return svg;
  }
  function collectionBin(material) {
    const bin = node("span", ""); bin.className = `collection-bin ${material ? "new-bin" : "existing-bin"}`;
    bin.append(icon("M9 11h30l-3 43H12L9 11ZM7 7h34v4H7zM19 3h10v4M15 54v3M33 54v3", "0 0 48 60"));
    if (material) { const symbol = icon(materialPaths[material]); symbol.classList.add("bin-symbol"); bin.append(symbol); }
    return bin;
  }
  function renderChange(material) {
    const before = node("div", ""), after = node("div", "");
    before.className = after.className = "collection-stage";
    const existing = node("div", ""); existing.className = "collection-bins"; existing.append(collectionBin());
    before.append(node("span", "Now"), existing, node("strong", "General waste"));
    const proposed = node("div", ""); proposed.className = "collection-bins";
    const plus = node("span", "+"); plus.className = "collection-plus"; plus.setAttribute("aria-hidden", "true");
    proposed.append(collectionBin(), plus, collectionBin(material));
    after.append(node("span", "Proposed"), proposed, node("strong", `Add ${materialLabels[material].toLowerCase()}`));
    const arrow = icon("M4 12h16m-6-6 6 6-6 6"); arrow.classList.add("collection-arrow");
    $("upgrade-change").replaceChildren(before, arrow, after);
    $("upgrade-change").setAttribute("aria-label", `Keep general-waste collection and add ${materialNames[material]} collection`);
  }
  function comparison(before, after, label) {
    const chart = node("div", ""); chart.className = "access-comparison";
    chart.setAttribute("role", "img");
    chart.setAttribute("aria-label", `${label}: before ${percent(before)}, with all proposed upgrades ${percent(after)} walking access`);
    for (const [name, value, variant] of [["Now", before, "before"], ["With upgrades", after, "after"]]) {
      const row = node("div", ""); row.className = "access-row"; row.setAttribute("aria-hidden", "true");
      const track = node("span", ""); track.className = "access-track";
      if (Number.isFinite(value)) {
        const bar = node("span", ""); bar.className = `access-fill ${variant}`;
        bar.style.width = `${Math.max(0, Math.min(100, value))}%`; track.append(bar);
      } else { track.classList.add("access-unknown"); track.textContent = "Unavailable"; }
      row.append(node("span", name), track); chart.append(row);
    }
    return chart;
  }
  function reset() {
    if (active) active.abort();
    active = null;
    currentPlan = null; currentIndex = 0;
    marker?.remove(); marker = null;
    $("upgrade-carousel").hidden = true;
    $("upgrade-prev").disabled = $("upgrade-next").disabled = true;
    $("upgrade-position").textContent = "";
    $("upgrade-results").hidden = true;
    $("upgrade-solver").textContent = "";
    $("upgrade-limits").replaceChildren();
    const unsupported = $("coverage-material").value === "general";
    $("recommend-upgrades").disabled = unsupported;
    $("upgrade-count").disabled = unsupported;
    $("upgrade-status").textContent = unsupported
      ? "General-waste upgrades cannot be evaluated without reviewed acceptance evidence."
      : "";
  }
  function reasonFor(site) {
    const municipality = currentPlan.municipalities.find((row) => row.name === site.municipality);
    return municipality?.before !== null && Number.isFinite(municipality?.before)
      && municipality.before < currentPlan.equity_floor_percent
      ? "An existing waste site in a municipality with limited walking access to this collection."
      : "An existing waste site selected for the citywide walking-access plan.";
  }
  function drawSelectedSite() {
    if (!map || !currentPlan?.sites.length || $("upgrade-carousel").hidden) return;
    const site = currentPlan.sites[currentIndex];
    marker?.remove();
    const star = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    star.setAttribute("viewBox", "0 0 48 48"); star.setAttribute("aria-hidden", "true");
    const shape = document.createElementNS("http://www.w3.org/2000/svg", "path");
    shape.setAttribute("d", "m24 8 4.5 10.5L40 20l-8.5 7.5L34 39l-10-6-10 6 2.5-11.5L8 20l11.5-1.5Z");
    star.append(shape);
    const title = `Suggested upgrade ${currentIndex + 1}: ${site.name}, ${site.municipality}`;
    marker = L.marker([site.lat, site.lon], {
      icon: L.divIcon({ className: "upgrade-star", html: star, iconSize: [48, 48], iconAnchor: [24, 24] }),
      title,
    }).addTo(map).bindTooltip(node("span", title));
    marker.getElement().setAttribute("aria-label", title);
    const popup = node("div", "");
    popup.append(node("strong", `Add ${materialNames[currentPlan.material]} collection`), node("p", title), node("p", reasonFor(site)));
    marker.bindPopup(popup);
    map.invalidateSize({ pan: false });
    map.setView([site.lat, site.lon], 17, { animate: false });
  }
  async function ensureMap() {
    if (map) { drawSelectedSite(); return; }
    if (mapLoading) return mapLoading;
    $("upgrade-map-status").textContent = "Loading map…";
    $("retry-upgrade-map").hidden = true;
    mapLoading = (async () => {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 10000);
      try {
        if (!globalThis.L) throw new Error("Map library unavailable");
        const response = await fetch("/static/map-config.json", { signal: controller.signal });
        if (!response.ok) throw new Error("Map configuration unavailable");
        const config = await response.json();
        map = L.map("upgrade-map", { scrollWheelZoom: false, zoomControl: false }).setView(config.center, 17);
        L.control.zoom({ position: "bottomright" }).addTo(map);
        tileErrors = false;
        tiles = L.tileLayer(config.tile_url, { maxZoom: config.max_zoom, attribution: config.attribution }).addTo(map);
        tiles.on("tileerror", () => {
          tileErrors = true;
          $("upgrade-map-status").textContent = "Map tiles unavailable. Use the location link or retry.";
          $("retry-upgrade-map").hidden = false;
        });
        tiles.on("load", () => {
          if (!tileErrors) { $("upgrade-map-status").textContent = ""; $("retry-upgrade-map").hidden = true; }
        });
        new ResizeObserver(() => map?.invalidateSize({ pan: false })).observe($("upgrade-map"));
        $("upgrade-map-status").textContent = "";
        drawSelectedSite(); // Read the latest selection, never a stale slide captured before loading.
      } catch {
        map?.remove(); map = null; tiles = null;
        $("upgrade-map-status").textContent = "Map unavailable. Use the location link or retry.";
        $("retry-upgrade-map").hidden = false;
      } finally { clearTimeout(timer); }
    })();
    await mapLoading;
    mapLoading = null;
  }
  function renderSlide() {
    if (!currentPlan?.sites.length) return;
    const site = currentPlan.sites[currentIndex];
    $("upgrade-carousel").hidden = false;
    $("upgrade-carousel").dataset.siteId = site.id;
    $("upgrade-position").textContent = `${currentIndex + 1} of ${currentPlan.sites.length}`;
    $("upgrade-prev").disabled = currentIndex === 0;
    $("upgrade-next").disabled = currentIndex === currentPlan.sites.length - 1;
    $("upgrade-results").dataset.material = currentPlan.material;
    $("upgrade-action-title").textContent = `Add ${materialNames[currentPlan.material]} collection`;
    $("upgrade-material-icon").replaceChildren(icon(materialPaths[currentPlan.material]));
    $("upgrade-site-title").textContent = site.municipality;
    renderChange(currentPlan.material);
    $("upgrade-reason").textContent = reasonFor(site);
    $("upgrade-location").href = `https://www.openstreetmap.org/?mlat=${site.lat}&mlon=${site.lon}#map=18/${site.lat}/${site.lon}`;
    $("upgrade-location").setAttribute("aria-label", `View ${site.name} on OpenStreetMap`);
    ensureMap();
  }
  function moveSlide(direction) {
    if (!currentPlan?.sites.length) return;
    const next = Math.max(0, Math.min(currentPlan.sites.length - 1, currentIndex + direction));
    if (next === currentIndex) return;
    currentIndex = next; renderSlide();
    if (document.activeElement === $("upgrade-next") && $("upgrade-next").disabled) $("upgrade-prev").focus({ preventScroll: true });
    if (document.activeElement === $("upgrade-prev") && $("upgrade-prev").disabled) $("upgrade-next").focus({ preventScroll: true });
  }
  $("upgrade-prev").addEventListener("click", () => moveSlide(-1));
  $("upgrade-next").addEventListener("click", () => moveSlide(1));
  $("upgrade-map-shell").addEventListener("keydown", (event) => {
    if (event.target !== $("upgrade-map-shell") && !event.target.closest(".upgrade-arrow")) return;
    if (!["ArrowLeft", "ArrowRight"].includes(event.key)) return;
    event.preventDefault(); moveSlide(event.key === "ArrowLeft" ? -1 : 1);
  });
  $("retry-upgrade-map").addEventListener("click", () => {
    if (!map) { ensureMap(); return; }
    tileErrors = false; $("retry-upgrade-map").hidden = true;
    $("upgrade-map-status").textContent = "Loading map…";
    tiles.redraw();
  });
  function render(body) {
    const plan = body.plan;
    if (!Array.isArray(plan.sites) || plan.sites.some((site) =>
      !Number.isFinite(site.lat) || Math.abs(site.lat) > 90 || !Number.isFinite(site.lon) || Math.abs(site.lon) > 180)) throw new Error("Invalid site coordinates");
    currentPlan = plan; currentIndex = 0;
    $("upgrade-count").max = body.max_upgrades;
    $("upgrade-results").dataset.material = plan.material;
    $("upgrade-summary").replaceChildren(comparison(plan.before_percent, plan.after_percent, "Citywide"));
    const evidence = {
      met: "All municipalities with modeled population meet the floor.",
      proven_infeasible: "The municipal floor is proven infeasible for this budget under this model.",
      not_found: "The search did not find a plan meeting every municipal floor. Infeasibility is not proven.",
    };
    $("upgrade-solver").textContent = `${plan.solver === "optimal" ? "Exact search: optimal under this model." : "Approximate search: not a proven global optimum."} ${evidence[plan.floor_status]} Floor: ${plan.equity_floor_percent}%.`;
    $("upgrade-status").textContent = plan.sites.length
      ? ""
      : "No upgrades selected for this budget.";
    $("upgrade-municipalities").replaceChildren();
    for (const m of plan.municipalities) {
      const row = node("div", ""); row.className = "municipal-comparison";
      row.append(node("h4", m.name), comparison(m.before, m.after, m.name));
      $("upgrade-municipalities").append(row);
    }
    $("upgrade-limits").replaceChildren(...body.limitations.map((text) => node("li", text)));
    $("upgrade-results").hidden = false;
    renderSlide();
  }
  $("upgrade-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!$("upgrade-form").reportValidity()) return;
    reset();
    const material = $("coverage-material").value;
    if (material === "general") return;
    const n = Number($("upgrade-count").value);
    const controller = new AbortController(); active = controller;
    $("recommend-upgrades").disabled = true;
    $("upgrade-status").textContent = "Loading upgrade recommendations...";
    const timer = setTimeout(() => controller.abort(), 12000);
    try {
      const response = await fetch(`/api/v1/upgrades?material=${encodeURIComponent(material)}&n=${n}`, {signal: controller.signal, cache: "no-store"});
      if (!response.ok) throw new Error("Unavailable");
      const body = await response.json();
      if (body.schema_version !== 1 || body.plan.material !== material || body.plan.requested_upgrades !== n) throw new Error("Invalid scenario");
      if (active === controller) render(body);
    } catch {
      if (active === controller) $("upgrade-status").textContent = "Recommendations unavailable. Check your connection and select Recommend upgrades to retry. No substitute metric is shown.";
    } finally {
      clearTimeout(timer);
      if (active === controller) { active = null; $("recommend-upgrades").disabled = false; }
    }
  });
  $("coverage-material").addEventListener("change", reset);
  $("upgrade-count").addEventListener("input", reset);
  reset();
})();
