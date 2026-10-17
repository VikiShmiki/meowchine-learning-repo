const form = document.querySelector("#classify-form");
const item = document.querySelector("#item");
const result = document.querySelector("#result");
const category = document.querySelector("#category");
const message = document.querySelector("#message");
const question = document.querySelector("#question");
const manualForm = document.querySelector("#manual-form");
const selection = document.querySelector("#item-kind");
const conditionLabel = document.querySelector("#condition-label");
const contact = document.querySelector("#contact");
const phone = document.querySelector("#phone");
const submit = form.querySelector("button");
const manualSubmit = manualForm.querySelector("button");
const photoInput = document.querySelector("#item-photo");
const photoButton = document.querySelector("#analyze-photo");
const photoResult = document.querySelector("#photo-result");
const photoStatus = document.querySelector("#photo-status");
const photoItems = document.querySelector("#photo-items");
const labels = {
  glass: "Glass packaging", plastic_metal: "Plastic bottles / metal cans",
  paper_tetrapak: "Paper / cardboard / Tetra Pak", general: "General waste",
  special_unsupported: "Specialist disposal",
};
let generation = 0;
let pending = null;
let pendingPhoto = null;
let photoGeneration = 0;

function updateCondition() {
  const routable = !["batteries", "other"].includes(selection.value);
  conditionLabel.textContent = selection.value === "wearable_clothes"
    ? "Clothes are clean, washed and wearable, ready for donation. No damaged or contaminated textiles."
    : selection.value === "small_electronics"
    ? "Phone, charger, cable or earbuds only. No loose batteries, swollen/leaking batteries or chemical contamination."
    : selection.value === "electronics"
    ? "Household device only. No loose batteries, swollen/leaking batteries or chemical contamination."
    : selection.value === "ordinary_residual"
      ? "Used household tissues or nappies only. No clinical or hazardous waste."
      : "By adding, you confirm the selected item type, that it is empty/clean, and that it has no hazardous contents.";
  conditionLabel.hidden = !routable;
  manualSubmit.textContent = routable ? "Confirm & add to trip" : "Show disposal guidance";
}

function render(answer) {
  const displayedCategory = answer.suggested_item_kind === "wearable_clothes" && !answer.item_kind
    ? "Clothing · check condition"
    : answer.suggested_item_kind === "electronics" && !answer.item_kind
    ? "Electronics · check item"
    : answer.item_kind === "wearable_clothes" ? "Clothes · donation"
    : answer.item_kind === "small_electronics" ? "Small electronics"
    : answer.item_kind === "electronics" ? "Electronics"
    : labels[answer.category] || labels[answer.suggested_category];
  category.textContent = answer.suggested_category && !answer.category
    ? `Suggested: ${displayedCategory}`
    : displayedCategory || (answer.status === "held"
      ? "Disposal guidance not confirmed" : "Tell us a little more");
  message.textContent = answer.status === "confirm_condition" && !["ordinary_residual", "electronics", "small_electronics", "wearable_clothes"].includes(answer.item_kind)
    ? "Check the suggested item type below. Change it if needed." : answer.message;
  question.textContent = answer.status === "confirm_condition" ? "" : answer.clarification_question || "";
  selection.replaceChildren();
  for (const choice of answer.choices) selection.add(new Option(choice.label, choice.id));
  if (answer.item_kind && answer.choices.length) selection.value = answer.item_kind;
  else selection.selectedIndex = -1;
  manualForm.hidden = answer.choices.length === 0;
  updateCondition();
  contact.hidden = !answer.contact_url;
  contact.textContent = ["electronics", "small_electronics"].includes(answer.item_kind)
    ? "Request home pickup · Nula Otpad" : "Operator guidance";
  contact.removeAttribute("href");
  if (answer.contact_url) contact.href = answer.contact_url;
  phone.hidden = !answer.phone;
  phone.removeAttribute("href");
  phone.textContent = answer.phone ? `Call ${answer.phone}` : "";
  if (answer.phone) phone.href = `tel:${answer.phone}`;
}

