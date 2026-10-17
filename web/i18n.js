/* Presentation-only localization. Canonical item IDs, inputs and app state stay stable. */
(function () {
  "use strict";
  const attributes = ["aria-label", "aria-description", "placeholder", "title", "alt"];
  const records = new WeakMap();
  let language = "en", catalog = {}, reverse = {}, patterns = [], observer, loaded = false;
  try { language = localStorage.getItem("goodsort-language") === "mk" ? "mk" : "en"; } catch {}
  const normalize = value => value.replace(/\s+/g, " ").trim();
  const escape = value => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  function translate(value, depth = 0) {
    if (language !== "mk" || !value || depth > 3) return value;
    const key = normalize(value);
    if (catalog[key]) return value.replace(key, catalog[key]) === value ? catalog[key] : value.replace(key, catalog[key]);
    for (const [pattern, target] of patterns) {
      const match = pattern.exec(key);
      if (match) return target.replace(/\{(\d+)\}/g, (_, n) => translate(match[Number(n) + 1], depth + 1));
    }
    return value;
  }
  function localize(node, property, value, write) {
    const saved = records.get(node) || {};
    const previous = saved[property];
    const original = previous && previous.rendered === value ? previous.original : (reverse[value] || value);
    const rendered = translate(original);
    saved[property] = { original, rendered };
    records.set(node, saved);
    if (rendered !== value) write(rendered);
  }
  function scan(root) {
    if (root.nodeType === Node.TEXT_NODE) {
      if (root.parentElement?.closest('script,style,textarea,[translate="no"],[data-no-i18n]')) return;
      localize(root, "text", root.nodeValue, value => { root.nodeValue = value; });
      return;
    }
    if (root.nodeType !== Node.ELEMENT_NODE && root.nodeType !== Node.DOCUMENT_NODE) return;
    if (root.nodeType === Node.ELEMENT_NODE) {
      if (root.matches('script,style,[translate="no"],[data-no-i18n]')) return;
      for (const name of attributes) if (root.hasAttribute(name)) {
        localize(root, name, root.getAttribute(name), value => root.setAttribute(name, value));
      }
      if (root.tagName === "TEXTAREA") return;
    }
    for (const child of root.childNodes) scan(child);
  }
  function refresh() {
    observer?.disconnect();
    document.documentElement.lang = language;
    scan(document.documentElement);
    document.querySelectorAll(".language-switch").forEach(select => { select.value = language; });
    observer?.observe(document.documentElement, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: attributes });
  }
  async function setLanguage(value) {
    if (!["en", "mk"].includes(value)) return;
    await ready;
    if (value === "mk" && !loaded) { refresh(); return; }
    language = value;
    document.querySelectorAll("input,select,textarea").forEach(control => control.setCustomValidity(""));
    try { localStorage.setItem("goodsort-language", language); } catch {}
    refresh();
    document.dispatchEvent(new CustomEvent("languagechange", { detail: { language } }));
  }
  const nativeFetch = window.fetch.bind(window);
  async function localizedFetch(input, options = {}) {
    const url = new URL(typeof input === "string" ? input : input.url, location.href);
    if (url.origin !== location.origin || !url.pathname.startsWith("/api/")) return nativeFetch(input, options);
    const headers = new Headers(options.headers || (input instanceof Request ? input.headers : undefined));
    headers.set("Accept-Language", language);
    return nativeFetch(input, { ...options, headers });
  }
  const ready = nativeFetch("/static/locales/mk.json", { cache: "no-cache" }).then(response => {
    if (!response.ok) throw new Error("Language catalog unavailable");
    return response.json();
  }).then(data => {
    catalog = data;
    loaded = true;
    reverse = Object.fromEntries(Object.entries(catalog).filter(([key]) => !/\{\d+\}/.test(key)).map(([key, value]) => [value, key]));
    patterns = Object.entries(catalog).filter(([key]) => /\{\d+\}/.test(key))
      .sort(([a], [b]) => b.replace(/\{\d+\}/g, "").length - a.replace(/\{\d+\}/g, "").length)
      .map(([key, target]) => {
      const parts = key.split(/\{\d+\}/);
      return [new RegExp("^" + parts.map(part => escape(part).replace(/ /g, "\\s*")).join("(.*?)") + "$"), target];
    });
  }).catch(() => {
    language = "en";
  });
  window.GoodsortI18n = { translate, setLanguage, fetch: localizedFetch, get language() { return language; },
    get locale() { return language === "mk" ? "mk-MK" : "en-GB"; },
    original(node) { return records.get(node)?.text?.original || node?.nodeValue || node?.textContent; }, ready };
  document.addEventListener("input", event => event.target.setCustomValidity?.(""));
  document.addEventListener("change", event => event.target.setCustomValidity?.(""));
  document.addEventListener("invalid", event => {
    const control = event.target;
    control.setCustomValidity("");
    if (language !== "mk") return;
    const validity = control.validity;
    control.setCustomValidity(validity.valueMissing ? "Пополнете го ова поле."
      : validity.tooShort ? `Внесете најмалку ${control.minLength} знаци.`
      : validity.tooLong ? `Внесете најмногу ${control.maxLength} знаци.`
      : validity.rangeUnderflow ? `Внесете вредност најмалку ${control.min}.`
      : validity.rangeOverflow ? `Внесете вредност најмногу ${control.max}.`
      : validity.patternMismatch ? translate(control.title) || "Проверете го форматот на внесот."
      : "Внесете валидна вредност.");
  }, true);
  document.addEventListener("DOMContentLoaded", async () => {
    await ready;
    if (!loaded) {
      const notice = document.createElement("p");
      notice.textContent = "Macedonian translations could not load. Reload to retry. / Преводот не се вчита. Превчитајте ја страницата.";
      notice.setAttribute("role", "alert");
      document.querySelector("main")?.prepend(notice);
    }
    const host = document.querySelector(".site-header") || document.querySelector("header") || document.querySelector("main");
    const select = document.createElement("select");
    select.className = "language-switch";
    select.setAttribute("aria-label", "Language");
    select.innerHTML = '<option value="en" lang="en" translate="no">English</option><option value="mk" lang="mk" translate="no">Македонски</option>';
    select.value = language;
    select.addEventListener("change", () => setLanguage(select.value));
    host?.append(select);
    observer = new MutationObserver(changes => {
      observer.disconnect();
      for (const change of changes) {
        if (change.type === "childList") change.addedNodes.forEach(scan);
        else scan(change.target);
      }
      observer.observe(document.documentElement, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: attributes });
    });
    refresh();
  });
})();
