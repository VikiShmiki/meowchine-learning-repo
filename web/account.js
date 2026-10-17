/* Optional account UI. Credentials and sessions never enter browser storage. */
(function () {
  "use strict";
  const { el } = CommunityUI;
  const names = { glass: "Glass", plastic_metal: "Plastic & cans", paper_tetrapak: "Paper & cartons", general: "General waste", electronics: "Electronics", clothes: "Clothes" };
  let state = { user: null }, generation = 0, busy = false, signup = false;
  let activePane = "overview", historyFilter = "all", displayedUser = null;
  const formatDate = timestamp => new Date(timestamp * 1000).toLocaleDateString(globalThis.GoodsortI18n?.locale || "en-GB", {day: "numeric", month: "short", year: "numeric"});
  const badgeArt = {
    first_dropoff: '<circle class="badge-base" cx="50" cy="48" r="36"/><circle class="badge-rim" cx="50" cy="48" r="30"/><g class="badge-symbol"><path class="badge-detail" d="M37 60C29 42 44 31 64 32c1 21-8 34-27 28Z M35 65l21-24"/></g>',
    ten_dropoffs: '<path class="badge-base" d="M50 8 85 28v40L50 88 15 68V28z"/><path class="badge-rim" d="m50 16 28 16v32L50 80 22 64V32z"/><g class="badge-symbol"><text x="50" y="48">10</text><path class="badge-detail" d="M43 66h14"/></g>',
    twentyfive_dropoffs: '<path class="badge-base" d="m50 5 13 10 16 1 5 16 11 13-8 15-1 16-17 6L55 94 41 84l-17-2-6-16L7 53l9-15 1-17 17-5z"/><circle class="badge-rim" cx="51" cy="49" r="29"/><g class="badge-symbol"><text x="51" y="49">25</text><path class="badge-detail" d="M44 67h14"/></g>',
    full_circle: '<circle class="badge-base" cx="50" cy="48" r="37"/><circle class="badge-rim" cx="50" cy="48" r="30"/><g class="badge-symbol"><path class="badge-detail" d="M33 41a18 18 0 0 1 33-4 M66 29v8h-8 M67 55a18 18 0 0 1-33 4 M34 67v-8h8"/></g>',
    second_life: '<path class="badge-base" d="M27 12h46l15 16v43L71 87H29L12 71V28z"/><path class="badge-rim" d="M30 20h40l10 11v36L68 79H32L20 67V31z"/><g class="badge-symbol"><path class="badge-detail" d="m41 33-13 8 6 10 7-4v20h18V47l7 4 6-10-13-8a9 9 0 0 1-18 0Z"/><path class="badge-detail" d="M50 59l-5-5a3 3 0 0 1 5-3 3 3 0 0 1 5 3Z"/></g>',
    tech_return: '<path class="badge-base" d="m50 7 34 13v29c0 23-19 34-34 43-15-9-34-20-34-43V20z"/><path class="badge-rim" d="m50 16 26 10v22c0 18-13 29-26 36-13-7-26-18-26-36V26z"/><g class="badge-symbol"><rect class="badge-detail" x="38" y="35" width="24" height="24" rx="5"/><path class="badge-detail" d="M44 29v6m12-6v6M44 59v6m12-6v6M32 41h6m-6 12h6m24-12h6m-6 12h6M49 41l-4 8h9l-4 6"/></g>',
  };
  const entry = el("button", "Sign in", "secondary account-entry");
  entry.type = "button"; entry.id = "account-entry"; entry.setAttribute("aria-haspopup", "dialog");
  document.querySelector(".site-header").append(entry);
  const dialog = el("dialog", "", "account-dialog"); dialog.id = "account-dialog";
  dialog.setAttribute("aria-labelledby", "account-heading");
  dialog.innerHTML = `<div class="account-heading"><h2 id="account-heading">Sign in</h2><button type="button" class="secondary icon-button" id="account-close" aria-label="Close account"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 6 12 12M18 6 6 18"/></svg></button></div>
    <div id="account-guest"><div class="account-tabs"><button type="button" id="account-login-tab" aria-pressed="true">Sign in</button><button type="button" id="account-register-tab" aria-pressed="false">Create account</button></div>
    <form id="account-form"><label for="account-username">Username</label><input id="account-username" name="username" autocomplete="username" autocapitalize="none" spellcheck="false" minlength="3" maxlength="24" pattern="[A-Za-z0-9_]{3,24}" title="3–24 letters, digits or underscores" required>
    <label for="account-password">Password</label><input id="account-password" name="password" type="password" autocomplete="current-password" minlength="15" maxlength="128" required>
    <p id="account-password-note" hidden>15+ characters. Use a unique password; this demo has no password recovery.</p><button type="submit" id="account-submit">Sign in</button></form>
    <p class="account-privacy">Optional. Save your drop-offs and badges. No email or location history.</p></div>
    <div id="account-member" hidden></div><p id="account-message" role="status"></p>`;
  document.body.append(dialog);
  const $ = id => document.getElementById(id);
  const form = $("account-form"), message = $("account-message");
  async function request(path, method = "GET", body) {
    const response = await (globalThis.GoodsortI18n?.fetch || fetch)("/api/v1/account" + path, { method, cache: "no-store", signal: AbortSignal.timeout(15000),
      headers: { "Content-Type": "application/json", "X-Goodsort-Action": "1" }, ...(body ? { body: JSON.stringify(body) } : {}) });
    const data = response.status === 204 ? {} : await response.json();
    if (!response.ok) throw new Error(data.detail || "Account unavailable. Please retry.");
    return data;
  }
  function medal(achievement) {
    const earned = achievement.earned_at !== null;
    const card = el("article", "", "account-badge"); card.dataset.earned = String(earned); card.dataset.badge = achievement.id;
    // Only local vector paths enter this markup; account/API text uses textContent.
    card.innerHTML = `<div class="badge-art"><svg viewBox="0 0 100 100" aria-hidden="true">${badgeArt[achievement.id] || badgeArt.first_dropoff}</svg><span class="badge-status" aria-hidden="true">${earned ? '<svg viewBox="0 0 24 24"><path d="m6 12 4 4 8-9"/></svg>' : '<svg viewBox="0 0 24 24"><rect x="6" y="10" width="12" height="10" rx="3"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/></svg>'}</span></div>`;
    card.append(el("h3", achievement.title), el("p", achievement.requirement, "badge-requirement"));
    const detail = el("details", "", "badge-details");
    detail.append(el("summary", earned ? "Earned" : `${achievement.progress} / ${achievement.target}`));
    detail.append(el("p", earned ? `Earned ${formatDate(achievement.earned_at)}` : achievement.requirement));
    card.append(detail);
    return card;
  }
  function materialChips(materials) {
    const chips = el("div", "", "account-materials");
    for (const material of materials) { const chip = el("span", names[material] || material); chip.dataset.material = material; chips.append(chip); }
    return chips;
  }
  function drawPanel(panel) {
    panel.replaceChildren(); panel.setAttribute("aria-labelledby", `activity-tab-${activePane}`);
    for (const tab of $("account-member").querySelectorAll('[role="tab"]')) {
      const selected = tab.dataset.pane === activePane;
      tab.setAttribute("aria-selected", String(selected)); tab.tabIndex = selected ? 0 : -1;
    }
    const achievements = state.achievements;
    if (activePane === "overview") {
      const next = achievements.slice(0, 3).find(a => a.earned_at === null) || achievements[2];
      const progress = el("section", "", "account-progress");
      const totals = el("div"); totals.append(el("p", "Recycling drop-offs"), el("strong", String(state.recycling_count), "account-total"));
      totals.append(el("span", `${achievements.filter(a => a.earned_at !== null).length} badges earned`, "account-earned-count"));
      const ring = el("div", "", "account-ring");
      ring.setAttribute("role", "progressbar"); ring.setAttribute("aria-label", `Progress to ${next.target} recycling drop-offs`);
      ring.setAttribute("aria-valuemin", "0"); ring.setAttribute("aria-valuemax", String(next.target)); ring.setAttribute("aria-valuenow", String(next.progress));
      ring.innerHTML = '<svg viewBox="0 0 120 120" aria-hidden="true"><circle class="ring-track" cx="60" cy="60" r="51"/><circle class="ring-value" cx="60" cy="60" r="51" pathLength="100"/></svg>';
      ring.style.setProperty("--ring-progress", String(next.progress / next.target * 100));
      const ringText = el("div"); ringText.append(el("strong", String(next.target)), el("span", next.earned_at !== null ? "Reached" : "Next milestone")); ring.append(ringText);
      progress.append(totals, ring);
      const heading = el("div", "", "activity-section-heading"); heading.append(el("h3", "Last four weeks"), el("span", "UTC"));
      const activity = el("section", "", "account-calendar"); activity.append(heading);
      const days = el("div", "", "activity-days");
      for (const day of state.activity.days) {
        const cell = el("span"); cell.dataset.level = String(Math.min(day.count, 3));
        const label = `${new Date(day.date * 1000).toLocaleDateString(globalThis.GoodsortI18n?.locale || "en-GB", {day: "numeric", month: "short", timeZone: "UTC"})}: ${day.count} recycling drop-offs`;
        cell.title = label; cell.setAttribute("role", "img"); cell.setAttribute("aria-label", label); days.append(cell);
      }
      const legend = el("div", "", "activity-legend"); legend.append(el("span", "No drop-offs"));
      for (let i = 0; i < 4; i++) { const swatch = el("i"); swatch.dataset.level = String(i); swatch.setAttribute("aria-hidden", "true"); legend.append(swatch); }
      legend.append(el("span", "3+")); activity.append(days, legend);
      panel.append(progress, activity);
      const collection = el("div", "", "activity-section-heading"); collection.append(el("h3", "Your materials"), el("span", `${Object.keys(state.activity.material_counts).length} / 5`)); panel.append(collection);
      const materials = materialChips(Object.keys(names).filter(m => m !== "general")); materials.classList.add("account-material-collection");
      for (const chip of materials.children) { const count = state.activity.material_counts[chip.dataset.material] || 0; chip.dataset.collected = String(count > 0); chip.title = `${count} drop-offs`; }
      panel.append(materials);
      const featured = el("div", "", "activity-section-heading"); featured.append(el("h3", "Milestones"));
      const all = el("button", "View all badges", "secondary"); all.type = "button";
      all.addEventListener("click", () => { activePane = "badges"; drawPanel(panel); $("activity-tab-badges").focus(); }); featured.append(all);
      const badges = el("div", "", "account-badges featured-badges");
      const last = [...achievements.slice(0, 3)].reverse().find(a => a.earned_at !== null);
      const picks = [...new Set([last || achievements[0], next])];
      if (picks.length === 1) picks.push(achievements.find(a => a.id !== picks[0].id && a.earned_at === null) || achievements[3]);
      badges.append(...picks.map(medal)); panel.append(featured, badges);
    } else if (activePane === "badges") {
      const heading = el("div", "", "activity-section-heading"); heading.append(el("h3", "Badge collection"), el("span", `${achievements.filter(a => a.earned_at !== null).length} / ${achievements.length} earned`));
      const gallery = el("div", "", "account-badges"); gallery.append(...achievements.map(medal)); panel.append(heading, gallery);
    } else {
      const header = el("div", "", "activity-section-heading"); header.append(el("h3", "Drop-off history"));
      const label = el("label", "Filter by material"); label.className = "visually-hidden"; label.htmlFor = "history-material";
      const filter = el("select"); filter.id = "history-material";
      for (const [value, name] of [["all", "All materials"], ...Object.entries(names)]) { const option = el("option", name); option.value = value; filter.append(option); }
      filter.value = historyFilter; filter.addEventListener("change", () => { historyFilter = filter.value; drawPanel(panel); $("history-material").focus(); });
      header.append(label, filter); panel.append(header);
      const rows = state.history.filter(item => historyFilter === "all" || item.materials.includes(historyFilter));
      if (!rows.length) { const empty = el("div", "", "account-empty"); empty.append(el("strong", state.history.length ? "No matching drop-offs" : "Your history starts here"), el("p", state.history.length ? "Try another material." : "Mark a stop as dropped off after your next route.")); panel.append(empty); }
      for (const item of rows) {
        const row = el("article", "", "account-history-row");
        const time = el("time", formatDate(item.created)); time.dateTime = new Date(item.created * 1000).toISOString();
        row.append(time, materialChips(item.materials)); panel.append(row);
      }
      if (state.history_count > state.history.length) panel.append(el("p", "Showing your latest 50 drop-offs. Material filters apply to these entries.", "account-privacy"));
    }
  }
  function render() {
    entry.textContent = state.user ? "My activity" : "Sign in";
    $("account-heading").setAttribute("translate", state.user ? "no" : "yes");
    $("account-heading").textContent = state.user ? state.user.username : signup ? "Create account" : "Sign in";
    $("account-guest").hidden = Boolean(state.user); $("account-member").hidden = !state.user;
    dialog.dataset.member = String(Boolean(state.user));
    if (displayedUser !== state.user?.id) { activePane = "overview"; historyFilter = "all"; displayedUser = state.user?.id; }
    const member = $("account-member"); member.replaceChildren();
    if (!state.user) return;
    const tabs = el("div", "", "activity-tabs"); tabs.setAttribute("role", "tablist"); tabs.setAttribute("aria-label", "My activity");
    const panel = el("div", "", "activity-panel"); panel.id = "activity-panel"; panel.setAttribute("role", "tabpanel"); panel.tabIndex = 0;
    for (const [key, title] of [["overview", "Overview"], ["badges", "Badges"], ["history", "History"]]) {
      const tab = el("button", title); tab.type = "button"; tab.id = `activity-tab-${key}`; tab.dataset.pane = key; tab.setAttribute("role", "tab"); tab.setAttribute("aria-controls", "activity-panel");
      tab.addEventListener("click", () => { activePane = key; drawPanel(panel); });
      tab.addEventListener("keydown", event => {
        const keys = ["overview", "badges", "history"], index = keys.indexOf(activePane);
        const next = event.key === "ArrowRight" ? (index + 1) % 3 : event.key === "ArrowLeft" ? (index + 2) % 3 : event.key === "Home" ? 0 : event.key === "End" ? 2 : -1;
        if (next < 0) return; event.preventDefault(); activePane = keys[next]; drawPanel(panel); $(`activity-tab-${activePane}`).focus();
      }); tabs.append(tab);
    }
    member.append(tabs, panel); drawPanel(panel);
    member.append(el("p", "Self-reported recycling & donations · General waste excluded from badges", "account-privacy"));
    const logout = el("button", "Sign out", "secondary account-signout"); logout.type = "button";
    logout.addEventListener("click", () => action(async () => { await request("/logout", "POST"); state = {user: null}; render(); message.textContent = "Signed out."; }));
    member.append(logout);
    const removal = el("details", "", "account-delete"); removal.append(el("summary", "Delete account"));
    const deletion = el("form");
    deletion.innerHTML = '<p>Permanently delete this account, drop-off history and badges.</p><label for="account-delete-password">Confirm password</label><input id="account-delete-password" type="password" autocomplete="current-password" minlength="15" maxlength="128" required><button type="submit" class="secondary">Delete account and history</button>';
    deletion.addEventListener("submit", event => {
      event.preventDefault(); const password = $("account-delete-password").value;
      action(async () => { await request("", "DELETE", {password}); state = {user: null}; render(); message.textContent = "Account and history deleted."; });
    });
    removal.append(deletion); member.append(removal);
  }
  async function refresh() {
    const current = ++generation;
    const data = await request("/me");
    if (current === generation) { state = data; render(); }
    return data;
  }
  async function action(work) {
    if (busy) return;
    busy = true; generation++; message.textContent = "";
    const controls = [...dialog.querySelectorAll("button:not(#account-close), input")];
    controls.forEach(control => { control.disabled = true; });
    try { await work(); }
    catch (error) { message.textContent = error instanceof TypeError ? "Connection failed. Your entries are kept; retry." : error.message; }
    finally { busy = false; controls.forEach(control => { control.disabled = false; }); }
  }
  function mode(register) {
    signup = register; message.textContent = "";
    $("account-login-tab").setAttribute("aria-pressed", String(!signup));
    $("account-register-tab").setAttribute("aria-pressed", String(signup));
    $("account-password-note").hidden = !signup;
    $("account-password").autocomplete = signup ? "new-password" : "current-password";
    $("account-submit").textContent = signup ? "Create account" : "Sign in";
    render();
  }
  $("account-login-tab").addEventListener("click", () => mode(false));
  $("account-register-tab").addEventListener("click", () => mode(true));
  form.addEventListener("submit", event => {
    event.preventDefault(); const username = form.elements.username.value, password = form.elements.password.value;
    action(async () => { state = await request(signup ? "/register" : "/login", "POST", {username, password}); form.reset(); render(); message.textContent = signup ? "Account created." : "Signed in."; });
  });
  entry.addEventListener("click", () => { dialog.showModal(); message.textContent = ""; action(refresh); });
  $("account-close").addEventListener("click", () => dialog.close());
  dialog.addEventListener("close", () => { form.elements.password.value = ""; if ($("account-delete-password")) $("account-delete-password").value = ""; entry.focus(); });
  document.addEventListener("languagechange", () => { if (state.user && $("activity-panel")) drawPanel($("activity-panel")); });
  document.addEventListener("visibilitychange", () => { if (!document.hidden && !busy) refresh().catch(() => {}); });
  globalThis.AccountUI = {
    async saveDropoff(ticket) {
      const fresh = await refresh();
      if (!ticket && !fresh.user) return false;
      if (!fresh.user) throw new Error("Sign in again to save this drop-off, or mark it without saving.");
      if (!ticket) throw new Error("Plan a new route while signed in to save drop-offs, or mark this one without saving.");
      const current = ++generation;
      const updated = await request("/dropoffs", "POST", {ticket});
      if (current === generation) { state = updated; render(); }
      return true;
    },
  };
  refresh().catch(() => {});
})();
