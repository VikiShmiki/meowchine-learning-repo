/* A memory-only basket. Every trip is independently validated by the server. */
(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  let origin = null, basket = [], generation = 0, pending = null;
  let configured = false;
  let unconfirmedPicks = false;
  let editingOrigin = false;
  let currentRoute = null;
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
  function readiness() {
    if (unconfirmedPicks) return "Add your selected items to the route first.";
    if (editingOrigin && origin) return "Finish choosing your starting point.";
    if (basket.length && !origin) return "Choose a starting point.";
    return "";
  }
  function updatePlanButton() {
    $("plan-trip").disabled = !configured || !basket.length || !origin || Boolean(pending) || unconfirmedPicks || editingOrigin;
    $("plan-trip").textContent = pending ? "Finding route…" : "Find my route";
    $("plan-trip").setAttribute("aria-busy", String(Boolean(pending)));
  }
  function invalidate() {
    currentRoute = null;
    generation += 1;
    pending?.abort();
    pending = null;
    updatePlanButton();
    $("trip-result").hidden = true;
    $("trip-result").replaceChildren();
    document.dispatchEvent(new CustomEvent("trip-route", { detail: null }));
    $("trip-status").textContent = readiness();
  }
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
  $("trip-mode").addEventListener("change", invalidate);
  document.addEventListener("container-status-change", event => {
    if (!currentRoute || !currentRoute.stops.some(stop => stop.asset_ids?.some(id => event.detail.includes(id)))) return;
    const notice = $("route-condition-notice");
    if (notice) { notice.hidden = false; notice.querySelector("strong").textContent = "Container conditions changed · update your route"; $("request-route-update").hidden = true; }
    document.dispatchEvent(new CustomEvent("trip-route", {detail: null}));
  });
  $("plan-trip").addEventListener("click", async () => {
    if (pending || !configured || !basket.length || !origin || unconfirmedPicks || editingOrigin) {
      $("trip-status").textContent = readiness();
      return;
    }
    invalidate();
    const current = generation;
    const controller = new AbortController();
    pending = controller;
    const timer = setTimeout(() => controller.abort(), 40000);
    updatePlanButton();
    $("trip-status").textContent = "Finding compatible sites and a network route…";
    try {
      const response = await (globalThis.GoodsortI18n?.fetch || fetch)("/api/v1/trips", {
        method: "POST", headers: { "Content-Type": "application/json" }, signal: controller.signal,
        body: JSON.stringify({ origin, mode: travelMode(), items: basket, share_coordinates: true }),
      });
      const body = await response.json();
      if (current !== generation) return;
      if (!response.ok) throw new Error(body.detail?.message || "Could not plan this trip. Check the items and try again.");
      currentRoute = body;
      const result = $("trip-result");
      result.replaceChildren(node("h3", `${body.mode === "walking" ? "Walking" : "Driving"} trip`));
      result.append(node("p", `${(body.distance_m / 1000).toFixed(2)} km · about ${Math.ceil(body.duration_s / 60)} minutes on the network. Ends at the last stop.`));
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
        row.style.setProperty("--stop-ink", appearance.color);
        row.dataset.materials = appearance.materials.join(" ");
        row.append(node("strong", stop.name), node("p", `Drop off: ${stop.item_kinds.map((kind) => kindNames[kind] || kind).join(", ")}`));
        if (globalThis.CommunityUI && stop.asset_ids?.length) row.append(CommunityUI.containerControl(stop.asset_ids));
        const completed = node("button", "Dropped these off"); completed.className = "secondary"; completed.type = "button";
        const skipSave = node("button", "Mark without saving"); skipSave.type = "button"; skipSave.className = "secondary"; skipSave.hidden = true;
        const saveMessage = node("p", ""); saveMessage.setAttribute("role", "status");
        function finish(saved = false) {
          if (current !== generation) return;
          basket = basket.filter(item => !stop.item_kinds.includes(item.material === "clothes" ? "wearable_clothes" : item.material ? item.small_only ? "small_electronics" : item.material : item.manual_kind));
          invalidate(); renderBasket();
          $("trip-status").textContent = basket.length ? "Remaining items kept. Choose your current starting point, then find a route." : "All items marked dropped off.";
          if (basket.length) $("change-origin").click();
          if (saved) $("trip-status").textContent += " Saved to My activity.";
          $("trip-panel").scrollIntoView({block: "start"});
        }
        completed.addEventListener("click", async () => {
          completed.disabled = true; skipSave.hidden = true; saveMessage.textContent = "";
          try { finish(globalThis.AccountUI ? await AccountUI.saveDropoff(stop.completion_ticket) : false); }
          catch (error) { saveMessage.textContent = error.message || "Could not save. Retry."; skipSave.hidden = false; }
          finally { completed.disabled = false; }
        });
        skipSave.addEventListener("click", () => finish());
        row.append(completed, skipSave, saveMessage);
        for (const note of stop.arrival_notes || []) row.append(node("p", note));
        if (stop.unverified_materials?.includes("general")) {
          const warning = node("p", "General waste: acceptance unverified. Follow bin instructions. No hazardous, medical or bulky waste.");
          warning.className = "acceptance-warning";
          row.append(warning);
        }
        row.append(node("p", `Recorded site is ${stop.network_access_gap_m} m from the route endpoint; access is unverified.`));
        const limits = document.createElement("details");
        limits.append(node("summary", "Documented acceptance"));
        for (const limit of stop.acceptance_limits) limits.append(node("p", limit));
        if (stop.acceptance_limits.length) row.append(limits);
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
  async function checkAvailability() {
    $("retry-routing").hidden = true;
    $("routing-availability").textContent = "Checking routing availability...";
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 10000);
    try {
      const response = await (globalThis.GoodsortI18n?.fetch || fetch)("/api/v1/routing", { signal: controller.signal });
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
