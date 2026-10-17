(function () {
  "use strict";
  if (!document.body.classList.contains("city")) return;
  const { el, request } = CommunityUI;
  const section = el("section", "", "community-panel card");
  section.id = "dumping-panel";
  const heading = el("h2", "Community reports");
  heading.id = "community-reports-heading";
  section.setAttribute("aria-labelledby", heading.id);
  section.append(heading);
  const body = el("div", "", "community-body"); section.append(body);
  body.append(el("h3", "Illegal dumping"));
  const mapNode = el("div", "", "community-map");
  mapNode.id = "dumping-map"; mapNode.setAttribute("aria-label", "Dumping report location map");
  body.append(mapNode);
  const layerLabel = el("label", "", "community-layer");
  const layerToggle = el("input"); layerToggle.type = "checkbox"; layerToggle.checked = true;
  layerLabel.append(layerToggle, document.createTextNode("Show reviewed reports")); body.append(layerLabel);
  const form = el("form", "", "dumping-form");
  form.innerHTML = '<div class="community-coordinates"><label>Dumping latitude<input name="latitude" type="number" step="any" min="41.8" max="42.2" required></label><label>Dumping longitude<input name="longitude" type="number" step="any" min="21.2" max="21.7" required></label></div><label>Description<textarea name="description" minlength="3" maxlength="500" rows="2" placeholder="What is dumped here?" required></textarea></label><label>Photo (optional)<input name="photo" type="file" accept="image/jpeg,image/png,image/webp"></label><p class="community-privacy">Choose a point on the map or enter coordinates. Location and description become public after review. Photos are visible only to reviewers; avoid faces and personal details. Reports are kept for 30 days, not sent to the municipality.</p><button type="submit">Submit report</button>';
  const message = el("p"); message.setAttribute("role", "status"); form.append(message); body.append(form);
  document.querySelector(".city-method").before(section);
  let map, pin, reportsLayer, submitted = null, saving = false, reportGeneration = 0;
  const lat = form.elements.latitude, lon = form.elements.longitude;
  function setPoint(latitude, longitude) {
    if (saving) return;
    submitted = null;
    lat.value = latitude.toFixed(6); lon.value = longitude.toFixed(6);
    pin?.remove(); pin = L.marker([latitude, longitude]).addTo(map).bindTooltip("Report location");
  }
  async function drawReports() {
    const current = ++reportGeneration;
    reportsLayer?.clearLayers();
    if (!map || !layerToggle.checked) return;
    try {
      const { reports } = await request("/api/v1/dumping-reports");
      if (current !== reportGeneration || !layerToggle.checked) return;
      for (const report of reports) {
        const popup = el("div"); popup.append(el("strong", report.state === "cleared" ? "Cleared" : "Reported dumping"), Object.assign(el("p", report.description), { translate: false }));
        L.circleMarker([report.latitude, report.longitude], {radius: 8, color: report.state === "cleared" ? "#3b6851" : "#9b503a", fillOpacity: .7}).addTo(reportsLayer).bindPopup(popup);
      }
    } catch {
      if (current === reportGeneration && layerToggle.checked) message.textContent = "Reports unavailable. Reload the page to retry.";
    }
  }
  try {
    map = L.map(mapNode).setView([41.998, 21.43], 13);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {maxZoom: 19, attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'}).addTo(map);
    reportsLayer = L.layerGroup().addTo(map);
    map.on("click", event => setPoint(event.latlng.lat, event.latlng.lng));
  } catch { mapNode.replaceChildren(el("p", "Map unavailable. Enter coordinates below.")); }
  drawReports();
  layerToggle.addEventListener("change", drawReports);
  form.addEventListener("input", event => {
    // Replacing a failed photo still belongs to the report already saved.
    if (submitted && event.target !== form.elements.photo) {
      submitted = null; form.querySelector('button[type="submit"]').textContent = "Submit report";
    }
  });
  form.addEventListener("submit", async event => {
    event.preventDefault();
    if (saving) return;
    const button = form.querySelector('button[type="submit"]');
    const photo = form.elements.photo.files[0];
    if (photo && photo.size > 5 * 1024 * 1024) { message.textContent = "Photo must be 5 MB or smaller."; return; }
    saving = true;
    for (const input of form.elements) input.disabled = true;
    message.textContent = "Saving…";
    try {
      if (!submitted) submitted = await request("/api/v1/dumping-reports", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({latitude: Number(lat.value), longitude: Number(lon.value), description: form.elements.description.value})});
      if (photo) await request(`/api/v1/dumping-reports/${submitted.id}/photo`, {method: "POST", headers: {"Content-Type": photo.type}, body: photo});
      message.textContent = "Report saved · awaiting review";
      form.reset(); submitted = null; pin?.remove();
      button.textContent = "Submit report";
    } catch (error) {
      message.textContent = submitted ? `Report saved, but photo failed: ${error.message}` : error.message;
      if (submitted) button.textContent = "Retry photo";
    } finally { saving = false; for (const input of form.elements) input.disabled = false; }
  });
})();
