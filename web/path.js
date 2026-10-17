/* Known waste selects a stream; the server checks every required bin capability. */
(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const picks = new Set();
  const controls = [...$("waste-picker").querySelectorAll("button[data-material]")];
  const activeMaterials = () => new Set(globalThis.TripUI.getItems().map(globalThis.TripUI.materialFor));
  function render() {
    const active = activeMaterials();
    for (const material of active) picks.delete(material);
    for (const button of controls) {
      const selected = active.has(button.dataset.material) || picks.has(button.dataset.material);
      button.setAttribute("aria-pressed", String(selected));
      button.classList.toggle("selected", selected);
    }
    $("confirm-picks").disabled = !picks.size;
    $("confirm-picks").hidden = !picks.size;
    $("confirm-picks").textContent = "Add to route";
    $("picker-condition").hidden = !picks.size;
    $("electronics-size").hidden = !picks.has("electronics");
    if (!picks.has("electronics")) $("small-electronics").checked = false;
    const conditions = [];
    if (["glass", "plastic_metal", "paper_tetrapak"].some((material) => picks.has(material))) conditions.push("Recyclables empty / clean.");
    if (picks.has("general")) conditions.push("General waste: ordinary household waste only.");
    if (picks.has("electronics")) conditions.push("Electronics: household devices only; no loose, swollen or leaking batteries.");
    if (picks.has("clothes")) conditions.push("Clothes: clean, washed and wearable — for donation.");
    $("picker-condition").replaceChildren(document.createTextNode("Confirm: "));
    for (const condition of conditions) {
      const phrase = document.createElement("span"); phrase.textContent = condition;
      $("picker-condition").append(phrase, document.createTextNode(" "));
    }
    const warning = document.createElement("span"); warning.textContent = "No hazardous contents.";
    $("picker-condition").append(warning);
    document.dispatchEvent(new CustomEvent("picker-change", { detail: picks.size > 0 }));
  }
  for (const button of controls) button.addEventListener("click", () => {
    $("picker-status").textContent = "";
    const material = button.dataset.material;
    if (activeMaterials().has(material)) globalThis.TripUI.removeMaterial(material);
    else if (picks.has(material)) picks.delete(material);
    else picks.add(material);
    render();
  });
  $("confirm-picks").addEventListener("click", () => {
    if (!picks.size) return;
    try {
      globalThis.TripUI.addStreams([...picks], { smallOnly: $("small-electronics").checked });
      picks.clear();
      $("picker-status").textContent = "";
      const behavior = matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth";
      $("trip-panel").scrollIntoView({ block: "nearest", behavior });
      globalThis.TripUI.focusNext();
    } catch (error) {
      $("picker-status").textContent = error.message;
    }
    render();
  });
  document.addEventListener("basket-change", render);
  render();
})();
