import { useMemo, useState } from "react";
import type { CameraBatteryDatabase } from "../lib/database";
import { confidenceLabel, sourceTypeLabel } from "./Badge";
import type { Confidence, SourceType } from "../types/database";

export function DatabaseStats({ db }: { db: CameraBatteryDatabase }) {
  const [open, setOpen] = useState(false);
  const brandCoverage = useMemo(() => db.getBrandCoverage(), [db]);
  const sourceQuality = useMemo(() => db.getSourceQualityBreakdown(), [db]);

  return (
    <section data-testid="database-stats" className="rounded-lg border border-slate-200 bg-white p-5 shadow-soft">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-950">Thống kê dữ liệu</h2>
          <p data-testid="last-data-update" className="text-sm text-slate-500">
            Cập nhật dữ liệu gần nhất: {db.dataSummary.lastDataUpdate ?? "Chưa có"}
          </p>
          <p data-testid="app-build-version" className="text-xs text-slate-500">
            Phiên bản ứng dụng: {__APP_BUILD_VERSION__}
          </p>
        </div>
        <button
          data-testid="toggle-database-stats"
          className="rounded-md border border-slate-300 px-3 py-2 text-sm font-medium hover:bg-slate-50"
          type="button"
          onClick={() => setOpen((value) => !value)}
        >
          {open ? "Ẩn chi tiết" : "Xem chi tiết"}
        </button>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-2 text-sm sm:grid-cols-4 lg:grid-cols-7">
        <Metric label="Máy có pin" value={db.dataSummary.verifiedCameras} />
        <Metric label="Catalog" value={db.dataSummary.candidates} />
        <Metric label="Chưa xác minh" value={db.dataSummary.unresolved} />
        <Metric label="Pin" value={db.dataSummary.batteries} />
        <Metric label="Liên kết" value={db.dataSummary.compatibilityRows} />
        <Metric label="Nguồn" value={db.dataSummary.sources} />
        <Metric label="Gợi ý" value={db.dataSummary.suggestions} />
      </div>

      {open ? (
        <div className="mt-5 grid gap-5 xl:grid-cols-[1.2fr_0.8fr]">
          <div className="overflow-auto">
            <h3 className="mb-2 text-sm font-semibold uppercase text-slate-500">Mức độ bao phủ theo hãng</h3>
            <table data-testid="brand-coverage-table" className="min-w-full text-left text-sm">
              <thead className="border-b border-slate-200 text-xs uppercase text-slate-500">
                <tr>
                  <th className="py-2 pr-3">Hãng</th>
                  <th className="py-2 pr-3 text-right">Catalog</th>
                  <th className="py-2 pr-3 text-right">Có pin</th>
                  <th className="py-2 pr-3 text-right">Chưa rõ</th>
                  <th className="py-2 pr-3 text-right">Liên kết</th>
                  <th className="py-2 text-right">Nguồn</th>
                </tr>
              </thead>
              <tbody>
                {brandCoverage.map((row) => (
                  <tr key={row.brand} className="border-b border-slate-100">
                    <td className="py-2 pr-3 font-medium text-slate-900">{row.brand}</td>
                    <td className="py-2 pr-3 text-right">{row.totalCandidates}</td>
                    <td className="py-2 pr-3 text-right">{row.verifiedCameras}</td>
                    <td className="py-2 pr-3 text-right">{row.unresolvedModels}</td>
                    <td className="py-2 pr-3 text-right">{row.compatibilityRows}</td>
                    <td className="py-2 text-right">{row.sourceCount}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div>
            <h3 className="mb-2 text-sm font-semibold uppercase text-slate-500">Chất lượng nguồn mapping</h3>
            <div data-testid="source-quality-breakdown" className="space-y-2">
              {sourceQuality.map((row) => (
                <div key={row.label} className="flex items-center justify-between rounded-md border border-slate-200 px-3 py-2 text-sm">
                  <span className="text-slate-700">{formatQualityLabel(row.label)}</span>
                  <strong className="text-slate-950">{row.count}</strong>
                </div>
              ))}
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}

function formatQualityLabel(label: string): string {
  const [source, confidence] = label.split(" / ") as [SourceType, Confidence];
  return `${sourceTypeLabel(source)} / ${confidenceLabel(confidence)}`;
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-center">
      <div className="text-lg font-semibold text-slate-950">{value.toLocaleString("vi-VN")}</div>
      <div className="text-xs text-slate-500">{label}</div>
    </div>
  );
}
