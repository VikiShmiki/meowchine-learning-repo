/* Site discovery only. No item acceptance inference and no route computation. */
(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const names = { glass: "Glass", plastic_metal: "Plastic / metal", paper_tetrapak: "Paper / Tetra Pak",
    general: "General waste", special_unsupported: "Electronics", clothes: "Clothes · donation" };
  const colors = SiteData.materialColors;
  const cacheName = "sra-citizen-sites-v2";
  const endpoint = "/api/v1/sites?scope=citizen";
  let snapshot = null, map = null, markers = null, originMarker = null;
  let routeLayer = null, routeRenderer = null, activeRoute = null, showOtherSites = false;
  let origin = null, visible = [], selectedId = null, picking = false, locationRequest = 0;
  let editingOrigin = true;
  const resultLimit = 5;
  let tileErrors = false;
  let mapConfig = null, selectedMarker = null, discoveryRenderer = null;

  async function timedFetch(url, options = {}) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 12000);
    try {
      const response = await fetch(url, { ...options, signal: controller.signal });
      const body = response.status === 304 ? null : await response.arrayBuffer();
      return new Response(body, { status: response.status, headers: response.headers });
    }
    finally { clearTimeout(timer); }
  }
  function text(tag, value) {
    const node = document.createElement(tag);
    node.textContent = value;
    return node;
  }
  function keyboardActivate(marker) {
    marker.getElement().addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") return;
      event.preventDefault();
      event.stopPropagation();
      marker.fire("click");
    });
  }
  function cancelLocationRequest() {
    locationRequest += 1;
    $("locate").disabled = false;
    $("locate").textContent = "Use my location";
    $("locate").setAttribute("aria-busy", "false");
  }
  function renderOrigin() {
    $("origin-editor").hidden = !editingOrigin;
    $("origin-summary").hidden = !origin || editingOrigin;
    $("origin-edit-actions").hidden = !origin;
    document.dispatchEvent(new CustomEvent("origin-edit", { detail: editingOrigin }));
  }
  function restoreCoordinateFields() {
    $("latitude").value = origin ? origin.latitude.toFixed(6) : "";
    $("longitude").value = origin ? origin.longitude.toFixed(6) : "";
  }
  function setOrigin(latitude, longitude, description, label) {
    if (!SiteData.coordinates(latitude, longitude)) {
      $("origin-status").textContent = "Enter valid latitude (-90 to 90) and longitude (-180 to 180).";
      return;
    }
    const returnToTrip = picking;
    cancelLocationRequest();
    setPicking(false);
    origin = { latitude, longitude };
    editingOrigin = false;
    $("manual-origin").open = false;
    $("origin-details").open = false;
    $("origin-label").textContent = label || "Point on map";
    $("origin-coordinates").textContent = `${description}: ${latitude.toFixed(5)}, ${longitude.toFixed(5)}.`;
    $("origin-status").textContent = "";
    renderOrigin();
    document.dispatchEvent(new CustomEvent("origin-change", { detail: origin }));
    restoreCoordinateFields();
    drawOrigin();
    if (map) map.setView([latitude, longitude], 16, { animate: false });
    render();
    if (returnToTrip) {
      $("trip-panel").scrollIntoView({ block: "start" });
    }
    $("origin-label").focus({ preventScroll: true });
  }
  function drawOrigin() {
    if (!map || !origin) return;
    originMarker?.remove();
    const badge = text("span", "");
    badge.className = "origin-pin";
    originMarker = L.marker([origin.latitude, origin.longitude], {
      icon: L.divIcon({ className: "origin-marker", html: badge, iconSize: [28, 28], iconAnchor: [14, 14] }),
      title: "Starting point", zIndexOffset: 1000, interactive: false,
    }).addTo(map).bindTooltip("Starting point");
  }
  function setPicking(enabled) {
    picking = enabled;
    $("pick-controls").hidden = !enabled;
    $("pick-origin").setAttribute("aria-pressed", String(enabled));
    $("map-pick-hint").hidden = !enabled;
    $("map-shell").classList.toggle("is-picking", enabled);
    render();
  }
  function showDetails(site, focus = true) {
    selectedId = site.id;
    const panel = $("site-details");
    panel.replaceChildren(text("h3", site.assets[0].name));
    for (const asset of site.assets) {
      const article = document.createElement("article");
      if (site.assets.length > 1) article.append(text("h4", asset.name));
      article.append(text("p", `${asset.municipality_name} · ${asset.collection_mode.replaceAll("_", " ")}`));
      article.append(text("p", `Recorded materials: ${asset.source_materials.join(", ").replaceAll("_", " ")}.`));
      article.append(text("p", asset.acceptance
        ? `Acceptance limits: ${asset.acceptance.limits}`
        : "Item acceptance is not confirmed. This record does not establish where your item should go."));
      article.append(text("p", `Operating status: ${asset.operational_status}. Last field check: ${asset.provenance.last_field_verified_at || "not recorded"}.`));
      if (globalThis.CommunityUI) article.append(CommunityUI.containerControl([asset.id]));
      if (asset.address) article.append(text("p", `Address: ${asset.address}`));
      const source = document.createElement("details");
      source.append(text("summary", "Source & data notes"));
      source.append(text("p", `Site ${site.id} · ${site.latitude.toFixed(6)}, ${site.longitude.toFixed(6)}`));
      source.append(text("p", `Source: ${asset.provenance.source_name} · as of ${asset.provenance.as_of_date}.`));
      if (asset.qa_flags.length) source.append(text("p", `Data notes: ${asset.qa_flags.join(", ").replaceAll("_", " ")}.`));
      if (asset.provenance.source_url.startsWith("https://")) {
        const link = text("a", "View source record service");
        link.href = asset.provenance.source_url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        source.append(link);
      }
      article.append(source);
      panel.append(article);
    }
    panel.hidden = false;
    drawDiscovery();
    if (focus) panel.focus({ preventScroll: false });
  }
  function renderSearchResults() {
    $("site-list").replaceChildren();
    const searching = $("site-search").value.trim().length >= 2;
    $("site-list").hidden = !searching || visible.length === 0;
    $("search-status").textContent = !searching
      ? ""
      : visible.length === 0 ? "No matching collection points. Try another name, address or municipality."
        : visible.length > resultLimit
          ? `Showing ${resultLimit} of ${visible.length} matches. Keep typing or choose a material to narrow your search.`
          : `${visible.length} matching collection ${visible.length === 1 ? "point" : "points"}.`;
    if (!searching) return;
    for (const entry of visible.slice(0, resultLimit)) {
      const button = text("button", entry.site.assets[0].name);
      button.type = "button";
      button.className = "site-button";
      button.addEventListener("click", () => {
        if (activeRoute) { showOtherSites = true; updateRouteView(); }
        map?.setView([entry.site.latitude, entry.site.longitude], 16, { animate: false });
        showDetails(entry.site);
      });
      const li = document.createElement("li");
      li.append(button, text("p", `${entry.site.assets[0].municipality_name} · ${entry.site.materials.map((m) => names[m]).join(" / ")}`));
      if (entry.distance !== null) li.append(text("p", `${(entry.distance / 1000).toFixed(2)} km straight-line`));
      $("site-list").append(li);
    }
  }
  function render(fit = false) {
    if (!snapshot) return;
    visible = SiteData.discover(snapshot.sites, $("material-filter").value, $("site-search").value, origin);
    $("site-count").textContent = picking
      ? "Choose your starting point. Collection markers are hidden while selecting."
      : activeRoute && !showOtherSites
      ? "Showing your route and stops only. Other collection points are hidden."
      : visible.length
      ? `${visible.length.toLocaleString()} recorded sites in this dataset. ${origin ? "Search matches sorted by straight-line distance." : ""}`
      : "No recorded sites match this filter. This does not mean disposal is safe elsewhere. Try another material or clear the search.";
    if (!visible.some(({ site }) => site.id === selectedId)) {
      $("site-details").hidden = true;
      selectedId = null;
    } else if (selectedId) showDetails(visible.find(({ site }) => site.id === selectedId).site, false);
    drawDiscovery();
    if (fit && map && visible.length && !activeRoute) {
      map.fitBounds(visible.map(({ site }) => [site.latitude, site.longitude]), {
        paddingTopLeft: [40, 70], paddingBottomRight: [40, 155], maxZoom: 16, animate: false,
      });
    }
    renderSearchResults();
  }
  function drawDiscovery() {
    if (!map || !markers) return;
    const hidden = picking || Boolean(activeRoute && !showOtherSites);
    map.getPane("discovery").hidden = hidden;
    $("map-legend").hidden = picking;
    $("route-map-key").hidden = picking || !activeRoute;
    $("map-pick-hint").hidden = !picking;
    $("map-shell").classList.toggle("is-picking", picking);
    $("map-shell").classList.toggle("has-route", Boolean(activeRoute));
    $("map-context-label").textContent = picking ? "Choose a starting point" : activeRoute
      ? `${{walking: "Walking", driving: "Driving", transit: "JSP bus"}[activeRoute.mode]} route` : "Skopje · Collection points";
    const bounds = map.getBounds();
    const inView = visible.filter(({ site }) => bounds.contains([site.latitude, site.longitude]));
    $("map-view-count").textContent = picking ? "Location is not shared yet" : activeRoute && !showOtherSites
      ? `${activeRoute.stops.length} ${activeRoute.stops.length === 1 ? "stop" : "stops"} · Ends at last stop`
      : !snapshot ? "Site data unavailable" : `${inView.length} ${inView.length === 1 ? "site" : "sites"} in view`;
    $("map-overview").disabled = !visible.length || picking || Boolean(activeRoute && !showOtherSites);
    markers.clearLayers();
    selectedMarker = null;
    $("site-map").dataset.zoom = String(map.getZoom());
    if (hidden) return;
    const paddedBounds = bounds.pad(0.15);
    const nearby = visible.filter(({ site }) => paddedBounds.contains([site.latitude, site.longitude]));
    for (const { site } of nearby) {
      const material = $("material-filter").value !== "all" ? $("material-filter").value
        : site.materials[0];
      const selected = site.id === selectedId;
      const radius = SiteData.markerRadius(map.getZoom(), selected);
      const marker = L.circleMarker([site.latitude, site.longitude], {
        pane: "discovery", renderer: discoveryRenderer, radius,
        color: selected ? "#263c30" : "#fff", fillColor: colors[material] || "#66736c",
        fillOpacity: 1, weight: selected ? 3 : map.getZoom() < 15 ? 1 : 1.5, bubblingMouseEvents: false,
      }).addTo(markers).bindTooltip(text("span", `${site.assets[0].name} · ${site.materials.map((m) => names[m]).join(" / ")}`))
        .on("click", () => showDetails(site))
        .on("mouseover", () => { marker.setRadius(radius + 2); marker.bringToFront(); })
        .on("mouseout", () => { marker.setRadius(radius); selectedMarker?.bringToFront(); });
      if (selected) selectedMarker = marker;
    }
    selectedMarker?.bringToFront();
  }
  async function loadSites() {
    $("refresh-sites").disabled = true;
    $("data-status").textContent = "Loading the City site snapshot…";
    let cache = null, saved = null;
    try {
      cache = await caches.open(cacheName);
      saved = await cache.match(endpoint);
      if (saved) SiteData.validate(await saved.clone().json());
    } catch { saved = null; }
    try {
      const response = await timedFetch(endpoint, {
        headers: saved?.headers.get("ETag") ? { "If-None-Match": saved.headers.get("ETag") } : {},
      });
      if (response.status === 304 && saved) snapshot = SiteData.validate(await saved.clone().json());
      else {
        if (!response.ok) throw new Error("Site download failed");
        snapshot = SiteData.validate(await response.clone().json());
        try { await cache?.put(endpoint, response); } catch { /* Storage quota/private mode: live data still works. */ }
      }
      $("data-status").textContent = `City snapshot ${snapshot.dataset_version} · as of ${snapshot.as_of_date}. ${snapshot.site_count.toLocaleString()} sites / ${snapshot.asset_count.toLocaleString()} assets. Not live availability.`;
    } catch {
      if (saved) snapshot = SiteData.validate(await saved.json());
      if ($("data-details")) $("data-details").open = true;
      $("data-status").textContent = snapshot
        ? `Refresh unavailable. Showing saved snapshot as of ${snapshot.as_of_date}; locations and availability may have changed. Retry when connected.`
        : "Site data is unavailable and no saved snapshot exists. Check your connection, then retry.";
    } finally {
      $("refresh-sites").disabled = false;
      render();
    }
  }
  async function initMap() {
    try {
      const response = await timedFetch("/static/map-config.json?v=map-refresh-2");
      if (!response.ok || !globalThis.L) throw new Error("Map unavailable");
      const config = await response.json();
      mapConfig = config;
      map = L.map("site-map", { preferCanvas: true, scrollWheelZoom: false, zoomControl: false }).setView(config.center, config.zoom);
      map.createPane("discovery");
      // Draw every site at its real coordinates; smaller dots keep the overview light.
      discoveryRenderer = L.canvas({ pane: "discovery", tolerance: 7 }).addTo(map);
      markers = L.layerGroup().addTo(map);
      L.control.zoom({ position: "bottomright" }).addTo(map);
      L.control.scale({ position: "bottomright", imperial: false, maxWidth: 80 }).addTo(map);
      map.on("moveend", drawDiscovery);
      $("map-home").disabled = false;
      const tiles = L.tileLayer(config.tile_url, { maxZoom: config.max_zoom, attribution: config.attribution }).addTo(map);
      tiles.on("tileerror", () => {
        tileErrors = true;
        $("retry-map").hidden = false;
        $("map-status").textContent = "Some map tiles are unavailable. Search for collection points above or retry the map when connected.";
      });
      $("retry-map").addEventListener("click", () => {
        $("map-status").textContent = "Retrying map tiles…";
        tileErrors = false;
        tiles.redraw();
      });
      tiles.on("load", () => {
        if (!tileErrors && (globalThis.GoodsortI18n?.original($("map-status").firstChild) || $("map-status").textContent) === "Retrying map tiles…") {
          $("map-status").textContent = "";
          $("retry-map").hidden = true;
        }
      });
      map.on("click", (event) => {
        if (picking) setOrigin(event.latlng.lat, event.latlng.lng, "Selected starting point");
      });
      $("pick-origin").disabled = $("center-origin").disabled = false;
      $("map-status").textContent = "";
      drawOrigin();
      updateRouteView();
      if (activeRoute) drawRoute();
    } catch {
      $("map-status").textContent = "Map unavailable. Search for collection points above. Coordinate entry still works; reload the page to retry the map.";
      $("map-view-count").textContent = "Map unavailable";
      $("retry-map").disabled = true;
    }
  }
  $("material-filter").addEventListener("change", () => render(true));
  $("site-search").addEventListener("input", () => render(true));
  $("refresh-sites").addEventListener("click", loadSites);
  $("map-overview").addEventListener("click", () => {
    if (!map || !visible.length || picking) return;
    map.fitBounds(visible.map(({ site }) => [site.latitude, site.longitude]), {
      paddingTopLeft: [40, 70], paddingBottomRight: [40, 155], maxZoom: 16, animate: false,
    });
  });
  $("map-home").addEventListener("click", () => {
    if (!map || !mapConfig) return;
    if (activeRoute) fitRoute();
    else map.setView(origin ? [origin.latitude, origin.longitude] : mapConfig.center,
      origin ? 16 : mapConfig.zoom, { animate: false });
  });
  $("origin-form").addEventListener("submit", (event) => {
    event.preventDefault();
    if (!$("latitude").value.trim() || !$("longitude").value.trim()) return;
    setOrigin(Number($("latitude").value), Number($("longitude").value), "Manual starting point", "Custom coordinates");
  });
  $("manual-origin").addEventListener("toggle", () => {
    if (!$("manual-origin").open) return;
    cancelLocationRequest();
    setPicking(false);
    $("origin-status").textContent = "";
  });
  $("change-origin").addEventListener("click", () => {
    editingOrigin = true;
    restoreCoordinateFields();
    renderOrigin();
    $("locate").focus();
  });
  function cancelOriginEdit() {
    cancelLocationRequest();
    setPicking(false);
    editingOrigin = !origin;
    $("manual-origin").open = false;
    $("origin-status").textContent = "";
    restoreCoordinateFields();
    renderOrigin();
    $("trip-panel").scrollIntoView({ block: "nearest" });
    (origin ? $("change-origin") : $("pick-origin")).focus({ preventScroll: true });
  }
  $("cancel-origin-edit").addEventListener("click", cancelOriginEdit);
  $("pick-origin").addEventListener("click", () => {
    cancelLocationRequest();
    $("manual-origin").open = false;
    setPicking(!picking);
    if (picking) $("site-map").scrollIntoView({ block: "center" });
    $("origin-status").textContent = "";
  });
  $("cancel-origin").addEventListener("click", cancelOriginEdit);
  $("center-origin").addEventListener("click", () => {
    const center = map.getCenter();
    setOrigin(center.lat, center.lng, "Map center starting point");
  });
  $("clear-origin").addEventListener("click", () => {
    cancelLocationRequest();
    origin = null;
    editingOrigin = true;
    document.dispatchEvent(new CustomEvent("origin-change", { detail: null }));
    originMarker?.remove();
    originMarker = null;
    setPicking(false);
    $("manual-origin").open = false;
    $("origin-label").textContent = $("origin-coordinates").textContent = "";
    restoreCoordinateFields();
    $("origin-status").textContent = "";
    renderOrigin();
    render();
    $("locate").focus();
  });
  $("locate").addEventListener("click", () => {
    cancelLocationRequest();
    const request = locationRequest;
    setPicking(false);
    $("manual-origin").open = false;
    if (!navigator.geolocation) {
      $("origin-status").textContent = "Location is unavailable. Select a point on the map or enter coordinates.";
      return;
    }
    $("locate").disabled = true;
    $("locate").textContent = "Locating…";
    $("locate").setAttribute("aria-busy", "true");
    $("origin-status").textContent = "Waiting for location permission…";
    navigator.geolocation.getCurrentPosition((position) => {
      if (request !== locationRequest) return;
      setOrigin(position.coords.latitude, position.coords.longitude,
        `Device location (reported accuracy ±${Math.round(position.coords.accuracy)} m)`, "Current location");
    }, (error) => {
      if (request !== locationRequest) return;
      cancelLocationRequest();
      $("origin-status").textContent = `${error.code === 1 ? "Location permission denied" : "Could not get your location"}. Choose a point on the map or enter coordinates.`;
    }, { enableHighAccuracy: false, timeout: 10000, maximumAge: 0 });
  });
  initMap();
  function fitRoute() {
    if (!map || !routeLayer) return;
    const keys = [$("map-legend"), $("route-map-key")].filter((key) => !key.hidden);
    const bottom = Math.max(85, ...keys.map((key) => map.getSize().y - key.offsetTop + 24));
    map.stop().fitBounds(routeLayer.getBounds(), {
      paddingTopLeft: [45, 85], paddingBottomRight: [65, bottom], maxZoom: 17, animate: false,
    });
  }
  function updateRouteView() {
    $("fit-route").disabled = !map;
    $("route-controls").hidden = !activeRoute;
    $("route-map-key").dataset.mode = activeRoute?.mode || "";
    $("route-mode-label").textContent = activeRoute?.mode === "transit" ? "JSP bus + walking" : activeRoute?.mode === "walking" ? "Walking" : "Driving";
    $("map-heading").textContent = activeRoute ? "Route & stops" : "Collection points";
    $("show-other-sites").textContent = showOtherSites ? "Hide other collection points" : "Show other collection points";
    $("show-other-sites").setAttribute("aria-pressed", String(showOtherSites));
    render();
  }
  $("fit-route").addEventListener("click", fitRoute);
  $("show-other-sites").addEventListener("click", () => {
    showOtherSites = !showOtherSites;
    $("discovery-controls").open = showOtherSites;
    updateRouteView();
  });
  document.addEventListener("trip-route", (event) => {
    routeLayer?.remove();
    routeLayer = null;
    const hadRoute = Boolean(activeRoute);
    activeRoute = event.detail;
    if (activeRoute || hadRoute) $("discovery-controls").open = !activeRoute;
    showOtherSites = false;
    updateRouteView();
    if (!activeRoute) return;
    $("site-details").hidden = true;
    selectedId = null;
    $("route-summary").textContent = activeRoute.mode === "transit"
      ? `JSP bus + walking | about ${Math.ceil(activeRoute.duration_s / 60)} minutes including waits. Scheduled service, not live tracking.`
      : `${activeRoute.mode === "walking" ? "Walking" : "Driving"} | ${(activeRoute.distance_m / 1000).toFixed(2)} km | about ${Math.ceil(activeRoute.duration_s / 60)} min | ${activeRoute.stops.length} ${activeRoute.stops.length === 1 ? "stop" : "stops"}. Finish at the last stop. Access gaps are unverified.`;
    drawRoute();
  });
  function drawRoute() {
    if (!map || !activeRoute) return;
    routeLayer?.remove();
    routeRenderer ||= L.svg();
    routeLayer = L.featureGroup().addTo(map);
    const segments = activeRoute.mode === "transit" ? activeRoute.legs : [{geometry: activeRoute.geometry, mode: activeRoute.mode}];
    for (const segment of segments) {
      if (segment.geometry) {
        L.geoJSON(segment.geometry, { renderer: routeRenderer, interactive: false, style: { color: "#fff", weight: 10, opacity: 0.95 } }).addTo(routeLayer);
        L.geoJSON(segment.geometry, { renderer: routeRenderer, interactive: false, style: {
          className: `trip-route-line ${segment.mode === "bus" ? "bus-route-line" : ""}`, color: segment.mode === "bus" ? "#305d9b" : "#2f4d35", weight: 5, opacity: 1,
          lineCap: "round", lineJoin: "round", dashArray: segment.mode === "walking" ? "8 10" : null,
        } }).addTo(routeLayer);
      }
      if (segment.mode === "bus") {
        for (const [point, name] of [[segment.from_point, segment.from_name], [segment.to_point, segment.to_name]]) {
          L.circleMarker([point[1], point[0]], {radius: 5, color: "#305d9b", fillColor: "#fff", fillOpacity: 1, renderer: routeRenderer})
            .bindTooltip(text("span", `${segment.line} · ${name}`)).addTo(routeLayer);
        }
      }
    }
    activeRoute.stops.forEach((stop, index) => {
      const badge = text("span", String(index + 1));
      badge.className = "route-stop-number";
      const appearance = SiteData.stopAppearance(stop.item_kinds);
      badge.style.setProperty("--stop-fill", appearance.background);
      badge.style.setProperty("--stop-ink", appearance.color);
      badge.dataset.materials = appearance.materials.join(" ");
      const label = `Stop ${index + 1}: ${stop.name} · ${appearance.label}`;
      const stopMarker = L.marker([stop.latitude, stop.longitude], {
        icon: L.divIcon({ className: "route-stop", html: badge, iconSize: [32, 32], iconAnchor: [16, 16] }),
        title: label, bubblingMouseEvents: false,
      }).bindTooltip(text("span", label)).on("click", () => {
        if (picking) setOrigin(stop.latitude, stop.longitude, "Selected starting point");
        else $("trip-stop-" + (index + 1))?.focus();
      }).addTo(routeLayer);
      stopMarker.getElement().setAttribute("aria-label", label);
      keyboardActivate(stopMarker);
    });
    fitRoute();
  }
  loadSites();
})();