async function classify(manual = false, suggestedKind = null) {
  if (pending) return;
  if (manual && !selection.value) { selection.reportValidity(); return; }
  if (manual && !["batteries", "other"].includes(selection.value)
      && globalThis.TripUI?.isFull()) {
    message.textContent = "Your trip already has six items. Remove one from the basket before adding another.";
    return;
  }
  const current = ++generation;
  pending?.abort();
  const controller = new AbortController();
  pending = controller;
  const timeout = setTimeout(() => controller.abort(), 10000);
  submit.disabled = manualSubmit.disabled = true;
  form.setAttribute("aria-busy", "true");
  result.hidden = false;
  category.textContent = "Checking your item…";
  message.textContent = "";
  contact.hidden = phone.hidden = true;
  if (!manual) manualForm.hidden = true;
  const payload = { text: item.value.trim() };
  if (manual || suggestedKind) {
    payload.manual_kind = suggestedKind || selection.value;
    payload.condition_confirmed = manual
      && !["batteries", "other"].includes(selection.value);
  }
  try {
    const response = await (globalThis.NajdiFrliI18n?.fetch || fetch)("/api/v1/classify", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload), signal: controller.signal,
    });
    if (!response.ok) throw new Error("request_failed");
    const answer = await response.json();
    if (current !== generation) return;
    render(answer);
    if (manual && answer.status === "ready_for_site_matching") {
      globalThis.TripUI?.addItem(answer, payload.text);
    }
  } catch (error) {
    if (current !== generation) return;
    category.textContent = "Could not check this item";
    message.textContent = error.name === "AbortError"
      ? "The request took too long. Please try again."
      : "Check your connection and item description, then try again.";
    question.textContent = "";
    manualForm.hidden = !manual;
  } finally {
    clearTimeout(timeout);
    if (current === generation) {
      submit.disabled = manualSubmit.disabled = false;
      form.setAttribute("aria-busy", "false");
      pending = null;
    }
  }
}

function photoErrorMessage(body, status) {
  const detail = body?.detail;
  if (typeof detail?.message === "string") return detail.message;
  if (status === 413) return "The photo must be 8 MB or smaller.";
  if (status === 415 || status === 422) return "Choose a clear JPEG, PNG or WebP photo.";
  return "Photo analysis is unavailable right now. You can still describe an item manually.";
}

function usePhotoSuggestion(suggestion) {
  item.value = suggestion.description;
  item.dispatchEvent(new Event("input"));
  result.hidden = false;
  result.scrollIntoView({ behavior: "smooth", block: "start" });
  if (suggestion.status === "needs_review") {
    category.textContent = "Describe this item manually";
    message.textContent = "The photo was not clear enough for a safe suggestion. Add the material and condition, then check it.";
    item.focus();
    return;
  }
  classify(false, suggestion.item_kind);
}

function renderPhotoSuggestions(answer) {
  photoItems.replaceChildren();
  photoStatus.textContent = answer.message;
  for (const suggestion of answer.items) {
    const entry = document.createElement("li");
    const title = document.createElement("strong");
    title.setAttribute("translate", "no");
    title.textContent = suggestion.description;
    const proposed = document.createElement("p");
    proposed.textContent = suggestion.category
      ? `Suggested stream: ${suggestion.item_kind === "wearable_clothes" ? "Clothes · donation" : suggestion.item_kind === "small_electronics" ? "Small electronics" : suggestion.item_kind === "electronics" ? "Electronics" : labels[suggestion.category] || suggestion.category}`
      : "No safe stream suggestion yet";
    const reason = document.createElement("p");
    reason.setAttribute("translate", "no");
    reason.textContent = suggestion.reason;
    const action = document.createElement("button");
    action.type = "button";
    action.className = "secondary";
    action.textContent = suggestion.status === "specialist"
      ? "Show disposal guidance"
      : suggestion.status === "candidate" ? "Review suggestion" : "Describe manually";
    action.addEventListener("click", () => usePhotoSuggestion(suggestion));
    entry.append(title, proposed, reason, action);
    photoItems.append(entry);
  }
}

