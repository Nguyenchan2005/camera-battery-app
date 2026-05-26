import { useEffect, useMemo, useState } from "react";
import type { SearchEntityType, SearchMatch } from "../types/database";

type SearchTab = "all" | SearchEntityType;

const tabs: Array<{ id: SearchTab; label: string }> = [
  { id: "all", label: "Tất cả" },
  { id: "camera", label: "Máy có pin" },
  { id: "battery", label: "Pin" },
  { id: "unresolved_candidate", label: "Chưa xác minh pin" },
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
  const [showSuggestions, setShowSuggestions] = useState(true);
  const compactLength = query.replace(/[^a-z0-9]/gi, "").length;
  const activeSuggestions = useMemo(() => suggestionsByTab[activeTab], [activeTab, suggestionsByTab]);

  useEffect(() => {
    setActiveIndex(0);
  }, [activeTab, query]);

  function commitSelected() {
    setShowSuggestions(false);
    if (activeSuggestions[activeIndex]) {
      onSelect(activeSuggestions[activeIndex]);
    } else {
      onSubmit();
    }
  }

  return (
    <section data-testid="search-box" className="rounded-lg border border-slate-200 bg-white p-5 shadow-soft sm:p-6">
      <div className="mb-4">
        <h2 className="text-lg font-semibold text-slate-950">Tra cứu</h2>
        <p className="mt-1 text-sm text-slate-600">Tên máy ảnh, tên vùng, biệt danh model hoặc mã pin</p>
      </div>
      <div className="flex flex-col gap-3 sm:flex-row">
        <label className="sr-only" htmlFor="camera-battery-search">Máy ảnh hoặc pin</label>
        <input
          id="camera-battery-search"
          data-testid="search-input"
          className="min-h-12 flex-1 rounded-md border border-slate-300 px-4 text-base outline-none transition focus:border-teal-600 focus:ring-4 focus:ring-teal-100"
          placeholder='Canon G7 X Mark III, Sony RX100 VII, NB-13L...'
          value={query}
          onChange={(event) => {
            setShowSuggestions(true);
            onQueryChange(event.target.value);
          }}
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
          className="min-h-12 rounded-md bg-teal-700 px-5 text-sm font-semibold text-white transition hover:bg-teal-800"
          type="button"
          onClick={() => {
            setShowSuggestions(false);
            onSubmit();
          }}
        >
          Tìm kiếm
        </button>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            data-testid={`search-tab-${tab.id}`}
            className={`rounded-md border px-3 py-2 text-sm font-medium transition ${
              activeTab === tab.id
                ? "border-teal-700 bg-teal-700 text-white"
                : "border-slate-200 bg-white text-slate-700 hover:border-teal-200 hover:bg-teal-50"
            }`}
            type="button"
            onClick={() => {
              setShowSuggestions(true);
              setActiveTab(tab.id);
            }}
          >
            {tab.label} ({suggestionsByTab[tab.id].length})
          </button>
        ))}
      </div>

      {compactLength > 0 && compactLength < 2 ? (
        <div data-testid="short-query-hint" className="mt-4 rounded-md bg-slate-50 p-4 text-sm text-slate-600">
          Từ khóa quá ngắn. Hãy nhập model hoặc mã pin cụ thể hơn, ví dụ: G7X III, RX100 VII, NB13L, NPBX1.
        </div>
      ) : null}

      {showSuggestions && compactLength >= 2 && activeSuggestions.length ? (
        <div data-testid="search-suggestions" className="mt-4 grid gap-2">
          {activeSuggestions.map((match, index) => (
            <button
              key={`${match.type}-${match.id}`}
              data-testid={`search-result-${match.type}-${match.id}`}
              className={`rounded-md border px-3 py-2 text-left transition ${
                index === activeIndex ? "border-teal-500 bg-teal-50" : "border-slate-200 hover:border-teal-300 hover:bg-teal-50"
              }`}
              type="button"
              onClick={() => {
                setShowSuggestions(false);
                onSelect(match);
              }}
            >
              <div className="flex items-center justify-between gap-3">
                <span className="font-medium text-slate-900">{match.label}</span>
                <span className="rounded-full bg-slate-100 px-2 py-1 text-xs text-slate-600">
                  {match.type === "camera" ? "Đã có pin" : match.type === "battery" ? "Pin" : "Chưa xác minh"}
                </span>
              </div>
              <div className="mt-1 text-sm text-slate-500">{match.subtitle}</div>
              <div className="mt-1 text-xs text-slate-500">Khớp theo: {formatMatchReason(match.matchReason)}</div>
            </button>
          ))}
        </div>
      ) : null}

      {showSuggestions && compactLength >= 2 && !activeSuggestions.length ? (
        <div data-testid="no-suggestions" className="mt-4 rounded-md border border-dashed border-slate-300 p-4 text-sm text-slate-500">
          Không có gợi ý trong nhóm này.
        </div>
      ) : null}
    </section>
  );
}

export function formatMatchReason(reason: string): string {
  return {
    "exact alias": "tên hoặc bí danh chính xác",
    "generated alias": "tên viết tắt",
    "compact alias": "dạng viết liền",
    "fuzzy fallback": "kết quả gần đúng",
    "fuzzy match": "kết quả gần đúng",
  }[reason] ?? reason;
}
