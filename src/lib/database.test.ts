import { describe, expect, it } from "vitest";
import batteriesJson from "../../data/batteries.json";
import batterySuggestionsJson from "../../data/battery_suggestions.json";
import cameraCandidatesJson from "../../data/camera_candidates.json";
import camerasJson from "../../data/cameras.json";
import compatibilityJson from "../../data/compatibility.json";
import sourcesJson from "../../data/sources.json";
import unresolvedModelsJson from "../../data/unresolved_models.json";
import { readStoredIds, writeStoredIds } from "../hooks/useLocalStorageIds";
import type { Compatibility, DataBundle } from "../types/database";
import { createDatabase, loadDataBundle } from "./database";
import { exportInventory, parseInventoryImport } from "./inventory";

const bundle = {
  cameras: camerasJson,
  batteries: batteriesJson,
  compatibility: compatibilityJson,
  cameraCandidates: cameraCandidatesJson,
  sources: sourcesJson,
  unresolvedModels: unresolvedModelsJson,
  batterySuggestions: batterySuggestionsJson,
} as unknown as DataBundle;

const db = createDatabase(bundle);

describe("database loader, search, and source-backed lookup", () => {
  it("lazy-loads all seven JSON files through the loader", async () => {
    const requested: string[] = [];
    const loaded = await loadDataBundle({
      baseUrl: "/data",
      fetchJson: async <T,>(url: string) => {
        requested.push(url);
        const map: Record<string, unknown> = {
          "/data/cameras.json": bundle.cameras,
          "/data/batteries.json": bundle.batteries,
          "/data/compatibility.json": bundle.compatibility,
          "/data/camera_candidates.json": bundle.cameraCandidates,
          "/data/sources.json": bundle.sources,
          "/data/unresolved_models.json": bundle.unresolvedModels,
          "/data/battery_suggestions.json": bundle.batterySuggestions,
        };
        return map[url] as T;
      },
    });
    expect(requested).toHaveLength(7);
    expect(loaded.cameras).toHaveLength(bundle.cameras.length);
    expect(loaded.cameraCandidates).toHaveLength(bundle.cameraCandidates.length);
  });

  it("searches a verified camera with common shorthand", () => {
    const result = db.searchCamera("Canon G7X Mark III", 3);
    expect(result[0]?.id).toBe("canon_powershot_g7_x_mark_iii");
    const lookup = db.lookupFromMatch(result[0]);
    expect(lookup.kind).toBe("camera");
    if (lookup.kind === "camera") {
      expect(lookup.compatibility.length).toBeGreaterThan(0);
    }
  });

  it("searches Canon regional aliases for IXY/IXUS/ELPH compact forms", () => {
    const queries = [
      "canon ixy500",
      "canon ixy 500",
      "ixy500",
      "ixy digital 500",
      "ixus500",
      "digital ixus500",
      "powershot s500",
    ];
    for (const query of queries) {
      const result = db.searchAll(query, 5);
      expect(result[0]?.id, query).toBe("canon_powershot_s500_digital_elph");
    }
  });

  it("searches Sony DSC short aliases and keeps verified battery compatibility", () => {
    const queries = ["sony t700", "sony dsc t700", "dsc t700", "dsct700", "cyber shot t700"];
    for (const query of queries) {
      const result = db.searchAll(query, 5);
      expect(result[0]?.id, query).toBe("sony_cyber_shot_dsc_t700");
    }

    const lookup = db.lookupFromMatch(db.searchAll("sony t700", 1)[0]);
    expect(lookup.kind).toBe("camera");
    if (lookup.kind === "camera") {
      expect(lookup.compatibility.some((row) => row.battery_id === "sony_np_bd1")).toBe(true);
    }
  });

  it("searches researched Samsung regional alias and returns verified SLB-11A", () => {
    for (const query of ["Samsung WB1000", "Samsung TL320", "VLUU WB1000"]) {
      const result = db.searchAll(query, 5);
      expect(result[0]?.id, query).toBe("samsung_wb1000");
      const lookup = db.lookupFromMatch(result[0]);
      expect(lookup.kind, query).toBe("camera");
      if (lookup.kind === "camera") {
        expect(lookup.compatibility.some((row) => row.battery_id === "samsung_slb_11a"), query).toBe(true);
      }
    }
  });

  it("searches the corrected Panasonic TZ70 / ZS50 regional pair", () => {
    for (const query of ["Panasonic TZ70", "Panasonic ZS50"]) {
      const result = db.searchAll(query, 5);
      expect(result[0]?.id, query).toBe("panasonic_lumix_dmc_zs50");
      const lookup = db.lookupFromMatch(result[0]);
      expect(lookup.kind, query).toBe("camera");
      if (lookup.kind === "camera") {
        expect(lookup.compatibility.some((row) => row.battery_id === "panasonic_dmw_bcm13pp"), query).toBe(true);
      }
    }
  });

  it("searches common brand/model shorthand aliases across major brands", () => {
    const cases = [
      ["sony t900", "sony_cyber_shot_dsc_t900"],
      ["sony wx500", "sony_cyber_shot_dsc_wx500"],
      ["nikon p1000", "nikon_coolpix_p1000"],
      ["coolpix p1000", "nikon_coolpix_p1000"],
      ["panasonic tz90", "panasonic_lumix_dc_zs70"],
      ["panasonic zs70", "panasonic_lumix_dc_zs70"],
      ["fuji f30", "fujifilm_finepix_f30"],
      ["finepix f30", "fujifilm_finepix_f30"],
      ["olympus tg6", "olympus_tough_tg_6"],
      ["casio zr1000", "casio_exilim_ex_zr1000"],
    ] as const;

    for (const [query, expectedId] of cases) {
      const result = db.searchAll(query, 5);
      expect(result[0]?.id, query).toBe(expectedId);
    }
  });

  it("searches a battery with hyphenless input", () => {
    const result = db.searchBattery("NB13L", 3);
    expect(result[0]?.id).toBe("canon_nb_13l");
    expect(db.batteriesById.get(result[0].id)?.model).toBe("NB-13L");
  });

  it("searches an unresolved candidate without returning battery compatibility", () => {
    const result = db.searchAll("Kodak EasyShare C1013", 5);
    expect(result[0]?.type).toBe("unresolved_candidate");
    const lookup = db.lookupFromMatch(result[0]);
    expect(lookup.kind).toBe("unresolved");
    if (lookup.kind === "unresolved") {
      expect(db.getCameraBatteryCompatibility(lookup.candidate.camera_id)).toEqual([]);
      expect(db.buildNaturalAnswer(lookup)).toContain("chua co nguon xac minh pin");
    }
  });

  it("does not list unresolved cameras in battery compatibility results", () => {
    const compatibleCameras = db.getBatteryCompatibleCameras("canon_nb_13l");
    expect(compatibleCameras.some((row) => row.camera.camera_id === "kodak_easyshare_c1013")).toBe(false);
    expect(db.getMyCompatibleCameras("canon_nb_13l", ["kodak_easyshare_c1013"])).toEqual([]);
  });

  it("keeps weak battery suggestions separate from verified compatibility", () => {
    const suggestedDb = createDatabase({
      ...bundle,
      batterySuggestions: [
        {
          camera_id: "kodak_easyshare_c1013",
          display_name: "Kodak EasyShare C1013",
          brand: "Kodak",
          suggested_battery_model: "AA",
          suggested_battery_id: "generic_aa",
          evidence_type: "retailer_specification",
          source_name: "Test retailer source",
          source_url: "https://example.com/test-suggestion",
          source_text: "Kodak EasyShare C1013 battery suggestion: AA.",
          confidence: "low",
          warning: "Not verified official compatibility.",
          last_checked: "2026-05-25",
        },
      ],
    });
    const lookup = suggestedDb.lookupFromMatch(suggestedDb.searchAll("Kodak EasyShare C1013", 1)[0]);
    expect(lookup.kind).toBe("unresolved");
    if (lookup.kind === "unresolved") {
      expect(lookup.suggestions.some((row) => row.suggested_battery_model === "AA")).toBe(true);
      expect(suggestedDb.getCameraBatteryCompatibility(lookup.candidate.camera_id)).toEqual([]);
      expect(suggestedDb.buildNaturalAnswer(lookup)).toContain("goi y chua xac minh");
    }
    const aaSuggestions = suggestedDb.getBatterySuggestionsForBattery("generic_aa");
    expect(aaSuggestions.some((row) => row.camera_id === "kodak_easyshare_c1013")).toBe(true);
    expect(suggestedDb.getBatteryCompatibleCameras("generic_aa").some((row) => row.camera.camera_id === "kodak_easyshare_c1013")).toBe(false);
  });

  it("returns unknown for a model not in the database", () => {
    const lookup = db.resolveLookup("Definitely Not A Compact Camera 9999XYZ");
    expect(lookup.kind).toBe("unknown");
    expect(db.buildNaturalAnswer(lookup)).toContain("chua co du lieu");
  });

  it("groups duplicate compatibility sources by camera, battery, and status", () => {
    const rows: Compatibility[] = [
      {
        camera_id: "canon_ixus_245hs",
        battery_id: "canon_nb_11l",
        status: "fully_compatible",
        quantity_required: 1,
        note: "source one",
        source_name: "Source one",
        source_url: "https://example.com/one",
        source_type: "official_manual",
        confidence: "high",
        last_verified: "2026-05-24",
      },
      {
        camera_id: "canon_ixus_245hs",
        battery_id: "canon_nb_11l",
        status: "fully_compatible",
        quantity_required: 1,
        note: "source two",
        source_name: "Source two",
        source_url: "https://example.com/two",
        source_type: "trusted_database",
        confidence: "medium",
        last_verified: "2026-05-24",
      },
    ];
    const grouped = db.groupCompatibilityRows(rows);
    expect(grouped).toHaveLength(1);
    expect(grouped[0].sources).toHaveLength(2);
    expect(grouped[0].best_confidence).toBe("high");
  });

  it("compares my cameras and my batteries without inference", () => {
    const matches = db.getMyCompatibleBatteries("canon_powershot_g7_x_mark_iii", ["canon_nb_13l"]);
    expect(matches.some((row) => row.battery_id === "canon_nb_13l")).toBe(true);

    const noMatches = db.getMyCompatibleBatteries("fujifilm_finepix_f30", ["canon_nb_13l"]);
    expect(noMatches).toEqual([]);
  });

  it("exports and imports inventory with id validation warnings", () => {
    const exported = exportInventory(["canon_powershot_g7_x_mark_iii"], ["canon_nb_13l"]);
    const imported = parseInventoryImport(
      JSON.stringify({
        ...exported,
        myCameraIds: [...exported.myCameraIds, "missing_camera"],
        myBatteryIds: [...exported.myBatteryIds, "missing_battery"],
      }),
      db,
    );
    expect(imported.myCameraIds).toEqual(["canon_powershot_g7_x_mark_iii"]);
    expect(imported.myBatteryIds).toEqual(["canon_nb_13l"]);
    expect(imported.warnings).toHaveLength(2);
  });

  it("reads and writes localStorage id arrays", () => {
    const store = new Map<string, string>();
    (globalThis as unknown as { window: unknown }).window = {
      localStorage: {
        getItem: (key: string) => store.get(key) ?? null,
        setItem: (key: string, value: string) => store.set(key, value),
      },
    };
    writeStoredIds("test:ids", ["a", "a", "b"]);
    expect(readStoredIds("test:ids")).toEqual(["a", "b"]);
  });
});