async function analyzePhoto() {
  const photo = photoInput.files?.[0];
  if (!photo || pendingPhoto) return;
  if (!["image/jpeg", "image/png", "image/webp"].includes(photo.type)) {
    photoResult.hidden = false;
    photoStatus.textContent = "Choose a JPEG, PNG or WebP photo.";
    return;
  }
  if (photo.size > 8 * 1024 * 1024) {
    photoResult.hidden = false;
    photoStatus.textContent = "The photo must be 8 MB or smaller.";
    return;
  }
  const controller = new AbortController();
  const current = ++photoGeneration;
  pendingPhoto = controller;
  const timeout = setTimeout(() => controller.abort(), 35000);
  photoButton.disabled = true;
  photoInput.disabled = true;
  photoResult.hidden = false;
  photoItems.replaceChildren();
  photoStatus.textContent = "Analyzing the photo…";
  try {
    const response = await (globalThis.NajdiFrliI18n?.fetch || fetch)("/api/v1/photo-suggestions", {
      method: "POST", headers: { "Content-Type": photo.type }, body: photo,
      signal: controller.signal,
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw Object.assign(new Error("request_failed"), { body, status: response.status });
    if (current !== photoGeneration) return;
    renderPhotoSuggestions(body);
  } catch (error) {
    if (current !== photoGeneration) return;
    photoStatus.textContent = error.name === "AbortError"
      ? "Photo analysis took too long. Please try again or describe the item manually."
      : photoErrorMessage(error.body, error.status);
  } finally {
    clearTimeout(timeout);
    if (current === photoGeneration) {
      pendingPhoto = null;
      photoInput.disabled = false;
      photoButton.disabled = !photoInput.files?.length;
    }
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  if (!item.value.trim()) {
    item.setCustomValidity("Please describe an item.");
    item.reportValidity();
    return;
  }
  classify();
});
manualForm.addEventListener("submit", (event) => { event.preventDefault(); classify(true); });
photoButton.addEventListener("click", analyzePhoto);
photoInput.addEventListener("change", () => {
  document.querySelector("#photo-file-name").textContent = photoInput.files?.[0]?.name || "";
  photoGeneration += 1;
  pendingPhoto?.abort();
  pendingPhoto = null;
  photoButton.disabled = !photoInput.files?.length;
  photoResult.hidden = true;
  photoItems.replaceChildren();
});
selection.addEventListener("change", () => {
  updateCondition();
  if (pending) {
    generation += 1;
    pending.abort();
    pending = null;
    submit.disabled = manualSubmit.disabled = false;
    form.setAttribute("aria-busy", "false");
    category.textContent = "Confirm your updated choice";
    message.textContent = "Check the item type and condition, then confirm again.";
  }
});
item.addEventListener("input", () => {
  generation += 1;
  pending?.abort();
  pending = null;
  item.setCustomValidity("");
  result.hidden = true;
  manualForm.hidden = true;
  selection.replaceChildren();
  selection.value = "";
  selection.selectedIndex = -1;
  conditionLabel.hidden = true;
  question.textContent = "";
  contact.hidden = phone.hidden = true;
  contact.removeAttribute("href");
  phone.removeAttribute("href");
  document.querySelector("#continue-trip").hidden = true;
  document.querySelector("#add-another").hidden = true;
  submit.disabled = manualSubmit.disabled = false;
  form.setAttribute("aria-busy", "false");
});

function startAnotherItem(event) {
  event.preventDefault();
  item.value = "";
  item.dispatchEvent(new Event("input"));
  item.focus();
}
document.querySelector("#add-another").addEventListener("click", startAnotherItem);
document.querySelector("#basket-add-item").addEventListener("click", (event) => {
  event.preventDefault();
  document.querySelector("#waste-picker")?.focus();
});
