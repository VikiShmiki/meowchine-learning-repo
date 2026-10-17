// Controller tests with a minimal DOM double; these do not replace browser/device QA.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const test = require("node:test");

function harness() {
  const elements = new Map();
  let created = 0;
  function element(id) {
    if (!elements.has(id)) elements.set(id, {
      value: "a jar", hidden: false, disabled: false, checked: false,
      textContent: "", listeners: {}, options: [], children: [],
      addEventListener(name, listener) { this.listeners[name] = listener; },
      querySelector() { return element(`${id}-button`); },
      setAttribute(name, value) { this[name] = value; },
      removeAttribute(name) { delete this[name]; },
      replaceChildren() { this.options = []; this.children = []; },
      add(option) { this.options.push(option); },
      append(...children) { this.children.push(...children); },
      dispatchEvent(event) { this.listeners[event.type]?.(event); },
      focus() { this.focused = true; },
      scrollIntoView() {},
      setCustomValidity(value) { this.validity = value; },
      reportValidity() {},
    });
    return elements.get(id);
  }
  const requests = [];
  const context = vm.createContext({
    document: { querySelector: element, createElement: () => element(`created-${created++}`) },
    AbortController,
    Option: function (label, id) { this.label = label; this.id = id; },
    setTimeout: () => 1, clearTimeout: () => {},
    fetch: (url, options) => new Promise((resolve, reject) => {
      requests.push({ url, options, resolve, reject });
    }),
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname, "../web/app.js"), "utf8"), context);
  return { element, requests, run: (source) => vm.runInContext(source, context) };
}

const answer = {
  category: "glass", status: "confirm_condition", message: "Confirm the condition",
  clarification_question: "Is it empty?", item_kind: "empty_glass_packaging",
  choices: [{ id: "empty_glass_packaging", label: "Empty glass bottle or jar" }],
};
for (const [kind, category, title, confirmation] of [
  ["ordinary_residual", "general", "General waste", "Used household tissues or nappies"],
  ["electronics", "special_unsupported", "Electronics", "Household device only"],
  ["small_electronics", "special_unsupported", "Small electronics", "Phone, charger, cable or earbuds only"],
  ["wearable_clothes", "special_unsupported", "Clothes · donation", "Clothes are clean, washed and wearable"],
]) {
  test(`${kind} has a routable, item-specific confirmation`, async () => {
    const h = harness();
    const reply = { ...answer, category, item_kind: kind,
      message: "Correct disposal stream", choices: [{ id: kind, label: title }] };
    h.run(`render(${JSON.stringify(reply)})`);
    assert.equal(h.element("#category").textContent, title);
    assert.ok(h.element("#condition-label").textContent.startsWith(confirmation));
    assert.equal(h.element("#manual-form-button").textContent, "Confirm & add to trip");
    if (["electronics", "small_electronics"].includes(kind)) {
      assert.equal(h.element("#contact").textContent, "Request home pickup · Nula Otpad");
    }
    const pending = h.run("classify(true)");
    const body = JSON.parse(h.requests[0].options.body);
    assert.equal(body.manual_kind, kind);
    assert.equal(body.condition_confirmed, true);
    resolve(h.requests[0], { ...reply, status: "ready_for_site_matching", choices: [] });
    await pending;
  });
}
function resolve(request, body = answer) {
  request.resolve({ ok: true, json: async () => body });
}

test("manual recovery sends explicit item and condition, not coordinates", async () => {
  const h = harness();
  const initial = h.run("classify()");
  resolve(h.requests[0]);
  await initial;
  assert.equal(h.element("#manual-form").hidden, false);
  assert.equal(h.element("#condition-label").hidden, false);
  assert.equal(h.element("#manual-form-button").textContent, "Confirm & add to trip");
  const manual = h.run("classify(true)");
  assert.deepEqual(JSON.parse(h.requests[1].options.body), {
    text: "a jar", manual_kind: "empty_glass_packaging", condition_confirmed: true,
  });
  resolve(h.requests[1], { ...answer, choices: [], status: "ready_for_site_matching" });
  await manual;
  assert.equal(h.element("#manual-form").hidden, true);
});

test("editing input cancels pending work and ignores its late response", async () => {
  const h = harness();
  const old = h.run("classify()");
  h.element("#item").listeners.input();
  assert.equal(h.requests[0].options.signal.aborted, true);
  const fresh = h.run("classify()");
  resolve(h.requests[1], { ...answer, status: "clarify", message: "Fresh result" });
  await fresh;
  resolve(h.requests[0], { ...answer, status: "clarify", message: "Stale result" });
  await old;
  assert.equal(h.element("#message").textContent, "Fresh result");
  assert.equal(h.element("#classify-form-button").disabled, false);
});

test("changing a manual choice invalidates a pending confirmation", async () => {
  const h = harness();
  const pending = h.run("classify(true)");
  h.element("#item-kind").value = "batteries";
  h.element("#item-kind").listeners.change();
  resolve(h.requests[0]);
  await pending;
  assert.equal(h.element("#category").textContent, "Confirm your updated choice");
  assert.equal(h.element("#condition-label").hidden, true);
  assert.equal(h.element("#manual-form-button").textContent, "Show disposal guidance");
});

for (const failure of [new Error("offline"), Object.assign(new Error(), { name: "AbortError" })]) {
  test(`failure restores controls: ${failure.name}`, async () => {
    const h = harness();
    const pending = h.run("classify()");
    h.requests[0].reject(failure);
    await pending;
    assert.equal(h.element("#classify-form-button").disabled, false);
    assert.equal(h.element("#manual-form").hidden, true);
    assert.equal(h.element("#classify-form")["aria-busy"], "false");
    assert.match(h.element("#message").textContent, /try again/);
  });
}

test("operator contact is removed when the next item has no specialist evidence", () => {
  const h = harness();
  h.run(`render(${JSON.stringify({ ...answer, choices: [], contact_url: "https://example.org", phone: "123" })})`);
  assert.equal(h.element("#contact").hidden, false);
  h.run(`render(${JSON.stringify(answer)})`);
  assert.equal(h.element("#contact").hidden, true);
  assert.equal(h.element("#contact").href, undefined);
  assert.equal(h.element("#phone").href, undefined);
});

test("learned broad category is visibly marked as a suggestion", () => {
  const h = harness();
  h.run(`render(${JSON.stringify({
    ...answer,
    category: null,
    suggested_category: "paper_tetrapak",
    status: "clarify",
    message: "Choose the exact item type.",
  })})`);
  assert.equal(h.element("#category").textContent, "Suggested: Paper / cardboard / Tetra Pak");
});

test("photo analysis sends the raw image and renders reviewable suggestions", async () => {
  const h = harness();
  const photo = { type: "image/png", size: 1024 };
  h.element("#item-photo").files = [photo];
  const pending = h.run("analyzePhoto()");
  assert.equal(h.requests[0].url, "/api/v1/photo-suggestions");
  assert.equal(h.requests[0].options.headers["Content-Type"], "image/png");
  assert.equal(h.requests[0].options.body, photo);
  resolve(h.requests[0], {
    items: [{
      description: "clear glass jar", item_kind: "empty_glass_packaging",
      category: "glass", status: "candidate", reason: "Visible glass packaging.",
    }],
    message: "Review every suggestion.",
  });
  await pending;
  assert.equal(h.element("#photo-status").textContent, "Review every suggestion.");
  assert.equal(h.element("#photo-items").children.length, 1);
  assert.equal(h.element("#photo-items").children[0].children[0].textContent, "clear glass jar");
  assert.equal(h.element("#analyze-photo").disabled, false);
});
