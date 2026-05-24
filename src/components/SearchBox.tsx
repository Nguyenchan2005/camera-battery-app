import { useEffect, useMemo, useState } from "react";
import type { SearchEntityType, SearchMatch } from "../types/database";

type SearchTab = "all" | SearchEntityType;

const tabs: Array<{ id: SearchTab; label: string }> = [
  { id: "camera", label: "Verified cameras" },
  { id: "battery", label: "Batteries" },
  { id: "unresolved_candidate", label: "Unresolved candidates" },
  { id: "all", label: "All" },
];

export function SearchBox({
  query,
  suggestionsByTab,
  onQueryChange,
  onSubmit,
  onSelect,
}: {
  query: string;
  suggestionsByTab: Record<"all" | "camera" | "battery" | "unresolved_candidate", SearchMatch[]>;
  onQueryChange: (value: string) => void;
  onSubmit: () => void;
  onSelect: (match: SearchMatch) => void;
}) {
  const [activeTab, setActiveTab] = useState<SearchTab>("all");
  const [activeIndex, setActiveIndex] = useState(0);
  const compactLength = query.replace(/[^a-z0-9]/gi, "").length;
  const activeSuggestions = useMemo(() => suggestionsByTab[activeTab], [activeTab, suggestionsByTab]);

  useEffect(() => {
    setActiveIndex(0);
  }, [activeTab, query]);

  function commitSelected() {
    if (activeSuggestions[activeIndex]) {
      onSelect(activeSuggestions[activeIndex]);
    } else {
      onSubmit();
    }
  }

  return (
    <section data-testid="search-box" className="rounded-lg border border-slate-200 bg-white p-5 shadow-soft">
      <div className="flex flex-col gap-3 sm:flex-row">
        <input
          data-testid="search-input"
          className="min-h-12 flex-1 rounded-md border border-slate-300 px-4 text-base outline-none transition focus:border-sky-500 focus:ring-4 focus:ring-sky-100"
          placeholder='Nhap "Canon G7X Mark III", "NB-13L", "RX100 VII"...'
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "ArrowDown") {
              event.preventDefault();
              setActiveIndex((current) => Math.min(current + 1, Math.max(activeSuggestions.length - 1, 0)));
            } else if (event.key === "ArrowUp") {
              event.preventDefault();
              setActiveIndex((current) => Math.max(current - 1, 0));
            } else if (event.key === "Enter") {
              event.preventDefault();
              commitSelected();
            }
          }}
        />
        <button
          data-testid="search-submit"
          className="min-h-12 rounded-md bg-slate-950 px-5 text-sm font-semibold text-white transition hover:bg-slate-800"
          type="button"
          onClick={onSubmit}
        >
          Tra cuu
        </button>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            data-testid={`search-tab-${tab.id}`}
            className={`rounded-md border px-3 py-2 text-sm font-medium transition ${
              activeTab === tab.id
                ? "border-slate-950 bg-slate-950 text-white"
                : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
            }`}
            type="button"
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label} ({suggestionsByTab[tab.id].length})
          </button>
        ))}
      </div>

      {compactLength > 0 && compactLength < 2 ? (
        <div data-testid="short-query-hint" className="mt-4 rounded-md bg-slate-50 p-4 text-sm text-slate-600">
          Query qua ngan. Hay nhap model hoac pin cu the hon, vi du: G7X III, RX100 VII, NB13L, NPBX1.
        </div>
      ) : null}

      {compactLength >= 2 && activeSuggestions.length ? (
        <div data-testid="search-suggestions" className="mt-4 grid gap-2">
          {activeSuggestions.map((match, index) => (
            <button
              key={`${match.type}-${match.id}`}
              data-testid={`search-result-${match.type}-${match.id}`}
              className={`rounded-md border px-3 py-2 text-left transition ${
                index === activeIndex ? "border-sky-400 bg-sky-50" : "border-slate-200 hover:border-sky-300 hover:bg-sky-50"
              }`}
              type="button"
              onClick={() => onSelect(match)}
            >
              <div className="flex items-center justify-between gap-3">
                <span className="font-medium text-slate-900">{match.label}</span>
                <span className="rounded-full bg-slate-100 px-2 py-1 text-xs text-slate-600">
                  {match.type === "camera" ? "verified camera" : match.type === "battery" ? "battery" : "unresolved"}
                </span>
              </div>
              <div className="mt-1 text-sm text-slate-500">{match.subtitle}</div>
              <div className="mt-1 text-xs text-slate-400">Match: {match.matchReason}</div>
            </button>
          ))}
        </div>
      ) : null}

      {compactLength >= 2 && !activeSuggestions.length ? (
        <div data-testid="no-suggestions" className="mt-4 rounded-md border border-dashed border-slate-300 p-4 text-sm text-slate-500">
          Khong co goi y trong tab nay.
        </div>
      ) : null}
    </section>
  );
}
