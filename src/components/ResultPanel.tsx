import { useMemo, useState } from "react";
import type { CameraBatteryDatabase } from "../lib/database";
import type { GroupedCompatibility, LookupResult } from "../types/database";
import { Badge, ConfidenceBadge, SourceBadge, StatusBadge } from "./Badge";
import { SourceDisclosure } from "./SourceDisclosure";

export function ResultPanel({
  db,
  result,
  myCameraIds,
  myBatteryIds,
  addCamera,
  addBattery,
}: {
  db: CameraBatteryDatabase;
  result: LookupResult | null;
  myCameraIds: string[];
  myBatteryIds: string[];
  addCamera: (id: string) => void;
  addBattery: (id: string) => void;
}) {
  if (!result) {
    return (
      <section data-testid="result-empty" className="rounded-lg border border-dashed border-slate-300 bg-white p-8 text-center">
        <h2 className="text-lg font-semibold text-slate-950">Ket qua</h2>
        <p className="mt-2 text-sm text-slate-500">Nhap ten may anh hoac pin de tra cuu trong database source-backed.</p>
      </section>
    );
  }

  return (
    <section data-testid="result-panel" className="rounded-lg border border-slate-200 bg-white p-5 shadow-soft">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-950">Ket qua</h2>
          <p data-testid="natural-answer" className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
            {db.buildNaturalAnswer(result, { myCameraIds, myBatteryIds })}
          </p>
        </div>
        <ResultKindBadge result={result} />
      </div>

      {result.kind === "camera" ? (
        <CameraResult db={db} result={result} addCamera={addCamera} addBattery={addBattery} myBatteryIds={myBatteryIds} />
      ) : null}

      {result.kind === "battery" ? (
        <BatteryResult db={db} result={result} addCamera={addCamera} addBattery={addBattery} myCameraIds={myCameraIds} />
      ) : null}

      {result.kind === "unresolved" ? (
        <div data-testid="result-unresolved" className="mt-5 rounded-md border border-slate-200 bg-slate-50 p-4">
          <div className="flex flex-wrap gap-2">
            <Badge tone="gray">unresolved</Badge>
            <Badge tone="blue">{result.candidate.brand}</Badge>
            <Badge tone="gray">{result.candidate.series}</Badge>
          </div>
          <h3 className="mt-3 text-base font-semibold text-slate-950">{result.candidate.display_name}</h3>
          <p data-testid="unresolved-reason" className="mt-2 text-sm leading-6 text-slate-600">
            {result.unresolved?.reason ?? "Camera existence confirmed, battery not yet source-verified."}
          </p>
          <p className="mt-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm font-medium text-amber-900">
            Khong nen mua pin dua tren model nay cho den khi co nguon xac minh.
          </p>
          <a
            data-testid="unresolved-source"
            className="mt-3 block break-words text-sm font-medium text-sky-700 hover:text-sky-900"
            href={result.candidate.candidate_source_url}
            rel="noreferrer"
            target="_blank"
          >
            {result.candidate.candidate_source_name}
          </a>
          <div className="mt-4 flex flex-wrap gap-2">
            <button
              data-testid="add-unresolved-camera"
              className="rounded-md border border-slate-300 px-3 py-2 text-sm font-medium hover:bg-white"
              type="button"
              onClick={() => addCamera(result.candidate.camera_id)}
            >
              Them model vao kho
            </button>
            <button
              data-testid="copy-unresolved-info"
              className="rounded-md border border-slate-300 px-3 py-2 text-sm font-medium hover:bg-white"
              type="button"
              onClick={() => {
                const text = [
                  `camera_id: ${result.candidate.camera_id}`,
                  `display_name: ${result.candidate.display_name}`,
                  `source: ${result.candidate.candidate_source_url}`,
                  `reason: ${result.unresolved?.reason ?? "battery not source-verified"}`,
                ].join("\n");
                navigator.clipboard?.writeText(text);
              }}
            >
              Copy manual check info
            </button>
          </div>
        </div>
      ) : null}

      {result.kind === "unknown" ? (
        <div data-testid="result-unknown" className="mt-5 rounded-md border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
          Chua co du lieu ve model/pin nay. App khong doan pin theo series hoac ten gan giong.
        </div>
      ) : null}
    </section>
  );
}

