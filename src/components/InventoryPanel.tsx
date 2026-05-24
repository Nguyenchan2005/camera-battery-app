import { useMemo, useRef, useState } from "react";
import type React from "react";
import type { CameraBatteryDatabase } from "../lib/database";
import { exportInventory, parseInventoryImport } from "../lib/inventory";
import { Badge } from "./Badge";

export function InventoryPanel({
  db,
  myCameraIds,
  myBatteryIds,
  addCamera,
  replaceCameras,
  removeCamera,
  clearCameras,
  addBattery,
  replaceBatteries,
  removeBattery,
  clearBatteries,
}: {
  db: CameraBatteryDatabase;
  myCameraIds: string[];
  myBatteryIds: string[];
  addCamera: (id: string) => void;
  replaceCameras: (ids: string[]) => void;
  removeCamera: (id: string) => void;
  clearCameras: () => void;
  addBattery: (id: string) => void;
  replaceBatteries: (ids: string[]) => void;
  removeBattery: (id: string) => void;
  clearBatteries: () => void;
}) {
  const [cameraQuery, setCameraQuery] = useState("");
  const [batteryQuery, setBatteryQuery] = useState("");
  const [importWarnings, setImportWarnings] = useState<string[]>([]);
  const importRef = useRef<HTMLInputElement | null>(null);

  const cameraSuggestions = useMemo(
    () => db.searchAll(cameraQuery, 6).filter((match) => match.type === "camera" || match.type === "unresolved_candidate"),
    [cameraQuery, db],
  );
  const batterySuggestions = useMemo(() => db.searchBattery(batteryQuery, 6), [batteryQuery, db]);

  const coveredCameraIds = myCameraIds.filter((cameraId) => db.getMyCompatibleBatteries(cameraId, myBatteryIds).length > 0);
  const uncoveredCameraIds = myCameraIds.filter((cameraId) => !db.getMyCompatibleBatteries(cameraId, myBatteryIds).length);
  const unusedBatteryIds = myBatteryIds.filter((batteryId) => db.getMyCompatibleCameras(batteryId, myCameraIds).length === 0);

  function handleExport() {
    const payload = exportInventory(myCameraIds, myBatteryIds);
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `camera-battery-inventory-${new Date().toISOString().slice(0, 10)}.json`;
    link.click();
    URL.revokeObjectURL(url);
  }

  async function handleImport(file: File | undefined) {
    if (!file) return;
    const text = await file.text();
    const result = parseInventoryImport(text, db);
    replaceCameras(result.myCameraIds);
    replaceBatteries(result.myBatteryIds);
    setImportWarnings(result.warnings);
    if (importRef.current) importRef.current.value = "";
  }

  return (
    <section data-testid="inventory-panel" className="rounded-lg border border-slate-200 bg-white p-5 shadow-soft">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-950">Kho cua toi</h2>
          <p className="text-sm text-slate-500">Luu tren trinh duyet bang localStorage.</p>
        </div>
        <div className="grid grid-cols-2 gap-2 text-center text-sm sm:grid-cols-4">
          <Stat label="May" value={myCameraIds.length} testId="inventory-camera-count" />
          <Stat label="Pin" value={myBatteryIds.length} testId="inventory-battery-count" />
          <Stat label="Da khop" value={coveredCameraIds.length} testId="inventory-covered-count" />
          <Stat label="Chua khop" value={uncoveredCameraIds.length} testId="inventory-uncovered-count" />
        </div>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <button data-testid="inventory-export" className="rounded-md border border-slate-300 px-3 py-2 text-sm font-medium hover:bg-slate-50" type="button" onClick={handleExport}>
          Export kho JSON
        </button>
        <button
          data-testid="inventory-import-button"
          className="rounded-md border border-slate-300 px-3 py-2 text-sm font-medium hover:bg-slate-50"
          type="button"
          onClick={() => importRef.current?.click()}
        >
          Import kho JSON
        </button>
        <input
          ref={importRef}
          data-testid="inventory-import-input"
          className="hidden"
          type="file"
          accept="application/json,.json"
          onChange={(event) => {
            handleImport(event.target.files?.[0]).catch((error: Error) => setImportWarnings([error.message]));
          }}
        />
      </div>
      {importWarnings.length ? (
        <div data-testid="inventory-import-warnings" className="mt-3 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
          {importWarnings.map((warning) => (
            <div key={warning}>{warning}</div>
          ))}
        </div>
      ) : null}

      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <div>
          <div className="flex items-center justify-between gap-3">
            <h3 className="font-semibold text-slate-900">May anh</h3>
            <button data-testid="clear-cameras" className="text-xs font-medium text-slate-500 hover:text-rose-700" type="button" onClick={clearCameras}>
              Clear
            </button>
          </div>
          <Picker
            testIdPrefix="inventory-camera"
            placeholder="Them may anh..."
            query={cameraQuery}
            setQuery={setCameraQuery}
            suggestions={cameraSuggestions.map((match) => ({
              id: match.id,
              label: match.label,
              subtitle: `${match.subtitle} / ${match.matchReason}`,
              tag: match.type === "camera" ? "verified" : "unresolved",
            }))}
            onAdd={(id) => {
              addCamera(id);
              setCameraQuery("");
            }}
          />
          <div className="mt-3 space-y-2">
            {myCameraIds.length ? (
              myCameraIds.map((cameraId) => {
                const camera = db.camerasById.get(cameraId);
                const candidate = db.candidatesById.get(cameraId);
                const status = db.getCandidateStatus(cameraId);
                const label = camera?.display_name ?? candidate?.display_name ?? cameraId;
                const matches = camera ? db.getMyCompatibleBatteries(cameraId, myBatteryIds) : [];
                return (
                  <InventoryRow key={cameraId} testId={`inventory-camera-${cameraId}`} label={label} onRemove={() => removeCamera(cameraId)}>
                    <Badge tone={status.status === "verified" ? "green" : status.status === "unresolved" ? "gray" : "red"}>{status.status}</Badge>
                    {matches.length ? <Badge tone="green">co pin trong kho</Badge> : <Badge tone="gray">chua co pin khop</Badge>}
                  </InventoryRow>
                );
              })
            ) : (
              <Empty text="Chua co may anh trong kho." />
            )}
          </div>
        </div>

        <div>
          <div className="flex items-center justify-between gap-3">
            <h3 className="font-semibold text-slate-900">Pin</h3>
            <button data-testid="clear-batteries" className="text-xs font-medium text-slate-500 hover:text-rose-700" type="button" onClick={clearBatteries}>
              Clear
            </button>
          </div>
          <Picker
            testIdPrefix="inventory-battery"
            placeholder="Them pin..."
            query={batteryQuery}
            setQuery={setBatteryQuery}
            suggestions={batterySuggestions.map((match) => ({
              id: match.id,
              label: match.label,
              subtitle: `${match.subtitle} / ${match.matchReason}`,
              tag: "battery",
            }))}
            onAdd={(id) => {
              addBattery(id);
              setBatteryQuery("");
            }}
          />
          <div className="mt-3 space-y-2">
            {myBatteryIds.length ? (
              myBatteryIds.map((batteryId) => {
                const battery = db.batteriesById.get(batteryId);
                const matches = db.getMyCompatibleCameras(batteryId, myCameraIds);
                return (
                  <InventoryRow key={batteryId} testId={`inventory-battery-${batteryId}`} label={battery?.model ?? batteryId} onRemove={() => removeBattery(batteryId)}>
                    {matches.length ? <Badge tone="green">dung duoc cho {matches.length} may</Badge> : <Badge tone="gray">chua khop may nao</Badge>}
                  </InventoryRow>
                );
              })
            ) : (
              <Empty text="Chua co pin trong kho." />
            )}
          </div>
        </div>
      </div>

      <div data-testid="inventory-comparison" className="mt-5 rounded-md bg-slate-50 p-4">
        <h3 className="font-semibold text-slate-900">So voi kho cua toi</h3>
        <div className="mt-2 grid gap-2 text-sm text-slate-600">
          {uncoveredCameraIds.length ? (
            <p>May chua co pin phu hop: {uncoveredCameraIds.map((id) => db.camerasById.get(id)?.display_name ?? db.candidatesById.get(id)?.display_name ?? id).join(", ")}</p>
          ) : (
            <p>Tat ca may verified trong kho da co it nhat mot pin khop, neu co du lieu compatibility.</p>
          )}
          {unusedBatteryIds.length ? (
            <p>Pin chua dung duoc voi may nao trong kho: {unusedBatteryIds.map((id) => db.batteriesById.get(id)?.model ?? id).join(", ")}</p>
          ) : (
            <p>Khong co pin du theo du lieu hien tai.</p>
          )}
        </div>
      </div>
    </section>
  );
}

