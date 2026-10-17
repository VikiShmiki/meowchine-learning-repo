const assert = require("node:assert/strict");
const test = require("node:test");
const { coordinates, validate, discover, markerRadius, materialColors, stopAppearance } = require("../web/site-data.js");
const site = (id, latitude, material = "glass") => ({ id, latitude, longitude: 21.4,
  materials: [material], assets: [{ id: id + "-asset", name: "A jar site", address: null,
    municipality_name: "Centar", source_materials: ["glass"], qa_flags: [],
    acceptance: null, provenance: { source_url: "https://example.org" } }] });
const snapshot = { schema_version: 1, scope: "city", synthetic: false,
  categories_are_discovery_only: true, as_of_date: "2026-09-19", dataset_version: "test",
  site_count: 2, asset_count: 2, sites: [site("far", 42.1), site("near", 42)] };

test("invalid, duplicate, synthetic and wrong-scope snapshots are rejected", () => {
  assert.equal(validate(snapshot), snapshot);
  for (const change of [{ synthetic: true }, { scope: "metro_extension" },
    { sites: [site("same", 42), site("same", 42)] },
    { sites: [site("invalid", 91), site("valid", 42)] }]) {
    assert.throws(() => validate({ ...snapshot, ...change }));
  }
});
test("origin coordinates reject strings and nonfinite/out-of-range numbers", () => {
  assert.equal(coordinates(42, 21), true);
  for (const value of [NaN, Infinity, 91, "42"]) assert.equal(coordinates(value, 21), false);
});
test("discovery filters and distances never imply item acceptance", () => {
  const results = discover(snapshot.sites, "glass", "centar", { latitude: 42, longitude: 21.4 });
  assert.deepEqual(results.map((row) => row.site.id), ["near", "far"]);
  assert.equal(results[0].distance, 0);
  assert.equal(results[0].site.assets[0].acceptance, null);
  assert.equal(discover(snapshot.sites, "special_unsupported", "", null).length, 0);
  assert.equal(discover(snapshot.sites, "all", "missing", null).length, 0);
});

test("individual dots stay small in overview and selection stays prominent at every zoom", () => {
  assert.deepEqual([12, 14, 16, 17, 19].map((zoom) => markerRadius(zoom)), [2.5, 3.5, 5, 6, 6]);
  for (let zoom = 0; zoom <= 19; zoom++) {
    assert.ok(markerRadius(zoom) > 0);
    assert.ok(markerRadius(zoom, true) > markerRadius(zoom));
  }
});

test("Cyrillic and Latin municipality searches return the same recorded sites", () => {
  for (const [source, query] of [["Karposh", "Карпош"], ["Čair", "Чаир"], ["Gjorche Petrov", "Ѓорче Петров"]]) {
    const record = site("recorded", 42);
    record.assets[0].municipality_name = source;
    assert.deepEqual(discover([record], "all", query, null).map(row => row.site.id), ["recorded"]);
    assert.equal(record.assets[0].municipality_name, source);
  }
});

test("stop colors come from assigned drop-offs, including exact item kinds", () => {
  for (const [kind, material] of Object.entries({ glass: "glass", empty_glass_packaging: "glass",
    plastic_metal: "plastic_metal", empty_plastic_bottle: "plastic_metal", empty_metal_can: "plastic_metal",
    paper_tetrapak: "paper_tetrapak", clean_paper: "paper_tetrapak", clean_cardboard: "paper_tetrapak",
    empty_tetrapak: "paper_tetrapak", general: "general",
    ordinary_residual: "general", electronics: "special_unsupported", wearable_clothes: "clothes" })) {
    const appearance = stopAppearance([kind]);
    assert.deepEqual(appearance.materials, [material]);
    assert.equal(appearance.background, materialColors[material]);
  }
  assert.deepEqual(stopAppearance(["empty_metal_can", "empty_plastic_bottle"]).materials, ["plastic_metal"]);
});

test("multi-stream stops retain each real material color without a mixed category", () => {
  const appearance = stopAppearance(["general", "empty_glass_packaging", "glass"]);
  assert.deepEqual(appearance.materials, ["glass", "general"]);
  assert.match(appearance.background, /conic-gradient/);
  assert.ok(appearance.background.includes(materialColors.glass));
  assert.ok(appearance.background.includes(materialColors.general));
  assert.equal(appearance.color, "#263c30");
  assert.equal(materialColors.mixed, undefined);
  assert.deepEqual(stopAppearance(["unknown"]).materials, []);
});
