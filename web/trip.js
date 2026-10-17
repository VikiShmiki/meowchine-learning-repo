/* A memory-only basket. Every trip is independently validated by the server. */
(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  let origin = null, basket = [], generation = 0, pending = null;
  let configured = false;
  let unconfirmedPicks = false;
  let editingOrigin = false;
  let currentRoute = null;
  const completedStops = new Set();
  let savingDropoffs = 0;
  const kindNames = { empty_glass_packaging: "Glass bottle/jar", empty_plastic_bottle: "Plastic bottle",
    empty_metal_can: "Metal can", clean_paper: "Clean paper", clean_cardboard: "Clean cardboard",
    empty_tetrapak: "Tetra Pak carton", glass: "Glass bottles & jars",
    plastic_metal: "Plastic bottles & cans", paper_tetrapak: "Paper, cardboard & cartons",
    general: "General waste", ordinary_residual: "General waste", electronics: "Electronics", small_electronics: "Small electronics", clothes: "Clothes · donation", wearable_clothes: "Clothes · donation" };
  const streams = { glass: ["empty_glass_packaging"],
    plastic_metal: ["empty_plastic_bottle", "empty_metal_can"],
    paper_tetrapak: ["clean_paper", "clean_cardboard", "empty_tetrapak"],
    general: ["ordinary_residual"], electronics: ["electronics", "small_electronics"], clothes: ["wearable_clothes"] };
  const materialFor = (item) => item.material || Object.keys(streams)
    .find((material) => streams[material].includes(item.manual_kind));
  function node(tag, value) {
    const element = document.createElement(tag);
    element.textContent = value;
    return element;
  }
  const travelMode = () => $("trip-mode").querySelector("input:checked").value;
  const includeParking = () => travelMode() === "driving" && $("include-parking").checked;
  function readiness() {
    if (unconfirmedPicks) return "Add your selected items to the route first.";
    if (editingOrigin && origin) return "Finish choosing your starting point.";
    if (basket.length && !origin) return "Choose a starting point.";
    return "";
  }
  function updatePlanButton() {
    $("plan-trip").disabled = !configured || !basket.length || !origin || Boolean(pending) || Boolean(savingDropoffs) || unconfirmedPicks || editingOrigin;
    $("plan-trip").textContent = pending ? "Finding route…" : "Find my route";
    $("plan-trip").setAttribute("aria-busy", String(Boolean(pending)));
    $("trip-completion").hidden = !currentRoute;
    $("finish-trip").disabled = Boolean(savingDropoffs || pending);
  }
  function invalidate() {
    currentRoute = null;
    completedStops.clear();
    generation += 1;
    pending?.abort();
    pending = null;
    updatePlanButton();
    $("trip-result").hidden = true;
    $("trip-result").replaceChildren();
    document.dispatchEvent(new CustomEvent("trip-route", { detail: null }));
    $("trip-status").textContent = readiness();
  }
  function finishTrip({ allDropped = false, saved = false } = {}) {
    if (savingDropoffs) return;
    invalidate();
    const panel = $("trip-checkin");
    const heading = node("h2", "Trip finished"); heading.id = "checkin-heading"; heading.tabIndex = -1;
    panel.replaceChildren(heading);
    const done = node("button", "Done"); done.type = "button"; done.className = "secondary";
    done.addEventListener("click", () => {
      panel.hidden = true; panel.replaceChildren();
      $("basket-add-item").focus({preventScroll: true});
      $("trip-panel").scrollIntoView({block: "start"});
    });
    panel.append(done); panel.hidden = false;
    $("trip-status").textContent = allDropped ? "All items marked dropped off."
      : "Trip ended. Items not marked dropped off are still in your basket.";
    if (saved) $("trip-status").textContent += " Saved to My activity.";
    heading.focus({preventScroll: true}); panel.scrollIntoView({block: "start"});
  }
  $("finish-trip").addEventListener("click", () => finishTrip());
  function renderBasket() {
    $("trip-items").replaceChildren();
    basket.forEach((item, index) => {
      const row = document.createElement("li");
      const remove = node("button", "");
      const icon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      icon.setAttribute("viewBox", "0 0 24 24");
      icon.setAttribute("class", "ui-icon");
      icon.setAttribute("aria-hidden", "true");
      const cross = document.createElementNS("http://www.w3.org/2000/svg", "path");
      cross.setAttribute("d", "M6 6l12 12M18 6 6 18");
      icon.append(cross);
      remove.append(icon);
      remove.setAttribute("aria-label", `Remove item ${index + 1}`);
      remove.type = "button";
      remove.className = "secondary";
      remove.addEventListener("click", () => { basket.splice(index, 1); invalidate(); renderBasket(); });
      row.append(node("span", kindNames[item.small_only ? "small_electronics" : item.material || item.manual_kind]), remove);
      $("trip-items").append(row);
    });
    $("continue-trip").hidden = basket.length === 0;
    updatePlanButton();
    $("basket-count").textContent = basket.length ? `${basket.length} selected` : "";
    $("basket-add-item").lastChild.textContent = basket.length ? "Edit waste types" : "Choose waste types";
    document.dispatchEvent(new CustomEvent("basket-change", { detail: basket.map((item) => ({ ...item })) }));
  }
  globalThis.TripUI = {
    isFull: () => basket.length >= 6,
    getItems: () => basket.map((item) => ({ ...item })),
    materialFor,
    focusNext() {
      const target = !$("plan-trip").disabled ? $("plan-trip")
        : !$("origin-summary").hidden ? $("change-origin") : $("locate");
      target.focus({ preventScroll: true });
    },
    addStreams(materials, { smallOnly = false } = {}) {
      if (materials.some((material) => !streams[material])) throw new Error("Unknown waste type.");
      const additions = [...new Set(materials)].filter((material) =>
        !basket.some((item) => materialFor(item) === material));
      if (basket.length + additions.length > 6) throw new Error("Your trip can hold six items. Remove an item and try again.");
      basket.push(...additions.map((material) => ({ material, condition_confirmed: true,
        accept_unverified: material === "general", ...(material === "electronics" ? { small_only: smallOnly } : {}) })));
      invalidate();
      renderBasket();
    },
    removeMaterial(material) {
      basket = basket.filter((item) => materialFor(item) !== material);
      invalidate();
      renderBasket();
    },
    addItems(items) {
      const additions = items.filter(({ answer }) => !basket.some((item) => item.manual_kind === answer.item_kind));
      if (additions.some(({ answer }) => answer.status !== "ready_for_site_matching" || !kindNames[answer.item_kind])) {
        throw new Error("Please review these items using the item helper.");
      }
      if (basket.length + additions.length > 6) throw new Error("Your trip can hold six items. Remove an item and try again.");
      basket.push(...additions.map(({ answer, description }) => ({ text: description, manual_kind: answer.item_kind, condition_confirmed: true })));
      invalidate();
      renderBasket();
    },
    removeKind(kind) {
      basket = basket.filter((item) => item.manual_kind !== kind);
      invalidate();
      renderBasket();
    },
    addItem(answer, description) {
      if (answer.status !== "ready_for_site_matching") return;
      const duplicate = basket.some((item) => item.material
        ? (item.small_only ? answer.item_kind === "small_electronics" : streams[item.material].includes(answer.item_kind))
        : item.manual_kind === answer.item_kind && item.text.toLowerCase() === description.toLowerCase());
      if (duplicate) {
        $("message").textContent = "This item is already in your trip. Its collection stop is covered.";
      } else if (basket.length >= 6) {
        $("message").textContent = "Your trip already has six items. Remove one before adding another.";
        return;
      } else {
        basket.push({ text: description, manual_kind: answer.item_kind, condition_confirmed: true });
        invalidate();
        renderBasket();
        $("message").textContent = "Added to your trip. Add another item or continue to trip planning.";
      }
      $("add-another").hidden = false;
      $("continue-trip").hidden = false;
    },
  };
  document.addEventListener("origin-change", (event) => { origin = event.detail; invalidate(); });
  document.addEventListener("origin-edit", (event) => {
    editingOrigin = event.detail;
    if (editingOrigin && pending) invalidate();
    updatePlanButton();
    $("trip-status").textContent = readiness();
  });
  document.addEventListener("picker-change", (event) => {
    if (unconfirmedPicks !== event.detail) {
      unconfirmedPicks = event.detail;
      invalidate();
    }
  });
  $("trip-mode").addEventListener("change", () => {
    $("transit-options").hidden = travelMode() !== "transit";
    $("parking-options").hidden = travelMode() !== "driving";
    invalidate();
  });
  $("transit-departure").addEventListener("change", invalidate);
  $("include-parking").addEventListener("change", invalidate);
  document.addEventListener("container-status-change", event => {
    if (!currentRoute || !currentRoute.stops.some(stop => !completedStops.has(stop) && stop.asset_ids?.some(id => event.detail.includes(id)))) return;
    const notice = $("route-condition-notice");
    if (notice) { notice.hidden = false; notice.querySelector("strong").textContent = "Container conditions changed · find an alternative route"; $("request-route-update").hidden = true; }
    document.dispatchEvent(new CustomEvent("trip-route", {detail: null}));
  });
  $("plan-trip").addEventListener("click", async () => {
    if (pending || savingDropoffs || !configured || !basket.length || !origin || unconfirmedPicks || editingOrigin) {
      $("trip-status").textContent = readiness();
      return;
    }
    invalidate();
    $("trip-checkin").hidden = true; $("trip-checkin").replaceChildren();
    const current = generation;
    const controller = new AbortController();
    pending = controller;
    const timer = setTimeout(() => controller.abort(), travelMode() === "transit" || includeParking() ? 75000 : 40000);
    updatePlanButton();
    $("trip-status").textContent = "Finding compatible sites and a network route…";
    try {
      const departure = travelMode() === "transit" && $("transit-departure").value
        ? new Date($("transit-departure").value).toISOString() : null;
      const response = await (globalThis.NajdiFrliI18n?.fetch || fetch)("/api/v1/trips", {
        method: "POST", headers: { "Content-Type": "application/json" }, signal: controller.signal,
        body: JSON.stringify({ origin, mode: travelMode(), items: basket, share_coordinates: true,
          ...(includeParking() ? {include_parking: true} : {}),
          ...(departure ? {departure_at: departure} : {}) }),
      });
      const body = await response.json();
      if (current !== generation) return;
      if (!response.ok) throw new Error(body.detail?.message || "Could not plan this trip. Check the items and try again.");
      currentRoute = body;
      const result = $("trip-result");
      result.replaceChildren(node("h3", `${{walking: "Walking", driving: "Driving", transit: "JSP bus"}[body.mode]} trip`));
      if (body.mode === "transit") {
        result.append(node("p", `About ${Math.ceil(body.duration_s / 60)} minutes including walking, waiting and intermediate drop-offs.`));
        result.append(node("p", "Scheduled times · Europe/Skopje. Check JSP notices for disruptions."));
        result.append(node("p", `Timetable checked: ${transitTime(body.transit_fetched_at)}. Service through: ${body.transit_service_end}.`));
      } else if (body.parking?.length) {
        result.append(node("p", `About ${Math.ceil(body.driving_duration_s / 60)} minutes driving + ${Math.ceil(body.walking_duration_s / 60)} minutes walking.`));
        result.append(node("p", "Includes walking back to the car between drop-offs. Excludes time finding a space, payment and disposal."));
        result.append(node("p", `Parking map dated ${body.parking_source_as_of.slice(0, 10)}. Space availability is unknown.`));
      } else result.append(node("p", `${(body.distance_m / 1000).toFixed(2)} km · about ${Math.ceil(body.duration_s / 60)} minutes on the network. Ends at the last stop.`));
      const viewMap = node("a", "View route on map");
      viewMap.href = "#site-map";
      result.append(viewMap);
      const update = node("div", ""); update.id = "route-condition-notice"; update.className = "route-update"; update.hidden = true;
      update.append(node("strong", "Update route"));
      const choices = node("div", ""); choices.className = "button-row";
      const sameStart = node("button", "Use existing start"); sameStart.type = "button";
      sameStart.addEventListener("click", () => $("plan-trip").click());
      const newStart = node("button", "Choose current position"); newStart.type = "button"; newStart.className = "secondary";
      newStart.addEventListener("click", () => { $("change-origin").click(); $("trip-panel").scrollIntoView({block: "start"}); });
      choices.append(sameStart, newStart); update.append(choices); result.append(update);
      const updateButton = node("button", "Update route"); updateButton.id = "request-route-update"; updateButton.className = "secondary"; updateButton.type = "button";
      updateButton.addEventListener("click", () => { update.hidden = false; updateButton.hidden = true; sameStart.focus(); }); result.append(updateButton);
      const stops = document.createElement("ol");
      stops.className = "route-stop-list";
      for (const [index, stop] of body.stops.entries()) {
        const row = document.createElement("li");
        row.id = `trip-stop-${index + 1}`;
        row.tabIndex = -1;
        const appearance = SiteData.stopAppearance(stop.item_kinds);
        row.style.setProperty("--stop-fill", appearance.background);
        row.style.setProperty("--stop-surface", appearance.surface);
        row.style.setProperty("--stop-ink", appearance.color);
        row.dataset.materials = appearance.materials.join(" ");
        const title = node("div", ""); title.className = "stop-card-heading";
        const number = node("span", String(index + 1)); number.className = "stop-card-number";
        title.append(number, node("strong", stop.name)); row.append(title);
        const materials = node("div", ""); materials.className = "stop-material-chips";
        for (const kind of stop.item_kinds) {
          const chip = node("span", kindNames[kind] || kind);
          const style = SiteData.stopAppearance([kind]);
          chip.style.setProperty("--material-color", SiteData.materialColors[style.materials[0]]);
          materials.append(chip);
        }
        row.append(materials);
        if (body.mode === "transit") row.append(transitItinerary(body.legs.filter(leg => leg.site_id === stop.site_id)));
        const parking = body.parking?.find(visit => visit.site_id === stop.site_id);
        if (parking) row.append(parkingItinerary(parking, index));
        const actions = node("div", ""); actions.className = "stop-actions";
        const completed = node("button", "Dropped off"); completed.type = "button";
        const reportProblem = node("button", "Report a problem"); reportProblem.type = "button"; reportProblem.className = "secondary report-problem-button";
        reportProblem.setAttribute("aria-haspopup", "dialog");
        completed.setAttribute("aria-haspopup", "dialog");
        const report = (problem, opener) => {
          if (globalThis.CommunityUI && stop.asset_ids?.length) CommunityUI.reportStop(stop.asset_ids,
            {problem, number: index + 1, appearance, opener});
        };
        reportProblem.addEventListener("click", () => report(true, reportProblem));
        actions.append(completed, reportProblem);
        const skipSave = node("button", "Mark without saving"); skipSave.type = "button"; skipSave.className = "secondary"; skipSave.hidden = true;
        const saveMessage = node("p", ""); saveMessage.setAttribute("role", "status");
        function finish(saved = false) {
          if (current !== generation || completedStops.has(stop)) return;
          completedStops.add(stop);
          basket = basket.filter(item => !stop.item_kinds.includes(item.material === "clothes" ? "wearable_clothes" : item.material ? item.small_only ? "small_electronics" : item.material : item.manual_kind));
          completed.disabled = true; completed.textContent = "Drop-off completed"; skipSave.hidden = true;
          row.dataset.completed = "true";
          saveMessage.textContent = saved ? "Saved to My activity." : "Marked dropped off.";
          renderBasket();
          if (!basket.length) finishTrip({allDropped: true, saved});
          else $("trip-status").textContent = "Stop completed. Continue to your next stop, or finish your trip.";
          report(false, basket.length ? reportProblem : $("checkin-heading"));
        }
        completed.addEventListener("click", async () => {
          if (completedStops.has(stop) || savingDropoffs) return;
          savingDropoffs += 1; updatePlanButton();
          completed.disabled = true; skipSave.hidden = true; saveMessage.textContent = "";
          try {
            const saved = globalThis.AccountUI ? await AccountUI.saveDropoff(stop.completion_ticket) : false;
            savingDropoffs -= 1;
            finish(saved);
          }
          catch (error) { saveMessage.textContent = error.message || "Could not save. Retry."; skipSave.hidden = false; }
          finally {
            savingDropoffs = 0;
            if (current === generation) completed.disabled = completedStops.has(stop);
            updatePlanButton();
          }
        });
        skipSave.addEventListener("click", () => { if (!savingDropoffs) finish(); });
        row.append(actions, skipSave, saveMessage);
        if (stop.unverified_materials?.includes("general")) {
          const warning = node("p", "General waste: acceptance unverified. Follow bin instructions. No hazardous, medical or bulky waste.");
          warning.className = "acceptance-warning"; row.append(warning);
        }
        const limits = document.createElement("details");
        limits.append(node("summary", "Stop details"));
        for (const note of stop.arrival_notes || []) limits.append(node("p", note));
        limits.append(node("p", `Recorded site is ${stop.network_access_gap_m} m from the route endpoint; access is unverified.`));
        for (const limit of stop.acceptance_limits) limits.append(node("p", limit));
        row.append(limits);
        stops.append(row);
      }
      result.append(stops);
      const notes = document.createElement("details");
      notes.append(node("summary", "Route sources & limitations"), node("p", `Infrastructure snapshot: ${body.source_as_of}. ${body.optimizer}.`));
      for (const warning of body.warnings) notes.append(node("p", warning));
      notes.append(node("p", body.attribution));
      result.append(notes);
      result.hidden = false;
      $("trip-status").textContent = "";
      document.dispatchEvent(new CustomEvent("trip-route", { detail: body }));
      if (body.status_version && globalThis.CommunityUI) CommunityUI.refresh().then(data => {
        if (current === generation && data.version !== body.status_version)
          document.dispatchEvent(new CustomEvent("container-status-change", {detail: body.stops.flatMap(stop => stop.asset_ids)}));
      }).catch(() => {});
      $("collection-points").scrollIntoView({ block: "start" });
    } catch (error) {
      if (current === generation) $("trip-status").textContent = error.name === "AbortError"
        ? "Routing took too long. Please retry."
        : error instanceof TypeError ? "Routing is unavailable. Check your connection and retry." : error.message;
    } finally {
      clearTimeout(timer);
      if (current === generation) { pending = null; updatePlanButton(); }
    }
  });
  function transitTime(value) {
    return new Intl.DateTimeFormat("en-GB", {timeZone: "Europe/Skopje", day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23"}).format(new Date(value));
  }
  function parkingItinerary(visit, index) {
    const panel = node("section", ""); panel.className = "parking-visit";
    panel.id = `parking-stop-${index + 1}`; panel.tabIndex = -1;
    panel.append(node("h4", `Park: ${visit.name}`));
    panel.append(node("p", "Space availability: unknown. Check signs before parking."));
    const details = node("details", ""); details.className = "parking-details";
    details.append(node("summary", "Parking details"));
    const fee = visit.fee === "yes" ? "Paid parking recorded" : visit.fee === "no" ? "No fee recorded" : visit.fee === "unknown" ? "Fee unknown" : `Recorded fee: ${visit.fee}`;
    details.append(node("p", fee), node("p", visit.opening_hours === "unknown" ? "Opening hours unknown" : `Recorded hours: ${visit.opening_hours}`));
    details.append(node("p", visit.point_kind === "driveway_crossing" ? "Mapped driveway crossing; entrance and access are unverified." : "Mapped parking point; entrance and access are unverified."));
    panel.append(node("strong", visit.walk_to.distance_m < 1
      ? "Parking and drop-off use the same network point. Check access on foot."
      : `Walk ${Math.round(visit.walk_to.distance_m)} m · about ${Math.ceil(visit.walk_to.duration_s / 60)} minutes to the drop-off.`));
    details.append(node("p", `Unverified walking access gaps: ${Math.round(visit.walk_to.start_gap_m)} m at parking, ${Math.round(visit.walk_to.end_gap_m)} m at the drop-off.`));
    details.append(node("p", `Driving endpoint is ${Math.round(visit.drive_access_gap_m)} m from the mapped parking point. Access is unverified.`));
    if (visit.walk_back) panel.append(node("p", `After disposal, walk back ${Math.round(visit.walk_back.distance_m)} m · about ${Math.ceil(visit.walk_back.duration_s / 60)} minutes to your car before the next drive.`));
    else panel.append(node("p", "Final drop-off: your car remains at this parking location. The final walk back is not included."));
    const source = node("a", "View parking on OpenStreetMap"); source.href = visit.source_url; source.target = "_blank"; source.rel = "noopener noreferrer";
    const data = node("a", "Parking data & license"); data.href = "/api/v1/parking"; data.target = "_blank"; data.rel = "noopener noreferrer";
    details.append(source, node("span", " · "), data); panel.append(details);
    return panel;
  }
  function transitItinerary(legs) {
    const list = node("ol", ""); list.className = "transit-legs";
    let previous = null;
    for (const leg of legs) {
      const row = node("li", ""); row.dataset.mode = leg.mode;
      if (previous && new Date(leg.departure_at) > new Date(previous)) {
        row.append(node("p", `Wait about ${Math.ceil((new Date(leg.departure_at) - new Date(previous)) / 60000)} minutes.`));
      }
      if (leg.mode === "bus") {
        row.append(node("strong", `Bus ${leg.line} · ${leg.headsign}`));
        row.append(node("p", `Board: ${leg.from_name}`), node("p", `Get off: ${leg.to_name}`));
        row.append(node("p", `${leg.stop_count} bus stops`));
      } else row.append(node("strong", `Walk about ${Math.ceil(leg.duration_s / 60)} minutes`), node("p", `${leg.from_name} → ${leg.to_name}`));
      row.append(node("p", `${transitTime(leg.departure_at)} → ${transitTime(leg.arrival_at)}`));
      list.append(row); previous = leg.arrival_at;
    }
    return list;
  }
  async function checkAvailability() {
    $("retry-routing").hidden = true;
    $("routing-availability").textContent = "Checking routing availability...";
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 10000);
    try {
      const response = await (globalThis.NajdiFrliI18n?.fetch || fetch)("/api/v1/routing", { signal: controller.signal });
      if (!response.ok) throw new Error("Unavailable");
      configured = (await response.json()).configured === true;
      $("routing-availability").textContent = configured ? ""
        : "Live routing is not configured. You can still add items.";
      $("retry-routing").hidden = configured;
      updatePlanButton();
    } catch {
      configured = false;
      updatePlanButton();
      $("retry-routing").hidden = false;
      $("routing-availability").textContent = "Could not connect to routing. Retry when connected.";
    }
    finally { clearTimeout(timer); }
  }
  $("retry-routing").addEventListener("click", checkAvailability);
  renderBasket();
  $("trip-status").textContent = readiness();
  checkAvailability();
})();