function Picker({
  query,
  setQuery,
  suggestions,
  placeholder,
  onAdd,
  testIdPrefix,
}: {
  query: string;
  setQuery: (value: string) => void;
  suggestions: Array<{ id: string; label: string; subtitle: string; tag: string }>;
  placeholder: string;
  onAdd: (id: string) => void;
  testIdPrefix: string;
}) {
  return (
    <div className="mt-2">
      <input
        data-testid={`${testIdPrefix}-search`}
        className="min-h-10 w-full rounded-md border border-slate-300 px-3 text-sm outline-none focus:border-sky-500 focus:ring-4 focus:ring-sky-100"
        placeholder={placeholder}
        value={query}
        onChange={(event) => setQuery(event.target.value)}
      />
      {query && suggestions.length ? (
        <div data-testid={`${testIdPrefix}-suggestions`} className="mt-2 max-h-64 overflow-auto rounded-md border border-slate-200 bg-white">
          {suggestions.map((suggestion) => (
            <button
              key={`${suggestion.tag}-${suggestion.id}`}
              data-testid={`${testIdPrefix}-option-${suggestion.id}`}
              className="block w-full border-b border-slate-100 px-3 py-2 text-left last:border-0 hover:bg-sky-50"
              type="button"
              onClick={() => onAdd(suggestion.id)}
            >
              <span className="block text-sm font-medium text-slate-900">{suggestion.label}</span>
              <span className="block text-xs text-slate-500">{suggestion.subtitle}</span>
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function InventoryRow({
  label,
  children,
  onRemove,
  testId,
}: {
  label: string;
  children: React.ReactNode;
  onRemove: () => void;
  testId: string;
}) {
  return (
    <div data-testid={testId} className="flex items-center justify-between gap-3 rounded-md border border-slate-200 px-3 py-2">
      <div className="min-w-0">
        <div className="truncate text-sm font-medium text-slate-900">{label}</div>
        <div className="mt-1 flex flex-wrap gap-1.5">{children}</div>
      </div>
      <button className="shrink-0 rounded-md px-2 py-1 text-sm font-medium text-slate-500 hover:bg-rose-50 hover:text-rose-700" type="button" onClick={onRemove}>
        Xoa
      </button>
    </div>
  );
}

function Stat({ label, value, testId }: { label: string; value: number; testId: string }) {
  return (
    <div data-testid={testId} className="rounded-md bg-slate-50 px-3 py-2">
      <div className="text-lg font-semibold text-slate-950">{value}</div>
      <div className="text-xs text-slate-500">{label}</div>
    </div>
  );
}

function Empty({ text }: { text: string }) {
  return <div className="rounded-md border border-dashed border-slate-300 px-3 py-4 text-sm text-slate-500">{text}</div>;
}
