import type { InventorySyncController } from "../lib/inventorySync";

const statusCopy: Record<InventorySyncController["status"], { label: string; tone: string }> = {
  local_only: { label: "Local only", tone: "border-slate-200 bg-slate-100 text-slate-700" },
  signed_in: { label: "Signed in", tone: "border-sky-200 bg-sky-50 text-sky-800" },
  loading_cloud: { label: "Loading cloud", tone: "border-sky-200 bg-sky-50 text-sky-800" },
  syncing: { label: "Syncing", tone: "border-sky-200 bg-sky-50 text-sky-800" },
  synced: { label: "Synced", tone: "border-emerald-200 bg-emerald-50 text-emerald-800" },
  unsynced_changes: { label: "Unsynced changes", tone: "border-amber-200 bg-amber-50 text-amber-900" },
  sync_error: { label: "Sync error", tone: "border-rose-200 bg-rose-50 text-rose-800" },
  offline_saved_locally: { label: "Offline, saved locally", tone: "border-amber-200 bg-amber-50 text-amber-900" },
};

export function SyncStatus({ sync }: { sync: InventorySyncController }) {
  const copy = statusCopy[sync.status];

  return (
    <section data-testid="sync-status" className={`rounded-lg border px-4 py-3 text-sm ${copy.tone}`}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <strong data-testid="sync-status-label">{copy.label}</strong>
          <p className="mt-1">
            Camera/battery database stays static in public/data. Cloud sync stores only your inventory ids.
          </p>
        </div>
        {sync.error ? (
          <button
            data-testid="sync-retry"
            className="rounded-md border border-current px-3 py-1.5 text-sm font-medium hover:bg-white/60"
            type="button"
            onClick={() => {
              sync.retrySync();
            }}
          >
            Retry sync
          </button>
        ) : null}
      </div>

      {sync.error ? (
        <p data-testid="sync-error" className="mt-2 font-medium">
          {sync.error}
        </p>
      ) : null}

      {sync.warnings.length ? (
        <div data-testid="sync-warnings" className="mt-2 space-y-1">
          {sync.warnings.map((warning) => (
            <p key={warning}>{warning}</p>
          ))}
        </div>
      ) : null}

      {sync.conflict ? (
        <div data-testid="sync-conflict" className="mt-4 rounded-md border border-amber-300 bg-white/70 p-3 text-slate-800">
          <h3 className="font-semibold">Inventory conflict</h3>
          <p className="mt-1 text-sm">
            Local and cloud inventory differ. Choose which version should become your synced inventory.
          </p>
          <div className="mt-3 grid gap-2 text-xs sm:grid-cols-2">
            <div className="rounded-md border border-slate-200 bg-white p-2">
              Local: {sync.conflict.local.myCameraIds.length} cameras, {sync.conflict.local.myBatteryIds.length} batteries
            </div>
            <div className="rounded-md border border-slate-200 bg-white p-2">
              Cloud: {sync.conflict.cloud.myCameraIds.length} cameras, {sync.conflict.cloud.myBatteryIds.length} batteries
            </div>
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <button className="rounded-md bg-slate-950 px-3 py-2 text-sm font-semibold text-white hover:bg-slate-800" type="button" onClick={() => sync.resolveConflict("local")}>
              Use local
            </button>
            <button className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-semibold hover:bg-slate-50" type="button" onClick={() => sync.resolveConflict("cloud")}>
              Use cloud
            </button>
            <button className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-semibold hover:bg-slate-50" type="button" onClick={() => sync.resolveConflict("merge")}>
              Merge
            </button>
          </div>
        </div>
      ) : null}
    </section>
  );
}
