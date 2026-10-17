/* Pure snapshot/discovery helpers. Broad material filters never establish acceptance. */
(function (root) {
  "use strict";
  const materials = ["glass", "plastic_metal", "paper_tetrapak", "general", "special_unsupported", "clothes"];
  const materialColors = { glass: "#9a7317", plastic_metal: "#36734e", paper_tetrapak: "#5265a6", general: "#66736c", special_unsupported: "#366d80", clothes: "#95617b" };
  const materialNames = { glass: "Glass", plastic_metal: "Plastic / metal", paper_tetrapak: "Paper / cartons", general: "General waste", special_unsupported: "Electronics", clothes: "Clothes · donation" };
  const kindMaterials = { empty_glass_packaging: "glass", empty_plastic_bottle: "plastic_metal",
    empty_metal_can: "plastic_metal", clean_paper: "paper_tetrapak", clean_cardboard: "paper_tetrapak", empty_tetrapak: "paper_tetrapak",
    ordinary_residual: "general", electronics: "special_unsupported", small_electronics: "special_unsupported", wearable_clothes: "clothes" };
  function stopAppearance(itemKinds) {
    const assigned = new Set(itemKinds.map((kind) => kindMaterials[kind] || kind));
    const selected = Object.keys(materialColors).filter((material) => assigned.has(material));
    const colors = selected.map((material) => materialColors[material]);
    // A multi-stream stop uses its real colors, never a fictional "mixed" category.
    const background = colors.length > 1
      ? `radial-gradient(circle, #fffefa 0 46%, transparent 49%), conic-gradient(${colors.map((color, i) => `${color} ${i * 100 / colors.length}% ${(i + 1) * 100 / colors.length}%`).join(", ")})`
      : colors[0] || "#66736c";
    return { materials: selected, background, color: colors.length > 1 ? "#263c30" : "#fff",
      label: selected.map((material) => materialNames[material]).join(" / ") || "Drop-off" };
  }
  function coordinates(latitude, longitude) {
    return typeof latitude === "number" && Number.isFinite(latitude) && Math.abs(latitude) <= 90
      && typeof longitude === "number" && Number.isFinite(longitude) && Math.abs(longitude) <= 180;
  }
  function validate(snapshot) {
    if (!snapshot || snapshot.schema_version !== 1 || !["city", "citizen"].includes(snapshot.scope)
      || snapshot.synthetic !== false || snapshot.categories_are_discovery_only !== true
      || typeof snapshot.as_of_date !== "string" || typeof snapshot.dataset_version !== "string"
      || !Number.isInteger(snapshot.asset_count) || snapshot.asset_count < 0
      || !Array.isArray(snapshot.sites) || snapshot.site_count !== snapshot.sites.length) {
      throw new Error("Unsupported site snapshot");
    }
    const ids = new Set();
    for (const site of snapshot.sites) {
      if (!site || typeof site.id !== "string" || ids.has(site.id)
        || !coordinates(site.latitude, site.longitude) || !Array.isArray(site.materials)
        || !site.materials.every((m) => materials.includes(m))
        || !Array.isArray(site.assets) || !site.assets.length) throw new Error("Invalid site");
      ids.add(site.id);
      for (const asset of site.assets) {
        if (!asset || typeof asset.id !== "string" || typeof asset.name !== "string"
          || !Array.isArray(asset.source_materials) || !Array.isArray(asset.qa_flags)
          || !asset.provenance || typeof asset.provenance.source_url !== "string"
          || (asset.acceptance !== null && (!asset.acceptance
            || !Array.isArray(asset.acceptance.accepted_item_kinds)
            || typeof asset.acceptance.limits !== "string"))) throw new Error("Invalid asset");
      }
    }
    return snapshot;
  }
  function distance(origin, site) {
    const rad = Math.PI / 180;
    const a = Math.sin((site.latitude - origin.latitude) * rad / 2) ** 2
      + Math.cos(origin.latitude * rad) * Math.cos(site.latitude * rad)
      * Math.sin((site.longitude - origin.longitude) * rad / 2) ** 2;
    return 6371000 * 2 * Math.asin(Math.sqrt(Math.min(1, a)));
  }
  function searchKey(text) {
    const letters = {а:"a",б:"b",в:"v",г:"g",д:"d",ѓ:"gj",е:"e",ж:"z",з:"z",ѕ:"dz",и:"i",ј:"j",к:"k",л:"l",љ:"lj",м:"m",н:"n",њ:"nj",о:"o",п:"p",р:"r",с:"s",т:"t",ќ:"k",у:"u",ф:"f",х:"h",ц:"c",ч:"c",џ:"dz",ш:"s"};
    return [...text.toLowerCase().normalize("NFC")].map(c => letters[c] || c).join("")
      .normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/sh/g, "s").replace(/ch/g, "c").replace(/zh/g, "z");
  }
  function discover(sites, material, query, origin) {
    const needle = searchKey(query.trim());
    return sites.filter((site) => (material === "all" || site.materials.includes(material))
      && (!needle || site.assets.some((asset) =>
        searchKey([asset.name, asset.address, asset.municipality_name].join(" ")).includes(needle))))
      .map((site) => ({ site, distance: origin ? distance(origin, site) : null }))
      .sort((a, b) => origin ? a.distance - b.distance || a.site.id.localeCompare(b.site.id)
        : a.site.id.localeCompare(b.site.id));
  }
  // Scale the symbol, never merge or move the underlying site.
  function markerRadius(zoom, selected = false) {
    return selected ? 9 : zoom < 14 ? 2.5 : zoom < 16 ? 3.5 : zoom < 17 ? 5 : 6;
  }
  const api = { coordinates, validate, distance, discover, markerRadius, materialColors, stopAppearance };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.SiteData = api;
})(globalThis);
