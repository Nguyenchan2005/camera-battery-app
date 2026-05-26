import { useEffect, useMemo, useRef, useState } from "react";
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
  const resultRef = useRef<HTMLDivElement | null>(null);
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

  function revealInventoryResult(nextResult: LookupResult) {
    setResult(nextResult);
    window.requestAnimationFrame(() => {
      resultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }

  function selectInventoryCamera(cameraId: string) {
    const status = db.getCandidateStatus(cameraId);
    if (status.status === "verified") {
      revealInventoryResult({
        kind: "camera",
        camera: status.camera,
        compatibility: db.getCameraBatteryCompatibility(cameraId),
      });
      return;
    }
    if (status.status === "unresolved") {
      revealInventoryResult({
        kind: "unresolved",
        candidate: status.candidate,
        unresolved: status.unresolved,
        suggestions: db.getBatterySuggestionsForCandidate(cameraId),
      });
      return;
    }
    revealInventoryResult({ kind: "unknown", query: cameraId });
  }

  function selectInventoryBattery(batteryId: string) {
    const battery = db.batteriesById.get(batteryId);
    if (!battery) {
      revealInventoryResult({ kind: "unknown", query: batteryId });
      return;
    }
    revealInventoryResult({
      kind: "battery",
      battery,
      cameras: db.getBatteryCompatibleCameras(batteryId),
      suggestions: db.getBatterySuggestionsForBattery(batteryId),
    });
  }

  return (
    <Shell>
      <header data-testid="app-ready" className="rounded-lg border border-slate-200 bg-white px-5 py-5 shadow-soft sm:px-6">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="mb-2 text-xs font-semibold uppercase text-teal-700">Cơ sở dữ liệu pin có nguồn đối chiếu</p>
          <h1 className="text-2xl font-semibold tracking-normal text-slate-950 sm:text-3xl">
            Tra cứu pin máy ảnh compact
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
            Chỉ hiển thị pin tương thích khi model đã có mapping kèm nguồn. Model chưa xác minh được tách riêng để tránh mua nhầm pin.
          </p>
        </div>
        <div className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-5 lg:min-w-[530px]">
          <Metric label="Máy có pin" value={db.dataSummary.verifiedCameras} />
          <Metric label="Pin" value={db.dataSummary.batteries} />
          <Metric label="Liên kết" value={db.dataSummary.compatibilityRows} />
          <Metric label="Catalog" value={db.dataSummary.candidates} />
          <Metric label="Chưa rõ pin" value={db.dataSummary.unresolved} />
        </div>
        </div>
      </header>

      <OnlineStatusBadge online={onlineStatus.online} serviceWorkerReady={onlineStatus.serviceWorkerReady} />

      {runtimeIssues.length ? (
        <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          Kiểm tra dữ liệu lúc khởi động phát hiện {runtimeIssues.length} cảnh báo/lỗi. Xem console để biết chi tiết.
        </div>
      ) : null}

      <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1.03fr)_minmax(430px,0.97fr)]">
        <div className="space-y-5">
          <SearchBox
            query={query}
            suggestionsByTab={suggestionsByTab}
            onQueryChange={setQuery}
            onSubmit={submitSearch}
            onSelect={selectMatch}
          />
          <div ref={resultRef}>
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
          onSelectCamera={selectInventoryCamera}
          onSelectBattery={selectInventoryBattery}
        />
      </div>

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(360px,0.7fr)]">
        <DatabaseStats db={db} />
        <div className="space-y-4">
          <AuthPanel sync={inventorySync} />
          <SyncStatus sync={inventorySync} />
        </div>
      </div>
    </Shell>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <main className="min-h-screen bg-paper text-ink">
      <div className="mx-auto flex w-full max-w-[1380px] flex-col gap-5 px-4 py-5 sm:px-6 lg:px-8">
        {children}
      </div>
    </main>
  );
}

function LoadingState() {
  return (
    <div data-testid="loading-state" className="mt-8 rounded-lg border border-slate-200 bg-white p-8 shadow-soft">
      <div className="h-2 w-48 overflow-hidden rounded-full bg-slate-100">
        <div className="h-full w-1/2 animate-pulse rounded-full bg-teal-600" />
      </div>
      <h1 className="mt-5 text-2xl font-semibold text-slate-950">Đang tải dữ liệu...</h1>
      <p className="mt-2 text-sm text-slate-600">Ứng dụng đang tải các tệp dữ liệu. Sau khi được lưu cache, bạn vẫn có thể tra cứu khi ngoại tuyến.</p>
    </div>
  );
}

function ErrorState({ error }: { error: Error }) {
  return (
    <div data-testid="data-load-error" className="rounded-lg border border-rose-200 bg-rose-50 p-8 text-rose-900">
      <h1 className="text-2xl font-semibold">Không tải được dữ liệu</h1>
      <p className="mt-2 text-sm">{error.message}</p>
      <p className="mt-4 text-sm">Hãy kiểm tra các tệp <code>public/data/*.json</code> và cấu trúc dữ liệu trước khi tải lại trang.</p>
    </div>
  );
}

function OnlineStatusBadge({ online, serviceWorkerReady }: { online: boolean; serviceWorkerReady: boolean }) {
  if (!online) {
    return (
      <div data-testid="network-status" className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm font-medium text-amber-900">
        Ngoại tuyến, đang dùng dữ liệu đã lưu{serviceWorkerReady ? " qua bộ nhớ đệm của ứng dụng." : "."}
      </div>
    );
  }
  return (
    <div data-testid="network-status" className="rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-800">
      Trực tuyến{serviceWorkerReady ? " - dữ liệu ngoại tuyến đã sẵn sàng." : " - đang chuẩn bị bộ nhớ đệm ngoại tuyến."}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-center">
      <div className="text-lg font-semibold text-slate-950">{value.toLocaleString("vi-VN")}</div>
      <div className="text-xs text-slate-500">{label}</div>
    </div>
  );
}