function CameraResult({
  db,
  result,
  addCamera,
  addBattery,
  myBatteryIds,
}: {
  db: CameraBatteryDatabase;
  result: Extract<LookupResult, { kind: "camera" }>;
  addCamera: (id: string) => void;
  addBattery: (id: string) => void;
  myBatteryIds: string[];
}) {
  const buckets = {
    primary: result.compatibility.filter((item) => item.status === "fully_compatible"),
    alternate: result.compatibility.filter((item) => item.status === "partially_compatible"),
    cells: result.compatibility.filter((item) => item.status === "uses_aa" || item.status === "uses_aaa"),
    builtIn: result.compatibility.filter((item) => item.status === "built_in_battery"),
  };
  const inInventory = db.getMyCompatibleBatteries(result.camera.camera_id, myBatteryIds);

  return (
    <div data-testid="result-camera" className="mt-5 space-y-4">
      <div className="flex flex-wrap gap-2">
        <button
          data-testid="add-result-camera"
          className="rounded-md bg-slate-950 px-3 py-2 text-sm font-semibold text-white hover:bg-slate-800"
          type="button"
          onClick={() => addCamera(result.camera.camera_id)}
        >
          Them may nay vao kho
        </button>
        <Badge tone="green">verified</Badge>
        <Badge tone="blue">{result.camera.brand}</Badge>
        <Badge tone="gray">{result.camera.category}</Badge>
        {inInventory.length ? <Badge tone="green">co pin trong kho cua ban</Badge> : <Badge tone="gray">chua co pin phu hop trong kho</Badge>}
      </div>

      <CompatibilityGroup title="Pin chinh" items={buckets.primary} db={db} addBattery={addBattery} myBatteryIds={myBatteryIds} />
      <CompatibilityGroup title="Pin thay the / tuong thich mot phan" items={buckets.alternate} db={db} addBattery={addBattery} myBatteryIds={myBatteryIds} />
      <CompatibilityGroup title="AA / AAA / pin pho thong" items={buckets.cells} db={db} addBattery={addBattery} myBatteryIds={myBatteryIds} />
      <CompatibilityGroup title="Built-in battery" items={buckets.builtIn} db={db} addBattery={addBattery} myBatteryIds={myBatteryIds} />
    </div>
  );
}

function CompatibilityGroup({
  title,
  items,
  db,
  addBattery,
  myBatteryIds,
}: {
  title: string;
  items: GroupedCompatibility[];
  db: CameraBatteryDatabase;
  addBattery: (id: string) => void;
  myBatteryIds: string[];
}) {
  if (!items.length) return null;
  return (
    <div>
      <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">{title}</h3>
      <div className="space-y-3">
        {items.map((item) => (
          <CompatibilityCard key={`${item.camera_id}-${item.battery_id}-${item.status}`} item={item} db={db} addBattery={addBattery} myBatteryIds={myBatteryIds} />
        ))}
      </div>
    </div>
  );
}

