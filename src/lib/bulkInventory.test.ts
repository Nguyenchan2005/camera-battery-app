import { describe, expect, it } from "vitest";
import batteriesJson from "../../data/batteries.json";
import cameraCandidatesJson from "../../data/camera_candidates.json";
import camerasJson from "../../data/cameras.json";
import compatibilityJson from "../../data/compatibility.json";
import sourcesJson from "../../data/sources.json";
import unresolvedModelsJson from "../../data/unresolved_models.json";
import type { DataBundle } from "../types/database";
import { analyzeBulkInventoryInput, parseBulkInventoryLines } from "./bulkInventory";
import { createDatabase } from "./database";

const db = createDatabase({
  cameras: camerasJson,
  batteries: batteriesJson,
  compatibility: compatibilityJson,
  cameraCandidates: cameraCandidatesJson,
  sources: sourcesJson,
  unresolvedModels: unresolvedModelsJson,
} as DataBundle);

describe("bulk inventory paste analysis", () => {
  it("normalizes pasted lines with bullets and numbering", () => {
    expect(parseBulkInventoryLines("1. Canon G7X Mark III\n- NB13L\n\n* Kodak EasyShare M753")).toEqual([
      "Canon G7X Mark III",
      "NB13L",
      "Kodak EasyShare M753",
    ]);
  });

  it("auto-matches only unique exact camera, battery, and unresolved candidate lines", () => {
    const result = analyzeBulkInventoryInput("Canon G7X Mark III\nNB13L\nKodak EasyShare M753", db);
    expect(result.autoMatches.map((row) => `${row.match.type}:${row.match.id}`)).toEqual([
      "camera:canon_powershot_g7_x_mark_iii",
      "battery:canon_nb_13l",
      "unresolved_candidate:kodak_easyshare_m753",
    ]);
    expect(result.ambiguousMatches).toEqual([]);
    expect(result.notFound).toEqual([]);
  });

  it("keeps fuzzy-only matches for manual review instead of auto-adding", () => {
    const fakeDb = {
      searchAll: () => [
        {
          type: "camera",
          id: "canon_powershot_g7_x_mark_iii",
          label: "Canon PowerShot G7 X Mark III",
          subtitle: "Canon / PowerShot G / 2019",
          score: 0.12,
          exact: false,
          matchReason: "fuzzy match",
        },
      ],
    } as unknown as typeof db;
    const result = analyzeBulkInventoryInput("Canon G7X-ish", fakeDb);
    expect(result.autoMatches).toEqual([]);
    expect(result.ambiguousMatches).toHaveLength(1);
    expect(result.ambiguousMatches[0].options.length).toBeGreaterThan(0);
  });

  it("reports unknown lines without creating inventory ids", () => {
    const result = analyzeBulkInventoryInput("Definitely Missing Camera 9999XYZ", db);
    expect(result.autoMatches).toEqual([]);
    expect(result.ambiguousMatches).toEqual([]);
    expect(result.notFound).toEqual([
      {
        line: "Definitely Missing Camera 9999XYZ",
        reason: "No database match.",
      },
    ]);
  });
});
