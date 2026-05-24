import type { SupabaseClient } from "@supabase/supabase-js";
import type { CameraBatteryDatabase } from "./database";

export interface InventorySnapshot {
  myCameraIds: string[];
  myBatteryIds: string[];
  updatedAt?: string | null;
}

export interface InventoryValidationResult {
  inventory: InventorySnapshot;
  warnings: string[];
}

interface UserInventoryRow {
  my_camera_ids: unknown;
  my_battery_ids: unknown;
  updated_at: string | null;
}

export function makeInventorySnapshot(myCameraIds: string[], myBatteryIds: string[], updatedAt?: string | null): InventorySnapshot {
  return {
    myCameraIds: dedupeIds(myCameraIds),
    myBatteryIds: dedupeIds(myBatteryIds),
    updatedAt: updatedAt ?? null,
  };
}

export function hasInventoryItems(inventory: InventorySnapshot): boolean {
  return inventory.myCameraIds.length > 0 || inventory.myBatteryIds.length > 0;
}

export function inventoriesEqual(left: InventorySnapshot, right: InventorySnapshot): boolean {
  return sameIdSet(left.myCameraIds, right.myCameraIds) && sameIdSet(left.myBatteryIds, right.myBatteryIds);
}

export function mergeInventorySnapshots(local: InventorySnapshot, cloud: InventorySnapshot): InventorySnapshot {
  return {
    myCameraIds: dedupeIds([...local.myCameraIds, ...cloud.myCameraIds]),
    myBatteryIds: dedupeIds([...local.myBatteryIds, ...cloud.myBatteryIds]),
    updatedAt: new Date().toISOString(),
  };
}

export function validateInventoryIds(inventory: InventorySnapshot, db: CameraBatteryDatabase, sourceLabel = "cloud"): InventoryValidationResult {
  const warnings: string[] = [];
  const myCameraIds = inventory.myCameraIds.filter((id) => {
    const exists = db.camerasById.has(id) || db.candidatesById.has(id);
    if (!exists) warnings.push(`${sourceLabel} camera id ignored because it is not in database: ${id}`);
    return exists;
  });
  const myBatteryIds = inventory.myBatteryIds.filter((id) => {
    const exists = db.batteriesById.has(id);
    if (!exists) warnings.push(`${sourceLabel} battery id ignored because it is not in database: ${id}`);
    return exists;
  });

  return {
    inventory: makeInventorySnapshot(myCameraIds, myBatteryIds, inventory.updatedAt),
    warnings,
  };
}

export function getInitialSyncStatus(options: { configured: boolean; userId: string | null; online: boolean }) {
  if (!options.configured || !options.userId) return "local_only" as const;
  if (!options.online) return "offline_saved_locally" as const;
  return "loading_cloud" as const;
}

export async function loadCloudInventory(client: SupabaseClient, userId: string): Promise<InventorySnapshot | null> {
  const { data, error } = await client
    .from("user_inventory")
    .select("my_camera_ids,my_battery_ids,updated_at")
    .eq("user_id", userId)
    .maybeSingle<UserInventoryRow>();

  if (error) {
    throw new Error(error.message);
  }

  if (!data) {
    return null;
  }

  return makeInventorySnapshot(readIdArray(data.my_camera_ids), readIdArray(data.my_battery_ids), data.updated_at);
}

export async function saveCloudInventory(client: SupabaseClient, userId: string, inventory: InventorySnapshot): Promise<InventorySnapshot> {
  const updatedAt = new Date().toISOString();
  const payload = {
    user_id: userId,
    my_camera_ids: dedupeIds(inventory.myCameraIds),
    my_battery_ids: dedupeIds(inventory.myBatteryIds),
    updated_at: updatedAt,
  };

  const { error } = await client.from("user_inventory").upsert(payload, { onConflict: "user_id" });
  if (error) {
    throw new Error(error.message);
  }

  return makeInventorySnapshot(payload.my_camera_ids, payload.my_battery_ids, updatedAt);
}

function readIdArray(value: unknown): string[] {
  return Array.isArray(value) ? dedupeIds(value.filter((item): item is string => typeof item === "string" && Boolean(item))) : [];
}

function dedupeIds(ids: string[]): string[] {
  return [...new Set(ids.filter(Boolean))];
}

function sameIdSet(left: string[], right: string[]): boolean {
  if (left.length !== right.length) return false;
  const rightSet = new Set(right);
  return left.every((id) => rightSet.has(id));
}
