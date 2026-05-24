import { describe, expect, it } from "vitest";
import batteriesJson from "../../data/batteries.json";
import cameraCandidatesJson from "../../data/camera_candidates.json";
import camerasJson from "../../data/cameras.json";
import compatibilityJson from "../../data/compatibility.json";
import sourcesJson from "../../data/sources.json";
import unresolvedModelsJson from "../../data/unresolved_models.json";
import type { DataBundle } from "../types/database";
import {
  getInitialSyncStatus,
  loadCloudInventory,
  makeInventorySnapshot,
  mergeInventorySnapshots,
  saveCloudInventory,
  validateInventoryIds,
} from "./cloudInventory";
import { createDatabase } from "./database";

const db = createDatabase({
  cameras: camerasJson,
  batteries: batteriesJson,
  compatibility: compatibilityJson,
  cameraCandidates: cameraCandidatesJson,
  sources: sourcesJson,
  unresolvedModels: unresolvedModelsJson,
} as DataBundle);

describe("cloud inventory helpers", () => {
  it("merges local and cloud inventory by union without duplicates", () => {
    const merged = mergeInventorySnapshots(
      makeInventorySnapshot(["canon_powershot_g7_x_mark_iii"], ["canon_nb_13l"]),
      makeInventorySnapshot(["canon_powershot_g7_x_mark_iii", "fujifilm_finepix_f30"], ["canon_nb_13l"]),
    );

    expect(merged.myCameraIds).toEqual(["canon_powershot_g7_x_mark_iii", "fujifilm_finepix_f30"]);
    expect(merged.myBatteryIds).toEqual(["canon_nb_13l"]);
  });

  it("validates cloud inventory ids against local static database only", () => {
    const result = validateInventoryIds(
      makeInventorySnapshot(["canon_powershot_g7_x_mark_iii", "missing_camera"], ["canon_nb_13l", "missing_battery"]),
      db,
      "cloud",
    );

    expect(result.inventory.myCameraIds).toEqual(["canon_powershot_g7_x_mark_iii"]);
    expect(result.inventory.myBatteryIds).toEqual(["canon_nb_13l"]);
    expect(result.warnings).toHaveLength(2);
  });

  it("reports local-only mode when Supabase is not configured or user is absent", () => {
    expect(getInitialSyncStatus({ configured: false, userId: null, online: true })).toBe("local_only");
    expect(getInitialSyncStatus({ configured: true, userId: null, online: true })).toBe("local_only");
    expect(getInitialSyncStatus({ configured: true, userId: "user-1", online: false })).toBe("offline_saved_locally");
    expect(getInitialSyncStatus({ configured: true, userId: "user-1", online: true })).toBe("loading_cloud");
  });

  it("loads signed-in cloud inventory through a Supabase-like client", async () => {
    const client = {
      from: () => ({
        select: () => ({
          eq: () => ({
            maybeSingle: async () => ({
              data: {
                my_camera_ids: ["canon_powershot_g7_x_mark_iii"],
                my_battery_ids: ["canon_nb_13l"],
                updated_at: "2026-05-24T00:00:00Z",
              },
              error: null,
            }),
          }),
        }),
      }),
    };

    const cloud = await loadCloudInventory(client as never, "user-1");
    expect(cloud?.myCameraIds).toEqual(["canon_powershot_g7_x_mark_iii"]);
    expect(cloud?.myBatteryIds).toEqual(["canon_nb_13l"]);
  });

  it("does not mutate local data when cloud sync fails", async () => {
    const local = makeInventorySnapshot(["canon_powershot_g7_x_mark_iii"], ["canon_nb_13l"]);
    const before = structuredClone(local);
    const client = {
      from: () => ({
        upsert: async () => ({
          error: { message: "network unavailable" },
        }),
      }),
    };

    await expect(saveCloudInventory(client as never, "user-1", local)).rejects.toThrow("network unavailable");
    expect(local).toEqual(before);
  });
});
