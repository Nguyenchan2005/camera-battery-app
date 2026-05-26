import { useMemo, useRef, useState } from "react";
import type React from "react";
import type { CameraBatteryDatabase } from "../lib/database";
import { analyzeBulkInventoryInput, type BulkInventoryAnalysis } from "../lib/bulkInventory";
import { exportInventory, parseInventoryImport } from "../lib/inventory";
import { Badge } from "./Badge";
import { formatMatchReason } from "./SearchBox";

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
  onSelectCamera,
  onSelectBattery,
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
  onSelectCamera: (id: string) => void;
  onSelectBattery: (id: string) => void;
}) {
  const [cameraQuery, setCameraQuery] = useState("");
  const [batteryQuery, setBatteryQuery] = useState("");
  const [bulkInput, setBulkInput] = useState("");
  const [bulkAnalysis, setBulkAnalysis] = useState<BulkInventoryAnalysis | null>(null);
  const [importWarnings, setImportWarnings] = useState<string[]>([]);
  const importRef = useRef<HTMLInputElement | null>(null);

  const cameraSuggestions = useMemo(
    () => db.searchAll(cameraQuery, 6).filter((match) => match.type === "camera" || match.type === "unresolved_candidate"),
    [cameraQuery, db],
  );
  const batterySuggestions = useMemo(() => db.searchBattery(batteryQuery, 6), [batteryQuery, db]);

  const verifiedInventoryCameraIds = myCameraIds.filter((cameraId) => db.camerasById.has(cameraId));
  const unverifiedInventoryCameraIds = myCameraIds.filter((cameraId) => !db.camerasById.has(cameraId) && db.candidatesById.has(cameraId));
  const unknownInventoryCameraIds = myCameraIds.filter((cameraId) => !db.camerasById.has(cameraId) && !db.candidatesById.has(cameraId));
  const coveredCameraIds = verifiedInventoryCameraIds.filter((cameraId) => db.getMyCompatibleBatteries(cameraId, myBatteryIds).length > 0);
  const uncoveredCameraIds = verifiedInventoryCameraIds.filter((cameraId) => !db.getMyCompatibleBatteries(cameraId, myBatteryIds).length);
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

  function addMatchToInventory(match: { type: "camera" | "battery" | "unresolved_candidate"; id: string }) {
    if (match.type === "battery") {
      addBattery(match.id);
    } else {
      addCamera(match.id);
    }
  }

  function handleBulkAdd() {
    const analysis = analyzeBulkInventoryInput(bulkInput, db);
    for (const row of analysis.autoMatches) {
      addMatchToInventory(row.match);
    }
    setBulkAnalysis(analysis);
  }

  function chooseAmbiguousOption(line: string, optionIndex: number) {
    if (!bulkAnalysis) return;
    const row = bulkAnalysis.ambiguousMatches.find((item) => item.line === line);
    const match = row?.options[optionIndex];
    if (!match) return;
    addMatchToInventory(match);
    setBulkAnalysis({
      ...bulkAnalysis,
      ambiguousMatches: bulkAnalysis.ambiguousMatches.filter((item) => item.line !== line),
      autoMatches: [...bulkAnalysis.autoMatches, { line, match }],
    });
  }

  return (
    <section data-testid="inventory-panel" className="rounded-lg border border-slate-200 bg-white p-5 shadow-soft">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-950">Kho của tôi</h2>
          <p className="text-sm text-slate-500">Máy ảnh và pin bạn đang sở hữu</p>
        </div>
        <div className="grid grid-cols-2 gap-2 text-center text-sm sm:grid-cols-5">
          <Stat label="Máy ảnh" value={myCameraIds.length} testId="inventory-camera-count" />
          <Stat label="Pin" value={myBatteryIds.length} testId="inventory-battery-count" />
          <Stat label="Có pin" value={coveredCameraIds.length} testId="inventory-covered-count" />
          <Stat label="Thiếu pin" value={uncoveredCameraIds.length} testId="inventory-uncovered-count" />
          <Stat label="Cần xác minh" value={unverifiedInventoryCameraIds.length} testId="inventory-unverified-count" />
        </div>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <button data-testid="inventory-export" className="rounded-md border border-slate-300 px-3 py-2 text-sm font-medium hover:bg-slate-50" type="button" onClick={handleExport}>
          Xuất kho dạng JSON
        </button>
        <button
          data-testid="inventory-import-button"
          className="rounded-md border border-slate-300 px-3 py-2 text-sm font-medium hover:bg-slate-50"
          type="button"
          onClick={() => importRef.current?.click()}
        >
          Nhập kho từ JSON
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

      <div data-testid="inventory-bulk-panel" className="mt-5 rounded-md border border-slate-200 bg-slate-50 p-4">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h3 className="font-semibold text-slate-900">Thêm nhiều mục từ danh sách</h3>
            <p className="mt-1 text-sm text-slate-600">
              Mỗi dòng là một máy ảnh hoặc pin. Mục khớp chính xác duy nhất sẽ được thêm tự động; mục mơ hồ sẽ chờ bạn chọn.
            </p>
          </div>
          <button
            data-testid="inventory-bulk-clear"
            className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-medium hover:bg-slate-50"
            type="button"
            onClick={() => {
              setBulkInput("");
              setBulkAnalysis(null);
            }}
          >
            Xóa nội dung
          </button>
        </div>
        <textarea
          data-testid="inventory-bulk-input"
          className="mt-3 min-h-32 w-full resize-y rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-teal-600 focus:ring-4 focus:ring-teal-100"
          placeholder={"Canon G7X Mark III\nSony RX100 VII\nNB13L\nNPBX1"}
          value={bulkInput}
          onChange={(event) => setBulkInput(event.target.value)}
        />
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            data-testid="inventory-bulk-add"
            className="rounded-md bg-teal-700 px-3 py-2 text-sm font-semibold text-white hover:bg-teal-800 disabled:cursor-not-allowed disabled:bg-slate-400"
            type="button"
            disabled={!bulkInput.trim()}
            onClick={handleBulkAdd}
          >
            Thêm mục khớp chính xác
          </button>
          <span className="self-center text-xs text-slate-500">Model chưa xác minh vẫn có thể lưu vào kho, nhưng sẽ không được gán pin.</span>
        </div>
        {bulkAnalysis ? (
          <BulkAnalysisSummary analysis={bulkAnalysis} onChooseOption={chooseAmbiguousOption} />
        ) : null}
      </div>

      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <div>
          <div className="flex items-center justify-between gap-3">
            <h3 className="font-semibold text-slate-900">Máy ảnh</h3>
            <button data-testid="clear-cameras" className="text-xs font-medium text-slate-500 hover:text-rose-700" type="button" onClick={clearCameras}>
              Xóa tất cả
            </button>
          </div>
          <Picker
            testIdPrefix="inventory-camera"
            placeholder="Thêm máy ảnh..."
            query={cameraQuery}
            setQuery={setCameraQuery}
            suggestions={cameraSuggestions.map((match) => ({
              id: match.id,
              label: match.label,
              subtitle: `${match.subtitle} / ${formatMatchReason(match.matchReason)}`,
              tag: match.type === "camera" ? "đã có pin" : "chưa xác minh",
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
                  <InventoryRow
                    key={cameraId}
                    testId={`inventory-camera-${cameraId}`}
                    label={label}
                    actionLabel={status.status === "verified" ? "Xem pin" : "Xem trạng thái"}
                    onOpen={() => onSelectCamera(cameraId)}
                    onRemove={() => removeCamera(cameraId)}
                  >
                    <Badge tone={status.status === "verified" ? "green" : status.status === "unresolved" ? "gray" : "red"}>
                      {status.status === "verified" ? "Đã có dữ liệu pin" : status.status === "unresolved" ? "Chưa xác minh" : "Không có dữ liệu"}
                    </Badge>
                    {status.status === "verified" && matches.length ? <Badge tone="green">Có pin trong kho</Badge> : null}
                    {status.status === "verified" && !matches.length ? <Badge tone="gray">Chưa có pin phù hợp</Badge> : null}
                    {status.status === "unresolved" ? <Badge tone="gray">Cần xác minh pin</Badge> : null}
                    {status.status === "unknown" ? <Badge tone="red">Không có trong dữ liệu</Badge> : null}
                  </InventoryRow>
                );
              })
            ) : (
              <Empty text="Chưa có máy ảnh trong kho." />
            )}
          </div>
        </div>

        <div>
          <div className="flex items-center justify-between gap-3">
            <h3 className="font-semibold text-slate-900">Pin</h3>
            <button data-testid="clear-batteries" className="text-xs font-medium text-slate-500 hover:text-rose-700" type="button" onClick={clearBatteries}>
              Xóa tất cả
            </button>
          </div>
          <Picker
            testIdPrefix="inventory-battery"
            placeholder="Thêm pin..."
            query={batteryQuery}
            setQuery={setBatteryQuery}
            suggestions={batterySuggestions.map((match) => ({
              id: match.id,
              label: match.label,
              subtitle: `${match.subtitle} / ${formatMatchReason(match.matchReason)}`,
              tag: "pin",
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
                  <InventoryRow
                    key={batteryId}
                    testId={`inventory-battery-${batteryId}`}
                    label={battery?.model ?? batteryId}
                    actionLabel="Xem máy tương thích"
                    onOpen={() => onSelectBattery(batteryId)}
                    onRemove={() => removeBattery(batteryId)}
                  >
                    {matches.length ? <Badge tone="green">Dùng được cho {matches.length} máy</Badge> : <Badge tone="gray">Chưa khớp máy nào</Badge>}
                  </InventoryRow>
                );
              })
            ) : (
              <Empty text="Chưa có pin trong kho." />
            )}
          </div>
        </div>
      </div>

      <div data-testid="inventory-comparison" className="mt-5 rounded-md bg-slate-50 p-4">
        <h3 className="font-semibold text-slate-900">Đối chiếu trong kho</h3>
        <div className="mt-2 grid gap-2 text-sm text-slate-600">
          {unverifiedInventoryCameraIds.length ? (
            <p data-testid="inventory-unverified-summary">Có {unverifiedInventoryCameraIds.length} máy trong kho chưa xác minh pin: {unverifiedInventoryCameraIds.map((id) => db.candidatesById.get(id)?.display_name ?? id).join(", ")}</p>
          ) : (
            <p>Không có máy chưa xác minh pin trong kho.</p>
          )}
          {uncoveredCameraIds.length ? (
            <p data-testid="inventory-verified-missing-summary">Máy đã có mapping nhưng thiếu pin phù hợp: {uncoveredCameraIds.map((id) => db.camerasById.get(id)?.display_name ?? id).join(", ")}</p>
          ) : (
            <p>Tất cả máy đã có mapping trong kho hiện có ít nhất một pin phù hợp.</p>
          )}
          {unknownInventoryCameraIds.length ? <p>Mã máy ảnh không còn trong dữ liệu: {unknownInventoryCameraIds.join(", ")}</p> : null}
          {unusedBatteryIds.length ? (
            <p>Pin chưa dùng được với máy nào trong kho: {unusedBatteryIds.map((id) => db.batteriesById.get(id)?.model ?? id).join(", ")}</p>
          ) : (
            <p>Không có pin dư theo dữ liệu hiện tại.</p>
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
        className="min-h-10 w-full rounded-md border border-slate-300 px-3 text-sm outline-none focus:border-teal-600 focus:ring-4 focus:ring-teal-100"
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
              className="block w-full border-b border-slate-100 px-3 py-2 text-left last:border-0 hover:bg-teal-50"
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

function BulkAnalysisSummary({
  analysis,
  onChooseOption,
}: {
  analysis: BulkInventoryAnalysis;
  onChooseOption: (line: string, optionIndex: number) => void;
}) {
  return (
    <div data-testid="inventory-bulk-summary" className="mt-4 space-y-3 text-sm">
      <div className="grid gap-2 sm:grid-cols-4">
        <SummaryMetric label="Dòng đã đọc" value={analysis.totalLines} />
        <SummaryMetric label="Tự thêm chính xác" value={analysis.autoMatches.length} />
        <SummaryMetric label="Cần chọn" value={analysis.ambiguousMatches.length} />
        <SummaryMetric label="Không thấy" value={analysis.notFound.length} />
      </div>

      {analysis.autoMatches.length ? (
        <div data-testid="inventory-bulk-auto" className="rounded-md border border-emerald-200 bg-emerald-50 p-3 text-emerald-800">
          <strong>Đã tự thêm:</strong>
          <ul className="mt-2 list-inside list-disc space-y-1">
            {analysis.autoMatches.map((row) => (
              <li key={`${row.line}-${row.match.type}-${row.match.id}`}>
                {row.line} → {row.match.label} ({formatItemType(row.match.type)})
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {analysis.ambiguousMatches.length ? (
        <div data-testid="inventory-bulk-ambiguous" className="rounded-md border border-amber-200 bg-amber-50 p-3 text-amber-900">
          <strong>Cần chọn thủ công:</strong>
          <div className="mt-3 space-y-3">
            {analysis.ambiguousMatches.map((row) => (
              <div key={row.line} className="rounded-md border border-amber-200 bg-white p-3">
                <div className="font-medium">{row.line}</div>
                <div className="mt-1 text-xs text-amber-800">{row.reason}</div>
                <div className="mt-2 grid gap-2">
                  {row.options.map((option, index) => (
                    <button
                      key={`${row.line}-${option.type}-${option.id}`}
                      data-testid={`inventory-bulk-option-${safeTestId(row.line)}-${index}`}
                      className="rounded-md border border-slate-200 bg-white px-3 py-2 text-left hover:border-teal-300 hover:bg-teal-50"
                      type="button"
                      onClick={() => onChooseOption(row.line, index)}
                    >
                      <span className="block font-medium text-slate-900">{option.label}</span>
                      <span className="block text-xs text-slate-500">
                        {formatItemType(option.type)} / {option.subtitle} / {formatMatchReason(option.matchReason)}
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {analysis.notFound.length ? (
        <div data-testid="inventory-bulk-not-found" className="rounded-md border border-rose-200 bg-rose-50 p-3 text-rose-800">
          <strong>Không tìm thấy:</strong>
          <ul className="mt-2 list-inside list-disc space-y-1">
            {analysis.notFound.map((row) => (
              <li key={row.line}>{row.line}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

function SummaryMetric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md border border-slate-200 bg-white px-3 py-2 text-center">
      <div className="text-base font-semibold text-slate-950">{value}</div>
      <div className="text-xs text-slate-500">{label}</div>
    </div>
  );
}

function safeTestId(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

function InventoryRow({
  label,
  children,
  actionLabel,
  onOpen,
  onRemove,
  testId,
}: {
  label: string;
  children: React.ReactNode;
  actionLabel: string;
  onOpen: () => void;
  onRemove: () => void;
  testId: string;
}) {
  return (
    <div data-testid={testId} className="flex items-start justify-between gap-2 rounded-md border border-slate-200 px-2 py-2">
      <button
        data-testid={`${testId}-open`}
        aria-label={`${actionLabel}: ${label}`}
        className="min-w-0 flex-1 rounded-md px-1 py-1 text-left transition hover:bg-teal-50 focus-visible:bg-teal-50"
        type="button"
        onClick={onOpen}
      >
        <div data-testid={`${testId}-label`} className="break-words text-sm font-medium leading-5 text-slate-900">{label}</div>
        <div className="mt-1 flex flex-wrap gap-1.5">{children}</div>
        <div className="mt-2 text-xs font-medium text-teal-700">{actionLabel}</div>
      </button>
      <button aria-label={`Xóa ${label} khỏi kho`} className="shrink-0 rounded-md px-2 py-1 text-sm font-medium text-slate-500 hover:bg-rose-50 hover:text-rose-700" type="button" onClick={onRemove}>
        Xóa
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

function formatItemType(type: "camera" | "battery" | "unresolved_candidate"): string {
  return type === "camera" ? "Máy đã có pin" : type === "battery" ? "Pin" : "Model chưa xác minh";
}
