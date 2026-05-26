import type { CameraBatteryDatabase } from "./database";

export interface InventoryExport {
  version: 1;
  exportedAt: string;
  myCameraIds: string[];
  myBatteryIds: string[];
}

export interface InventoryImportResult {
  myCameraIds: string[];
  myBatteryIds: string[];
  warnings: string[];
}

export function exportInventory(myCameraIds: string[], myBatteryIds: string[]): InventoryExport {
  return {
    version: 1,
    exportedAt: new Date().toISOString(),
    myCameraIds: [...new Set(myCameraIds)],
    myBatteryIds: [...new Set(myBatteryIds)],
  };
}

export function parseInventoryImport(raw: string, db: CameraBatteryDatabase): InventoryImportResult {
  const warnings: string[] = [];
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    throw new Error("File nhập không phải JSON hợp lệ.");
  }

  if (!parsed || typeof parsed !== "object") {
    throw new Error("Dữ liệu nhập không đúng định dạng.");
  }

  const object = parsed as Partial<InventoryExport>;
  const rawCameraIds = Array.isArray(object.myCameraIds) ? object.myCameraIds : [];
  const rawBatteryIds = Array.isArray(object.myBatteryIds) ? object.myBatteryIds : [];

  const myCameraIds = rawCameraIds.filter((id): id is string => typeof id === "string" && Boolean(id));
  const myBatteryIds = rawBatteryIds.filter((id): id is string => typeof id === "string" && Boolean(id));

  const validCameraIds = myCameraIds.filter((id) => {
    const exists = db.camerasById.has(id) || db.candidatesById.has(id);
    if (!exists) warnings.push(`Mã máy ảnh không còn trong dữ liệu: ${id}`);
    return exists;
  });
  const validBatteryIds = myBatteryIds.filter((id) => {
    const exists = db.batteriesById.has(id);
    if (!exists) warnings.push(`Mã pin không còn trong dữ liệu: ${id}`);
    return exists;
  });

  return {
    myCameraIds: [...new Set(validCameraIds)],
    myBatteryIds: [...new Set(validBatteryIds)],
    warnings,
  };
}
