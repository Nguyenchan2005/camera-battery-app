import { useEffect, useMemo, useState } from "react";
import type React from "react";
import { AuthPanel } from "./components/AuthPanel";
import { DatabaseStats } from "./components/DatabaseStats";
import { InventoryPanel } from "./components/InventoryPanel";
import { ResultPanel } from "./components/ResultPanel";
import { SearchBox } from "./components/SearchBox";
import { SyncStatus } from "./components/SyncStatus";
import { useLocalStorageIds } from "./hooks/useLocalStorageIds";
import { useOnlineStatus } from "./hooks/useOnlineStatus";
import { createDatabase, loadDataBundle, type CameraBatteryDatabase } from "./lib/database";
import { useInventorySync } from "./lib/inventorySync";
import type { LookupResult, RuntimeValidationIssue, SearchMatch } from "./types/database";

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: Error }
  | { status: "ready"; db: CameraBatteryDatabase; issues: RuntimeValidationIssue[] };

export default function App() {
  const [loadState, setLoadState] = useState<LoadState>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    loadDataBundle({ baseUrl: `${import.meta.env.BASE_URL}data` })
      .then((bundle) => {
        if (cancelled) return;
        const db = createDatabase(bundle);
        setLoadState({ status: "ready", db, issues: db.validateRuntimeData() });
      })
      .catch((error: Error) => {
        if (!cancelled) setLoadState({ status: "error", error });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (loadState.status === "loading") {
    return <Shell><LoadingState /></Shell>;
  }

  if (loadState.status === "error") {
    return <Shell><ErrorState error={loadState.error} /></Shell>;
  }

  return <ReadyApp db={loadState.db} runtimeIssues={loadState.issues} />;
}

function ReadyApp({ db, runtimeIssues }: { db: CameraBatteryDatabase; runtimeIssues: RuntimeValidationIssue[] }) {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<LookupResult | null>(null);
  const myCameras = useLocalStorageIds("compact-camera-db:my-camera-ids");
  const myBatteries = useLocalStorageIds("compact-camera-db:my-battery-ids");
  const onlineStatus = useOnlineStatus();
  const inventorySync = useInventorySync({
    db,
    myCameraIds: myCameras.ids,
    myBatteryIds: myBatteries.ids,
    replaceCameras: myCameras.replace,
    replaceBatteries: myBatteries.replace,
    online: onlineStatus.online,
  });

  const suggestionsByTab = useMemo(() => db.getSearchTabs(query), [query, db]);
  const allSuggestions = suggestionsByTab.all;

  function selectMatch(match: SearchMatch) {
    setResult(db.lookupFromMatch(match, query));
  }

  function submitSearch() {
    setResult(allSuggestions.length ? db.lookupFromMatch(allSuggestions[0], query) : { kind: "unknown", query });
  }

  return (
    <Shell>
      <header data-testid="app-ready" className="flex flex-col gap-4 border-b border-slate-200 pb-5 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-normal text-slate-950 sm:text-3xl">
            Tra cuu pin may anh compact
          </h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
            Database local, source-backed. App chi hien thi pin khi co camera verified va compatibility row.
          </p>
        </div>
        <div className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-5 lg:min-w-[520px]">
          <Metric label="Verified" value={db.dataSummary.verifiedCameras} />
          <Metric label="Pin" value={db.dataSummary.batteries} />
          <Metric label="Mapping" value={db.dataSummary.compatibilityRows} />
          <Metric label="Catalog" value={db.dataSummary.candidates} />
          <Metric label="Unresolved" value={db.dataSummary.unresolved} />
        </div>
      </header>

      <OnlineStatusBadge online={onlineStatus.online} serviceWorkerReady={onlineStatus.serviceWorkerReady} />
      <AuthPanel sync={inventorySync} />
      <SyncStatus sync={inventorySync} />

      {runtimeIssues.length ? (
        <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          Runtime data validation co {runtimeIssues.length} warning/error. Xem console de biet chi tiet.
        </div>
      ) : null}

      <DatabaseStats db={db} />

      <div className="grid gap-6 xl:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)]">
        <InventoryPanel
          db={db}
          myCameraIds={myCameras.ids}
          myBatteryIds={myBatteries.ids}
          addCamera={myCameras.add}
          replaceCameras={myCameras.replace}
          removeCamera={myCameras.remove}
          clearCameras={myCameras.clear}
          addBattery={myBatteries.add}
          replaceBatteries={myBatteries.replace}
          removeBattery={myBatteries.remove}
          clearBatteries={myBatteries.clear}
        />

        <div className="space-y-6">
          <SearchBox
            query={query}
            suggestionsByTab={suggestionsByTab}
            onQueryChange={setQuery}
            onSubmit={submitSearch}
            onSelect={selectMatch}
          />
          <ResultPanel
            db={db}
            result={result}
            myCameraIds={myCameras.ids}
            myBatteryIds={myBatteries.ids}
            addCamera={myCameras.add}
            addBattery={myBatteries.add}
          />
        </div>
      </div>
    </Shell>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <main className="min-h-screen bg-paper text-ink">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
        {children}
      </div>
    </main>
  );
}

function LoadingState() {
  return (
    <div data-testid="loading-state" className="rounded-lg border border-slate-200 bg-white p-8 shadow-soft">
      <div className="h-2 w-48 overflow-hidden rounded-full bg-slate-100">
        <div className="h-full w-1/2 animate-pulse rounded-full bg-sky-500" />
      </div>
      <h1 className="mt-5 text-2xl font-semibold text-slate-950">Dang tai database...</h1>
      <p className="mt-2 text-sm text-slate-600">App dang lazy-load JSON tu public/data. Khi da cache, app co the tra cuu offline.</p>
    </div>
  );
}

function ErrorState({ error }: { error: Error }) {
  return (
    <div data-testid="data-load-error" className="rounded-lg border border-rose-200 bg-rose-50 p-8 text-rose-900">
      <h1 className="text-2xl font-semibold">Khong tai duoc database</h1>
      <p className="mt-2 text-sm">{error.message}</p>
      <p className="mt-4 text-sm">Kiem tra public/data/*.json, missing file, hoac schema mismatch.</p>
    </div>
  );
}

function OnlineStatusBadge({ online, serviceWorkerReady }: { online: boolean; serviceWorkerReady: boolean }) {
  if (!online) {
    return (
      <div data-testid="network-status" className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm font-medium text-amber-900">
        Offline, dang dung cached data{serviceWorkerReady ? " qua service worker." : "."}
      </div>
    );
  }
  return (
    <div data-testid="network-status" className="rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-800">
      Online{serviceWorkerReady ? " - offline cache ready." : " - service worker dang khoi tao."}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md border border-slate-200 bg-white px-3 py-2 text-center">
      <div className="text-lg font-semibold text-slate-950">{value.toLocaleString("vi-VN")}</div>
      <div className="text-xs text-slate-500">{label}</div>
    </div>
  );
}
