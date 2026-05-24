import { describe, expect, it } from "vitest";
import batteriesJson from "../../data/batteries.json";
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
} as DataBundle;

const db = createDatabase(bundle);

describe("database loader, search, and source-backed lookup", () => {
  it("lazy-loads all six JSON files through the loader", async () => {
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
        };
        return map[url] as T;
      },
    });
    expect(requested).toHaveLength(6);
    expect(loaded.cameras).toHaveLength(463);
    expect(loaded.cameraCandidates).toHaveLength(1823);
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

  it("searches a battery with hyphenless input", () => {
    const result = db.searchBattery("NB13L", 3);
    expect(result[0]?.id).toBe("canon_nb_13l");
    expect(db.batteriesById.get(result[0].id)?.model).toBe("NB-13L");
  });

  it("searches an unresolved candidate without returning battery compatibility", () => {
    const result = db.searchAll("Fujifilm FinePix F30", 5);
    expect(result[0]?.type).toBe("unresolved_candidate");
    const lookup = db.lookupFromMatch(result[0]);
    expect(lookup.kind).toBe("unresolved");
    if (lookup.kind === "unresolved") {
      expect(db.getCameraBatteryCompatibility(lookup.candidate.camera_id)).toEqual([]);
      expect(db.buildNaturalAnswer(lookup)).toContain("chua co nguon xac minh pin");
    }
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
