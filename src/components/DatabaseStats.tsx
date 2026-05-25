import { useMemo, useState } from "react";
import type { CameraBatteryDatabase } from "../lib/database";

export function DatabaseStats({ db }: { db: CameraBatteryDatabase }) {
  const [open, setOpen] = useState(false);
  const brandCoverage = useMemo(() => db.getBrandCoverage(), [db]);
  const sourceQuality = useMemo(() => db.getSourceQualityBreakdown(), [db]);

  return (
    <section data-testid="database-stats" className="rounded-lg border border-slate-200 bg-white p-5 shadow-soft">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-950">Thong ke database</h2>
          <p data-testid="last-data-update" className="text-sm text-slate-500">
            Last data update: {db.dataSummary.lastDataUpdate ?? "unknown"}
          </p>
          <p data-testid="app-build-version" className="text-xs text-slate-500">
            App build version: {__APP_BUILD_VERSION__}
          </p>
        </div>
        <button
          data-testid="toggle-database-stats"
          className="rounded-md border border-slate-300 px-3 py-2 text-sm font-medium hover:bg-slate-50"
          type="button"
          onClick={() => setOpen((value) => !value)}
        >
          {open ? "An chi tiet" : "Xem chi tiet"}
        </button>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-2 text-sm sm:grid-cols-4 lg:grid-cols-7">
        <Metric label="Verified cameras" value={db.dataSummary.verifiedCameras} />
        <Metric label="Candidates" value={db.dataSummary.candidates} />
        <Metric label="Unresolved" value={db.dataSummary.unresolved} />
        <Metric label="Batteries" value={db.dataSummary.batteries} />
        <Metric label="Mappings" value={db.dataSummary.compatibilityRows} />
        <Metric label="Sources" value={db.dataSummary.sources} />
        <Metric label="Suggestions" value={db.dataSummary.suggestions} />
      </div>

      {open ? (
        <div className="mt-5 grid gap-5 xl:grid-cols-[1.2fr_0.8fr]">
          <div className="overflow-auto">
            <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">Coverage theo brand</h3>
            <table data-testid="brand-coverage-table" className="min-w-full text-left text-sm">
              <thead className="border-b border-slate-200 text-xs uppercase text-slate-500">
                <tr>
                  <th className="py-2 pr-3">Brand</th>
                  <th className="py-2 pr-3 text-right">Candidates</th>
                  <th className="py-2 pr-3 text-right">Verified</th>
                  <th className="py-2 pr-3 text-right">Unresolved</th>
                  <th className="py-2 pr-3 text-right">Rows</th>
                  <th className="py-2 text-right">Sources</th>
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
            <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">Source quality breakdown</h3>
            <div data-testid="source-quality-breakdown" className="space-y-2">
              {sourceQuality.map((row) => (
                <div key={row.label} className="flex items-center justify-between rounded-md border border-slate-200 px-3 py-2 text-sm">
                  <span className="text-slate-700">{row.label}</span>
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

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-center">
      <div className="text-lg font-semibold text-slate-950">{value.toLocaleString("vi-VN")}</div>
      <div className="text-xs text-slate-500">{label}</div>
    </div>
  );
}