function BatteryResult({
  db,
  result,
  addCamera,
  addBattery,
  myCameraIds,
}: {
  db: CameraBatteryDatabase;
  result: Extract<LookupResult, { kind: "battery" }>;
  addCamera: (id: string) => void;
  addBattery: (id: string) => void;
  myCameraIds: string[];
}) {
  const [brandFilter, setBrandFilter] = useState("all");
  const brandOptions = useMemo(() => ["all", ...new Set(result.cameras.map((row) => row.camera.brand).sort())], [result.cameras]);
  const filtered = brandFilter === "all" ? result.cameras : result.cameras.filter((row) => row.camera.brand === brandFilter);
  const myMatches = db.getMyCompatibleCameras(result.battery.battery_id, myCameraIds);

  return (
    <div data-testid="result-battery" className="mt-5">
      <div className="flex flex-wrap items-center gap-2">
        <button
          data-testid="add-result-battery"
          className="rounded-md bg-slate-950 px-3 py-2 text-sm font-semibold text-white hover:bg-slate-800"
          type="button"
          onClick={() => addBattery(result.battery.battery_id)}
        >
          Them pin nay vao kho
        </button>
        <Badge tone="green">battery</Badge>
        <Badge tone="blue">{result.battery.brand}</Badge>
        {result.battery.chemistry ? <Badge tone="gray">{result.battery.chemistry}</Badge> : null}
      </div>

      <div data-testid="battery-coverage-summary" className="mt-4 rounded-md bg-slate-50 p-3 text-sm text-slate-700">
        Pin nay dung duoc cho <strong>{result.cameras.length}</strong> may verified trong database, va <strong>{myMatches.length}</strong> may trong kho cua ban.
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <span className="text-sm font-medium text-slate-700">Filter brand</span>
        <select
          data-testid="battery-brand-filter"
          className="rounded-md border border-slate-300 px-3 py-2 text-sm"
          value={brandFilter}
          onChange={(event) => setBrandFilter(event.target.value)}
        >
          {brandOptions.map((brand) => (
            <option key={brand} value={brand}>
              {brand === "all" ? "Tat ca" : brand}
            </option>
          ))}
        </select>
      </div>

      <div className="mt-4 grid gap-3">
        {filtered.map(({ camera, compatibility }) => {
          const inMyCameras = myCameraIds.includes(camera.camera_id);
          return (
            <div key={camera.camera_id} data-testid={`battery-camera-${camera.camera_id}`} className="rounded-md border border-slate-200 p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h3 className="font-semibold text-slate-950">{camera.display_name}</h3>
                  <p className="mt-1 text-sm text-slate-500">
                    {camera.brand} / {camera.series}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  {inMyCameras ? <Badge tone="green">co trong kho may</Badge> : null}
                  <button className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium hover:bg-slate-50" type="button" onClick={() => addCamera(camera.camera_id)}>
                    Them may
                  </button>
                </div>
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                {compatibility.map((item) => (
                  <StatusBadge key={`${item.camera_id}-${item.battery_id}-${item.status}`} status={item.status} />
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function CompatibilityCard({
  item,
  db,
  addBattery,
  myBatteryIds,
}: {
  item: GroupedCompatibility;
  db: CameraBatteryDatabase;
  addBattery: (id: string) => void;
  myBatteryIds: string[];
}) {
  const battery = db.batteriesById.get(item.battery_id);
  const myMatches = db.getMyCompatibleBatteries(item.camera_id, myBatteryIds);
  const inInventory = myMatches.some((match) => match.battery_id === item.battery_id);

  return (
    <div data-testid={`compat-card-${item.battery_id}-${item.status}`} className="rounded-md border border-slate-200 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold text-slate-950">{battery?.model ?? item.battery_id}</h3>
          <p className="mt-1 text-sm text-slate-500">
            {battery?.brand ?? "Unknown brand"}
            {item.quantity_required ? ` / quantity ${item.quantity_required}` : ""}
          </p>
        </div>
        <button
          data-testid={`add-compat-battery-${item.battery_id}`}
          className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium hover:bg-slate-50"
          type="button"
          onClick={() => addBattery(item.battery_id)}
        >
          Them pin
        </button>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        <StatusBadge status={item.status} />
        <ConfidenceBadge confidence={item.best_confidence} />
        <SourceBadge sourceType={item.best_source_type} />
        {inInventory ? <Badge tone="green">co trong kho cua toi</Badge> : <Badge tone="gray">chua co trong kho</Badge>}
      </div>

      {item.notes.length ? <p className="mt-3 text-sm leading-6 text-slate-600">{item.notes[0]}</p> : null}
      <SourceDisclosure compatibility={item} />
    </div>
  );
}

function ResultKindBadge({ result }: { result: LookupResult }) {
  if (result.kind === "camera") return <Badge tone="green">verified camera</Badge>;
  if (result.kind === "battery") return <Badge tone="blue">battery</Badge>;
  if (result.kind === "unresolved") return <Badge tone="gray">unresolved</Badge>;
  return <Badge tone="red">not found</Badge>;
}
