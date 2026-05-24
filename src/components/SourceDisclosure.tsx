import { useState } from "react";
import { ConfidenceBadge, SourceBadge } from "./Badge";
import type { GroupedCompatibility } from "../types/database";

export function SourceDisclosure({ compatibility }: { compatibility: GroupedCompatibility }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="mt-4 border-t border-slate-200 pt-3">
      <button
        data-testid="source-toggle"
        className="text-sm font-semibold text-slate-700 underline-offset-4 hover:text-slate-950 hover:underline"
        type="button"
        onClick={() => setOpen((current) => !current)}
      >
        {open ? "An nguon xac minh" : `Nguon xac minh (${compatibility.sources.length})`}
      </button>
      {open ? (
        <div data-testid="source-list" className="mt-3 space-y-3">
          {compatibility.sources.map((source) => (
            <div key={`${source.source_url}-${source.source_name}`} data-testid="source-row" className="rounded-md border border-slate-200 bg-white p-3">
              <div className="flex flex-wrap gap-2">
                <SourceBadge sourceType={source.source_type} />
                <ConfidenceBadge confidence={source.confidence} />
                <span className="text-xs text-slate-500">verified {source.last_verified}</span>
              </div>
              <a
                className="mt-2 block break-words text-sm font-medium text-sky-700 hover:text-sky-900"
                href={source.source_url}
                rel="noreferrer"
                target="_blank"
              >
                {source.source_name}
              </a>
              <p className="mt-2 text-sm leading-6 text-slate-600">{source.note}</p>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
