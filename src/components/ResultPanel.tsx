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
        <h2 className="text-lg font-semibold text-slate-950">Kết quả tra cứu</h2>
        <p className="mt-2 text-sm text-slate-500">Nhập tên máy ảnh hoặc mã pin để xem dữ liệu tương thích và nguồn đối chiếu.</p>
      </section>
    );
  }

  return (
    <section data-testid="result-panel" className="rounded-lg border border-slate-200 bg-white p-5 shadow-soft">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-950">Kết quả tra cứu</h2>
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
        <div data-testid="result-unresolved" className="mt-5 rounded-md border border-amber-200 bg-amber-50/60 p-4">
          <div className="flex flex-wrap gap-2">
            <Badge tone="gray">Chưa xác minh pin</Badge>
            <Badge tone="blue">{result.candidate.brand}</Badge>
            <Badge tone="gray">{result.candidate.series}</Badge>
          </div>
          <h3 className="mt-3 text-base font-semibold text-slate-950">Đã tìm thấy model này trong catalog, nhưng chưa xác minh được pin.</h3>
          <div className="mt-3 grid gap-2 text-sm text-slate-700 sm:grid-cols-2">
            <InfoItem label="Model" value={result.candidate.display_name} />
            <InfoItem label="Hãng" value={result.candidate.brand} />
            <InfoItem label="Dòng máy" value={result.candidate.series} />
            <InfoItem label="Trạng thái" value="Chưa có nguồn xác minh pin" />
          </div>
          <p data-testid="unresolved-reason" className="mt-2 text-sm leading-6 text-slate-600">
            {formatUnresolvedReason(result.unresolved?.reason)}
          </p>
          <p className="mt-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm font-medium text-amber-900">
            Không nên mua pin dựa trên model này cho đến khi có nguồn xác minh.
          </p>
          <a
            data-testid="unresolved-source"
            className="mt-3 block break-words text-sm font-medium text-teal-700 hover:text-teal-900"
            href={result.candidate.candidate_source_url}
            rel="noreferrer"
            target="_blank"
          >
            {result.candidate.candidate_source_name}
          </a>
          {result.suggestions.length ? (
            <div data-testid="unresolved-suggestions" className="mt-4 rounded-md border border-amber-200 bg-amber-50 p-3">
              <h4 className="text-sm font-semibold text-amber-950">Gợi ý chưa xác minh</h4>
              <p className="mt-1 text-sm text-amber-900">
                Chưa có mapping pin đã xác minh. Các gợi ý dưới đây chỉ là đầu mối để kiểm tra thủ công, không phải kết luận tương thích.
              </p>
              <div className="mt-3 space-y-3">
                {result.suggestions.map((suggestion) => (
                  <div key={`${suggestion.camera_id}-${suggestion.suggested_battery_model}-${suggestion.source_url}`} className="rounded-md border border-amber-200 bg-white p-3 text-sm">
                    <div className="flex flex-wrap items-center gap-2">
                      <strong className="text-slate-950">{suggestion.suggested_battery_model}</strong>
                      <ConfidenceBadge confidence={suggestion.confidence} />
                      <Badge tone="gray">Gợi ý, chưa xác minh</Badge>
                    </div>
                    <p className="mt-2 text-slate-600">{suggestion.warning}</p>
                    <a className="mt-2 block break-words font-medium text-teal-700 hover:text-teal-900" href={suggestion.source_url} rel="noreferrer" target="_blank">
                      {suggestion.source_name}
                    </a>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
          <div className="mt-4 flex flex-wrap gap-2">
            <button
              data-testid="add-unresolved-camera"
              className="rounded-md border border-slate-300 px-3 py-2 text-sm font-medium hover:bg-white"
              type="button"
              onClick={() => addCamera(result.candidate.camera_id)}
            >
              Thêm model vào kho
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
                  `reason: ${formatUnresolvedReason(result.unresolved?.reason)}`,
                ].join("\n");
                navigator.clipboard?.writeText(text);
              }}
            >
              Sao chép thông tin để kiểm tra
            </button>
            <button
              data-testid="mark-needs-verification"
              className="rounded-md border border-slate-300 px-3 py-2 text-sm font-medium hover:bg-white"
              type="button"
              onClick={() => {
                const text = [
                  "{",
                  `  "query": "${result.candidate.display_name}",`,
                  `  "expected_brand": "${result.candidate.brand}",`,
                  `  "expected_model": "${result.candidate.model}",`,
                  `  "status": "unresolved_battery",`,
                  `  "notes": "Cần nguồn xác minh pin cụ thể."`,
                  "}",
                ].join("\n");
                navigator.clipboard?.writeText(text);
              }}
            >
              Đánh dấu cần xác minh pin
            </button>
          </div>
        </div>
      ) : null}

      {result.kind === "unknown" ? (
        <div data-testid="result-unknown" className="mt-5 rounded-md border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
          Chưa có dữ liệu về model/pin này. Ứng dụng không đoán pin theo cùng dòng máy hoặc tên gần giống.
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
          className="rounded-md bg-teal-700 px-3 py-2 text-sm font-semibold text-white hover:bg-teal-800"
          type="button"
          onClick={() => addCamera(result.camera.camera_id)}
        >
          Thêm máy này vào kho
        </button>
        <Badge tone="green">Đã ghi nhận mapping pin</Badge>
        <Badge tone="blue">{result.camera.brand}</Badge>
        <Badge tone="gray">{formatCategory(result.camera.category)}</Badge>
        {inInventory.length ? <Badge tone="green">Có pin phù hợp trong kho</Badge> : <Badge tone="gray">Chưa có pin phù hợp trong kho</Badge>}
      </div>

      <CompatibilityGroup title="Pin chính" items={buckets.primary} db={db} addBattery={addBattery} myBatteryIds={myBatteryIds} />
      <CompatibilityGroup title="Pin thay thế / tương thích một phần" items={buckets.alternate} db={db} addBattery={addBattery} myBatteryIds={myBatteryIds} />
      <CompatibilityGroup title="Pin AA / AAA" items={buckets.cells} db={db} addBattery={addBattery} myBatteryIds={myBatteryIds} />
      <CompatibilityGroup title="Pin tích hợp" items={buckets.builtIn} db={db} addBattery={addBattery} myBatteryIds={myBatteryIds} />
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
      <h3 className="mb-2 text-sm font-semibold uppercase text-slate-500">{title}</h3>
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
          className="rounded-md bg-teal-700 px-3 py-2 text-sm font-semibold text-white hover:bg-teal-800"
          type="button"
          onClick={() => addBattery(result.battery.battery_id)}
        >
          Thêm pin này vào kho
        </button>
        <Badge tone="green">Pin trong dữ liệu</Badge>
        <Badge tone="blue">{result.battery.brand}</Badge>
        {result.battery.chemistry ? <Badge tone="gray">{result.battery.chemistry}</Badge> : null}
      </div>

      <div data-testid="battery-coverage-summary" className="mt-4 rounded-md bg-slate-50 p-3 text-sm text-slate-700">
        Pin này dùng được cho <strong>{result.cameras.length}</strong> máy ảnh có mapping trong dữ liệu và <strong>{myMatches.length}</strong> máy trong kho của bạn.
      </div>
      <p data-testid="battery-unresolved-note" className="mt-2 rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-600">
        Kết quả chỉ bao gồm máy ảnh đã có mapping pin kèm nguồn. Các model chưa xác minh sẽ không xuất hiện trong danh sách tương thích pin.
      </p>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <span className="text-sm font-medium text-slate-700">Lọc theo hãng</span>
        <select
          data-testid="battery-brand-filter"
          className="rounded-md border border-slate-300 px-3 py-2 text-sm"
          value={brandFilter}
          onChange={(event) => setBrandFilter(event.target.value)}
        >
          {brandOptions.map((brand) => (
            <option key={brand} value={brand}>
              {brand === "all" ? "Tất cả" : brand}
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
                  {inMyCameras ? <Badge tone="green">Có trong kho máy</Badge> : null}
                  <button className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium hover:bg-slate-50" type="button" onClick={() => addCamera(camera.camera_id)}>
                    Thêm máy
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

      {result.suggestions.length ? (
        <div data-testid="battery-suggested-matches" className="mt-5 rounded-md border border-amber-200 bg-amber-50 p-4">
          <h3 className="text-sm font-semibold text-amber-950">Gợi ý tương thích chưa xác minh</h3>
          <p className="mt-1 text-sm text-amber-900">
            Các model này không nằm trong danh sách tương thích đã xác minh. Cần kiểm tra nguồn chính hãng hoặc hướng dẫn sử dụng trước khi mua pin.
          </p>
          <div className="mt-3 space-y-2">
            {result.suggestions.map((suggestion) => (
              <div key={`${suggestion.camera_id}-${suggestion.source_url}`} className="rounded-md border border-amber-200 bg-white px-3 py-2 text-sm">
                <strong>{suggestion.display_name}</strong>
                <span className="ml-2 text-slate-600">{suggestion.source_name}</span>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function InfoItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs font-semibold uppercase text-slate-500">{label}</div>
      <div className="mt-1 break-words font-medium text-slate-900">{value}</div>
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
            {battery?.brand ?? "Chưa rõ hãng"}
            {item.quantity_required ? ` / Số lượng: ${item.quantity_required}` : ""}
          </p>
        </div>
        <button
          data-testid={`add-compat-battery-${item.battery_id}`}
          className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium hover:bg-slate-50"
          type="button"
          onClick={() => addBattery(item.battery_id)}
        >
          Thêm pin
        </button>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        <StatusBadge status={item.status} />
        <ConfidenceBadge confidence={item.best_confidence} />
        <SourceBadge sourceType={item.best_source_type} />
        {inInventory ? <Badge tone="green">Có trong kho của tôi</Badge> : <Badge tone="gray">Chưa có trong kho</Badge>}
      </div>

      {item.notes.length ? <p className="mt-3 text-sm leading-6 text-slate-600">{item.notes[0]}</p> : null}
      <SourceDisclosure compatibility={item} />
    </div>
  );
}

function ResultKindBadge({ result }: { result: LookupResult }) {
  if (result.kind === "camera") return <Badge tone="green">Máy đã có dữ liệu pin</Badge>;
  if (result.kind === "battery") return <Badge tone="blue">Kết quả theo pin</Badge>;
  if (result.kind === "unresolved") return <Badge tone="gray">Chưa xác minh pin</Badge>;
  return <Badge tone="red">Không tìm thấy</Badge>;
}

function formatCategory(category: string): string {
  return {
    point_and_shoot: "Máy ngắm chụp",
    travel_zoom: "Zoom du lịch",
    bridge_superzoom: "Bridge / siêu zoom",
    premium_compact: "Compact cao cấp",
    waterproof_compact: "Chống nước",
    large_sensor_compact: "Cảm biến lớn",
    "3d_compact": "Compact 3D",
  }[category] ?? category;
}

function formatUnresolvedReason(reason?: string): string {
  if (!reason) return "Đã xác nhận model tồn tại, nhưng chưa có nguồn xác minh pin.";
  const translations: Record<string, string> = {
    "Camera existence confirmed, battery not yet source-verified": "Đã xác nhận model tồn tại, nhưng chưa có nguồn xác minh pin.",
    "Checked source but exact model match was not confirmed.": "Đã kiểm tra nguồn, nhưng chưa xác nhận được đúng model.",
    "Direct research attempted; source found but no explicit battery text was extracted.": "Đã nghiên cứu trực tiếp; tìm thấy nguồn nhưng chưa trích được thông tin pin rõ ràng.",
    "Checked source but no explicit battery/power mapping was extracted.": "Đã kiểm tra nguồn, nhưng chưa trích được mapping pin hoặc nguồn điện rõ ràng.",
    "Direct research attempted; manual mirror exposed no explicit battery/power source.": "Đã kiểm tra bản sao hướng dẫn; không thấy thông tin pin hoặc nguồn điện rõ ràng.",
    "Direct research attempted; optional charger listing is not compatibility evidence.": "Nguồn chỉ liệt kê bộ sạc tùy chọn, chưa đủ chứng minh pin tương thích.",
    "Direct research attempted; rechargeable battery without model is insufficient.": "Nguồn chỉ nói pin sạc mà không có mã pin cụ thể, chưa đủ xác minh.",
    "Direct research attempted; readable manual section did not specify an exact battery model or cell quantity.": "Phần hướng dẫn đọc được không nêu mã pin hoặc số lượng viên pin chính xác.",
    "Direct research attempted; battery compartment mention alone does not verify compatibility.": "Thông tin về khoang pin không đủ để xác minh pin tương thích.",
    "Direct research attempted; accessory listing is not accepted as primary battery evidence.": "Danh sách phụ kiện chưa đủ điều kiện xác minh pin chính.",
  };
  if (reason.startsWith("Battery source check failed: TimeoutError")) {
    return "Không thể kiểm tra nguồn pin do kết nối hết thời gian chờ.";
  }
  return translations[reason] ?? reason;
}
