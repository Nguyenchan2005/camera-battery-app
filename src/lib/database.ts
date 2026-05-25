import Fuse from "fuse.js";
import type {
  Battery,
  BatterySuggestion,
  Camera,
  CameraCandidate,
  Compatibility,
  Confidence,
  DataBundle,
  GroupedCompatibility,
  GroupedCompatibilitySource,
  LookupResult,
  RuntimeValidationIssue,
  Source,
  SearchEntityType,
  SearchMatch,
  SourceType,
  UnresolvedModel,
} from "../types/database";

type SearchIndexItem = {
  type: SearchEntityType;
  id: string;
  label: string;
  subtitle: string;
  terms: string[];
  searchText: string;
  compactTerms: string[];
  compactTermReasons: Record<string, string>;
};

type TermEntry = {
  term: string;
  reason: "exact alias" | "generated alias" | "compact alias";
};

type SearchBucket = "all" | "camera" | "battery";
type FetchJson = <T>(url: string) => Promise<T>;

const DATA_FILES = {
  cameras: "cameras.json",
  batteries: "batteries.json",
  compatibility: "compatibility.json",
  cameraCandidates: "camera_candidates.json",
  sources: "sources.json",
  unresolvedModels: "unresolved_models.json",
  batterySuggestions: "battery_suggestions.json",
} as const;

const confidenceRank: Record<Confidence, number> = { high: 3, medium: 2, low: 1 };

const sourceRank: Record<SourceType, number> = {
  official_manual: 6,
  official_accessory_page: 5,
  trusted_database: 4,
  manual_mirror: 3,
  retailer: 2,
  third_party_chart: 1,
  unknown: 0,
};

export async function loadDataBundle(options: { baseUrl?: string; fetchJson?: FetchJson } = {}): Promise<DataBundle> {
  const baseUrl = (options.baseUrl ?? "/data").replace(/\/$/, "");
  const fetchJson = options.fetchJson ?? defaultFetchJson;
  const [cameras, batteries, compatibility, cameraCandidates, sources, unresolvedModels, batterySuggestions] = await Promise.all([
    fetchJson<Camera[]>(`${baseUrl}/${DATA_FILES.cameras}`),
    fetchJson<Battery[]>(`${baseUrl}/${DATA_FILES.batteries}`),
    fetchJson<Compatibility[]>(`${baseUrl}/${DATA_FILES.compatibility}`),
    fetchJson<CameraCandidate[]>(`${baseUrl}/${DATA_FILES.cameraCandidates}`),
    fetchJson<Source[]>(`${baseUrl}/${DATA_FILES.sources}`),
    fetchJson<UnresolvedModel[]>(`${baseUrl}/${DATA_FILES.unresolvedModels}`),
    fetchJson<BatterySuggestion[]>(`${baseUrl}/${DATA_FILES.batterySuggestions}`),
  ]);
  const bundle = { cameras, batteries, compatibility, cameraCandidates, sources, unresolvedModels, batterySuggestions };
  validateBundleShape(bundle);
  return bundle;
}

async function defaultFetchJson<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to load ${url}: HTTP ${response.status}`);
  }
  return (await response.json()) as T;
}

function validateBundleShape(bundle: DataBundle): void {
  const arrays: Array<[keyof DataBundle, unknown]> = [
    ["cameras", bundle.cameras],
    ["batteries", bundle.batteries],
    ["compatibility", bundle.compatibility],
    ["cameraCandidates", bundle.cameraCandidates],
    ["sources", bundle.sources],
    ["unresolvedModels", bundle.unresolvedModels],
    ["batterySuggestions", bundle.batterySuggestions],
  ];
  for (const [name, value] of arrays) {
    if (!Array.isArray(value)) {
      throw new Error(`Schema mismatch: ${String(name)} must be a JSON array.`);
    }
  }

  const requiredSamples: Array<[string, unknown, string[]]> = [
    ["cameras.json", bundle.cameras[0], ["camera_id", "display_name"]],
    ["batteries.json", bundle.batteries[0], ["battery_id", "model"]],
    ["compatibility.json", bundle.compatibility[0], ["camera_id", "battery_id", "source_url"]],
    ["camera_candidates.json", bundle.cameraCandidates[0], ["camera_id", "candidate_status"]],
    ["sources.json", bundle.sources[0], ["source_id", "source_url"]],
    ["unresolved_models.json", bundle.unresolvedModels[0], ["camera_id", "reason"]],
  ];
  for (const [fileName, sample, keys] of requiredSamples) {
    if (!sample || typeof sample !== "object") {
      throw new Error(`Schema mismatch: ${fileName} is empty or does not contain objects.`);
    }
    for (const key of keys) {
      if (!(key in sample)) {
        throw new Error(`Schema mismatch: ${fileName} row is missing ${key}.`);
      }
    }
  }
  if (bundle.batterySuggestions.length) {
    const sample = bundle.batterySuggestions[0];
    for (const key of ["camera_id", "suggested_battery_model", "source_url", "warning"]) {
      if (!(key in sample)) {
        throw new Error(`Schema mismatch: battery_suggestions.json row is missing ${key}.`);
      }
    }
  }
}

export function createDatabase(data: DataBundle): CameraBatteryDatabase {
  return new CameraBatteryDatabase(data);
}

export class CameraBatteryDatabase {
  readonly cameras: Camera[];
  readonly batteries: Battery[];
  readonly compatibility: Compatibility[];
  readonly cameraCandidates: CameraCandidate[];
  readonly sources: Source[];
  readonly unresolvedModels: UnresolvedModel[];
  readonly batterySuggestions: BatterySuggestion[];

  readonly camerasById: Map<string, Camera>;
  readonly batteriesById: Map<string, Battery>;
  readonly candidatesById: Map<string, CameraCandidate>;
  readonly unresolvedByCameraId: Map<string, UnresolvedModel>;
  readonly compatibilityByCameraId: Map<string, Compatibility[]>;
  readonly compatibilityByBatteryId: Map<string, Compatibility[]>;
  readonly suggestionsByCameraId: Map<string, BatterySuggestion[]>;

  private readonly allSearchItems: SearchIndexItem[];
  private readonly cameraSearchItems: SearchIndexItem[];
  private readonly batterySearchItems: SearchIndexItem[];
  private readonly unresolvedSearchItems: SearchIndexItem[];
  private readonly allFuse: Fuse<SearchIndexItem>;
  private readonly cameraFuse: Fuse<SearchIndexItem>;
  private readonly batteryFuse: Fuse<SearchIndexItem>;

  readonly dataSummary: {
    verifiedCameras: number;
    batteries: number;
    compatibilityRows: number;
    candidates: number;
    unresolved: number;
    sources: number;
    suggestions: number;
    lastDataUpdate: string | null;
  };

  constructor(data: DataBundle) {
    this.cameras = data.cameras;
    this.batteries = data.batteries;
    this.compatibility = data.compatibility;
    this.cameraCandidates = data.cameraCandidates;
    this.sources = data.sources;
    this.unresolvedModels = data.unresolvedModels;
    this.batterySuggestions = data.batterySuggestions ?? [];

    this.camerasById = mapById(this.cameras, "camera_id");
    this.batteriesById = mapById(this.batteries, "battery_id");
    this.candidatesById = mapById(this.cameraCandidates, "camera_id");
    this.unresolvedByCameraId = mapById(this.unresolvedModels, "camera_id");
    this.compatibilityByCameraId = groupRowsBy(this.compatibility, (row) => row.camera_id);
    this.compatibilityByBatteryId = groupRowsBy(this.compatibility, (row) => row.battery_id);
    this.suggestionsByCameraId = groupRowsBy(this.batterySuggestions, (row) => row.camera_id);

    const verifiedCameraIds = new Set(this.cameras.map((camera) => camera.camera_id));
    const unresolvedCandidates = this.cameraCandidates.filter((candidate) => !verifiedCameraIds.has(candidate.camera_id));

    this.cameraSearchItems = this.cameras.map((camera) => makeCameraSearchItem(camera, "camera"));
    this.batterySearchItems = this.batteries.map(makeBatterySearchItem);
    this.unresolvedSearchItems = unresolvedCandidates.map((candidate) => makeCameraSearchItem(candidate, "unresolved_candidate"));
    this.allSearchItems = [...this.cameraSearchItems, ...this.batterySearchItems, ...this.unresolvedSearchItems];

    this.allFuse = makeFuse(this.allSearchItems);
    this.cameraFuse = makeFuse(this.cameraSearchItems);
    this.batteryFuse = makeFuse(this.batterySearchItems);

    this.dataSummary = {
      verifiedCameras: this.cameras.length,
      batteries: this.batteries.length,
      compatibilityRows: this.compatibility.length,
      candidates: this.cameraCandidates.length,
      unresolved: this.unresolvedModels.length,
      sources: this.sources.length,
      suggestions: this.batterySuggestions.length,
      lastDataUpdate: latestDate([
        ...this.compatibility.map((row) => row.last_verified),
        ...this.sources.map((source) => source.last_verified),
        ...this.unresolvedModels.map((row) => row.last_checked),
      ]),
    };
  }

  searchAll(query: string, limit = 12): SearchMatch[] {
    return this.runSearch("all", query, limit);
  }

  searchCamera(query: string, limit = 10): SearchMatch[] {
    return this.runSearch("camera", query, limit);
  }

  searchBattery(query: string, limit = 10): SearchMatch[] {
    return this.runSearch("battery", query, limit);
  }

  searchByType(query: string, type: SearchEntityType | "all", limit = 12): SearchMatch[] {
    if (type === "all") {
      return this.searchAll(query, limit);
    }
    return this.searchAll(query, limit * 3).filter((match) => match.type === type).slice(0, limit);
  }

  getSearchTabs(query: string): Record<"all" | "camera" | "battery" | "unresolved_candidate", SearchMatch[]> {
    const all = this.searchAll(query, 16);
    return {
      all,
      camera: all.filter((match) => match.type === "camera"),
      battery: all.filter((match) => match.type === "battery"),
      unresolved_candidate: all.filter((match) => match.type === "unresolved_candidate"),
    };
  }

  getCameraBatteryCompatibility(cameraId: string): GroupedCompatibility[] {
    if (!this.camerasById.has(cameraId)) {
      return [];
    }
    return this.groupCompatibilityRows(this.compatibilityByCameraId.get(cameraId) ?? []);
  }

  getBatteryCompatibleCameras(batteryId: string): Array<{ camera: Camera; compatibility: GroupedCompatibility[] }> {
    if (!this.batteriesById.has(batteryId)) {
      return [];
    }
    const rows = this.compatibilityByBatteryId.get(batteryId) ?? [];
    const rowsByCamera = groupRowsBy(rows, (row) => row.camera_id);
    return [...rowsByCamera.entries()]
      .map(([cameraId, cameraRows]) => {
        const camera = this.camerasById.get(cameraId);
        if (!camera) {
          return null;
        }
        return { camera, compatibility: this.groupCompatibilityRows(cameraRows) };
      })
      .filter((row): row is { camera: Camera; compatibility: GroupedCompatibility[] } => Boolean(row))
      .sort((a, b) => a.camera.display_name.localeCompare(b.camera.display_name));
  }

  getBatterySuggestionsForCandidate(cameraId: string): BatterySuggestion[] {
    return this.suggestionsByCameraId.get(cameraId) ?? [];
  }

  getBatterySuggestionsForBattery(batteryId: string): BatterySuggestion[] {
    return this.batterySuggestions.filter((row) => row.suggested_battery_id === batteryId);
  }

  getCandidateStatus(cameraId: string):
    | { status: "verified"; camera: Camera; candidate?: CameraCandidate }
    | { status: "unresolved"; candidate: CameraCandidate; unresolved?: UnresolvedModel }
    | { status: "unknown" } {
    const camera = this.camerasById.get(cameraId);
    if (camera) {
      return { status: "verified", camera, candidate: this.candidatesById.get(cameraId) };
    }

    const candidate = this.candidatesById.get(cameraId);
    if (candidate) {
      return { status: "unresolved", candidate, unresolved: this.unresolvedByCameraId.get(cameraId) };
    }

    return { status: "unknown" };
  }

  getMyCompatibleBatteries(cameraId: string, myBatteryIds: string[]): GroupedCompatibility[] {
    const myBatterySet = new Set(myBatteryIds);
    return this.getCameraBatteryCompatibility(cameraId).filter((row) => myBatterySet.has(row.battery_id));
  }

  getMyCompatibleCameras(batteryId: string, myCameraIds: string[]): Camera[] {
    const myCameraSet = new Set(myCameraIds);
    return this.getBatteryCompatibleCameras(batteryId)
      .map((row) => row.camera)
      .filter((camera) => myCameraSet.has(camera.camera_id));
  }

  resolveLookup(query: string): LookupResult {
    const matches = this.searchAll(query, 1);
    if (!matches.length) {
      return { kind: "unknown", query };
    }
    return this.lookupFromMatch(matches[0], query);
  }

  lookupFromMatch(match: SearchMatch | null | undefined, query = ""): LookupResult {
    if (!match) {
      return { kind: "unknown", query };
    }

    if (match.type === "camera") {
      const camera = this.camerasById.get(match.id);
      if (!camera) {
        return { kind: "unknown", query: match.label };
      }
      return { kind: "camera", camera, compatibility: this.getCameraBatteryCompatibility(camera.camera_id) };
    }

    if (match.type === "battery") {
      const battery = this.batteriesById.get(match.id);
      if (!battery) {
        return { kind: "unknown", query: match.label };
      }
      return {
        kind: "battery",
        battery,
        cameras: this.getBatteryCompatibleCameras(battery.battery_id),
        suggestions: this.getBatterySuggestionsForBattery(battery.battery_id),
      };
    }

    const candidate = this.candidatesById.get(match.id);
    if (!candidate) {
      return { kind: "unknown", query: match.label };
    }
    return {
      kind: "unresolved",
      candidate,
      unresolved: this.unresolvedByCameraId.get(candidate.camera_id),
      suggestions: this.getBatterySuggestionsForCandidate(candidate.camera_id),
    };
  }

  groupCompatibilityRows(rows: Compatibility[]): GroupedCompatibility[] {
    const grouped = new Map<string, GroupedCompatibility>();
    for (const row of rows) {
      if (!this.camerasById.has(row.camera_id) || !this.batteriesById.has(row.battery_id)) {
        continue;
      }
      const key = `${row.camera_id}::${row.battery_id}::${row.status}`;
      const source: GroupedCompatibilitySource = {
        source_name: row.source_name,
        source_url: row.source_url,
        source_type: row.source_type,
        confidence: row.confidence,
        last_verified: row.last_verified,
        note: row.note,
      };
      const existing = grouped.get(key);
      if (!existing) {
        grouped.set(key, {
          camera_id: row.camera_id,
          battery_id: row.battery_id,
          status: row.status,
          quantity_required: row.quantity_required,
          notes: dedupe([row.note]),
          sources: [source],
          best_confidence: row.confidence,
          best_source_type: row.source_type,
        });
        continue;
      }

      existing.quantity_required = existing.quantity_required ?? row.quantity_required;
      existing.notes = dedupe([...existing.notes, row.note]);
      if (!existing.sources.some((item) => item.source_url === source.source_url && item.source_name === source.source_name)) {
        existing.sources.push(source);
      }
      if (confidenceRank[row.confidence] > confidenceRank[existing.best_confidence]) {
        existing.best_confidence = row.confidence;
      }
      if (sourceRank[row.source_type] > sourceRank[existing.best_source_type]) {
        existing.best_source_type = row.source_type;
      }
    }

    return [...grouped.values()].sort((a, b) => {
      const batteryA = this.batteriesById.get(a.battery_id)?.model ?? a.battery_id;
      const batteryB = this.batteriesById.get(b.battery_id)?.model ?? b.battery_id;
      return batteryA.localeCompare(batteryB) || a.status.localeCompare(b.status);
    });
  }

  buildNaturalAnswer(result: LookupResult, context: { myCameraIds?: string[]; myBatteryIds?: string[] } = {}): string {
    if (result.kind === "camera") {
      if (!result.compatibility.length) {
        return `${result.camera.display_name} la camera verified, nhung hien chua co compatibility row hop le de hien thi.`;
      }

      const batteryNames = result.compatibility
        .map((row) => this.batteriesById.get(row.battery_id)?.model ?? row.battery_id)
        .join(", ");
      const sourceTypes = dedupe(result.compatibility.flatMap((row) => row.sources.map((source) => source.source_type))).join(" / ");
      const myMatches = this.getMyCompatibleBatteries(result.camera.camera_id, context.myBatteryIds ?? []);
      const myText = myMatches.length
        ? `Trong kho cua ban hien co ${myMatches.map((row) => this.batteriesById.get(row.battery_id)?.model ?? row.battery_id).join(", ")} nen dung duoc cho may nay.`
        : "Trong kho cua ban hien chua co pin nao duoc database xac nhan dung duoc cho may nay.";
      return `${result.camera.display_name} su dung pin/nguon ${batteryNames}. Du lieu nay da duoc xac minh tu nguon ${sourceTypes}. ${myText}`;
    }

    if (result.kind === "battery") {
      const camerasForBattery = result.cameras.map((row) => row.camera);
      if (!camerasForBattery.length) {
        return `Pin ${result.battery.model} co trong database pin, nhung hien chua co camera verified nao tro toi pin nay.`;
      }
      const shown = camerasForBattery.slice(0, 8).map((camera) => camera.display_name).join(", ");
      const remainder = camerasForBattery.length > 8 ? ` va ${camerasForBattery.length - 8} model khac` : "";
      const myMatches = this.getMyCompatibleCameras(result.battery.battery_id, context.myCameraIds ?? []);
      const myText = myMatches.length
        ? `Trong kho may cua ban, pin nay dung duoc cho ${myMatches.map((camera) => camera.display_name).join(", ")}.`
        : "Trong kho may cua ban hien chua co model nao duoc xac nhan dung pin nay.";
      return `Pin ${result.battery.model} dung duoc cho cac may verified nhu ${shown}${remainder}. ${myText}`;
    }

    if (result.kind === "unresolved") {
      const suggestionText = result.suggestions.length
        ? ` Co goi y chua xac minh (${result.suggestions.map((row) => row.suggested_battery_model).join(", ")}), nhung day khong phai compatibility verified.`
        : "";
      return `${result.candidate.display_name} co trong catalog, nhung hien database chua co nguon xac minh pin.${suggestionText} Khong nen mua pin dua tren model nay cho den khi co nguon xac minh.`;
    }

    return `Hien database chua co du lieu cho model/pin "${result.query}". Ban co the kiem tra lai cach viet hoac them vao danh sach can xac minh.`;
  }

  validateRuntimeData(): RuntimeValidationIssue[] {
    const issues: RuntimeValidationIssue[] = [];
    const candidateIds = new Set<string>();

    for (const candidate of this.cameraCandidates) {
      if (candidateIds.has(candidate.camera_id)) {
        issues.push({
          severity: "error",
          message: "Duplicate camera_id in camera_candidates.json",
          rowId: candidate.camera_id,
        });
      }
      candidateIds.add(candidate.camera_id);
    }

    for (const row of this.compatibility) {
      if (!this.camerasById.has(row.camera_id)) {
        issues.push({
          severity: "error",
          message: "Compatibility row references a missing camera_id",
          rowId: row.camera_id,
        });
      }
      if (!this.batteriesById.has(row.battery_id)) {
        issues.push({
          severity: "error",
          message: "Compatibility row references a missing battery_id",
          rowId: row.battery_id,
        });
      }
    }

    for (const unresolved of this.unresolvedModels) {
      if (!unresolved.reason || !unresolved.checked_source_urls?.length) {
        issues.push({
          severity: "warning",
          message: "Unresolved model is missing reason or checked_source_urls",
          rowId: unresolved.camera_id,
        });
      }
    }

    for (const suggestion of this.batterySuggestions) {
      if (!this.unresolvedByCameraId.has(suggestion.camera_id)) {
        issues.push({
          severity: "error",
          message: "Battery suggestion references a camera that is not unresolved",
          rowId: suggestion.camera_id,
        });
      }
      if (suggestion.suggested_battery_id && !this.batteriesById.has(suggestion.suggested_battery_id)) {
        issues.push({
          severity: "error",
          message: "Battery suggestion references a missing battery_id",
          rowId: suggestion.camera_id,
        });
      }
    }

    if (issues.length) {
      console.warn("Runtime database validation issues", issues);
    }

    return issues;
  }

  getBrandCoverage() {
    const brandSet = new Set<string>();
    for (const row of this.cameraCandidates) brandSet.add(row.brand);
    for (const row of this.cameras) brandSet.add(row.brand);
    for (const row of this.unresolvedModels) brandSet.add(row.brand);

    return [...brandSet]
      .map((brand) => {
        const cameraIds = new Set(this.cameras.filter((camera) => camera.brand === brand).map((camera) => camera.camera_id));
        return {
          brand,
          totalCandidates: this.cameraCandidates.filter((candidate) => candidate.brand === brand).length,
          verifiedCameras: cameraIds.size,
          unresolvedModels: this.unresolvedModels.filter((row) => row.brand === brand).length,
          compatibilityRows: this.compatibility.filter((row) => cameraIds.has(row.camera_id)).length,
          sourceCount: new Set(
            this.compatibility
              .filter((row) => cameraIds.has(row.camera_id))
              .map((row) => row.source_url),
          ).size,
        };
      })
      .sort((a, b) => b.totalCandidates - a.totalCandidates || a.brand.localeCompare(b.brand));
  }

  getSourceQualityBreakdown() {
    const counts = new Map<string, number>();
    for (const row of this.compatibility) {
      const key = `${row.source_type} / ${row.confidence}`;
      counts.set(key, (counts.get(key) ?? 0) + 1);
    }
    return [...counts.entries()]
      .map(([label, count]) => ({ label, count }))
      .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label));
  }

  private runSearch(bucket: SearchBucket, query: string, limit: number): SearchMatch[] {
    const items = bucket === "camera" ? this.cameraSearchItems : bucket === "battery" ? this.batterySearchItems : this.allSearchItems;
    const fuse = bucket === "camera" ? this.cameraFuse : bucket === "battery" ? this.batteryFuse : this.allFuse;
    return runSearch(fuse, items, query, limit);
  }
}

export interface AnswerEngine {
  build(result: LookupResult, context?: { myCameraIds?: string[]; myBatteryIds?: string[] }): string;
}

export class DefaultTemplateAnswerEngine implements AnswerEngine {
  constructor(private readonly db: CameraBatteryDatabase) {}

  build(result: LookupResult, context: { myCameraIds?: string[]; myBatteryIds?: string[] } = {}): string {
    return this.db.buildNaturalAnswer(result, context);
  }
}

function mapById<T extends Record<K, string>, K extends keyof T>(rows: T[], key: K): Map<string, T> {
  return new Map(rows.map((row) => [row[key], row]));
}

function groupRowsBy<T>(rows: T[], keyFn: (row: T) => string): Map<string, T[]> {
  const result = new Map<string, T[]>();
  for (const row of rows) {
    const key = keyFn(row);
    result.set(key, [...(result.get(key) ?? []), row]);
  }
  return result;
}

function latestDate(values: Array<string | null | undefined>): string | null {
  const valid = values.filter((value): value is string => Boolean(value)).sort();
  return valid.length ? valid[valid.length - 1] : null;
}

function flattenRegionalNames(regionalNames: Record<string, string[]>): string[] {
  return Object.values(regionalNames ?? {}).flat();
}

export function compactToken(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/gi, "")
    .toUpperCase();
}

function normalizeText(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[?!.:,;()[\]{}"'`]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function cleanQuery(value: string): string {
  return normalizeText(value)
    .replace(/\b(?:dung|su dung|xai|can|cho|minh|toi|cua|may anh|camera|digital camera|pin gi|pin nao)\b/gi, " ")
    .replace(/\b(?:dùng|sử dụng|xài|cần|mình|tôi|của|máy ảnh|pin gì|pin nào)\b/gi, " ")
    .replace(/\b(?:uses?|compatible|battery|batteries|what|which|for)\b/gi, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function dedupe(values: Array<string | null | undefined>): string[] {
  const seen = new Set<string>();
  const result: string[] = [];
  for (const value of values) {
    const normalized = normalizeText(value ?? "");
    const key = normalized.toLocaleLowerCase();
    if (!normalized || seen.has(key)) {
      continue;
    }
    seen.add(key);
    result.push(normalized);
  }
  return result;
}

function dedupeTermEntries(entries: TermEntry[]): TermEntry[] {
  const seen = new Map<string, TermEntry>();
  const rank: Record<TermEntry["reason"], number> = {
    "exact alias": 3,
    "generated alias": 2,
    "compact alias": 1,
  };
  for (const entry of entries) {
    const term = normalizeText(entry.term);
    if (!term) continue;
    const key = term.toLocaleLowerCase();
    const existing = seen.get(key);
    if (!existing || rank[entry.reason] > rank[existing.reason]) {
      seen.set(key, { term, reason: entry.reason });
    }
  }
  return [...seen.values()];
}

function splitNameVariants(value: string): string[] {
  const variants = new Set<string>();
  const normalized = normalizeText(value);
  if (normalized) variants.add(normalized);

  for (const piece of value.split(/[\/,;|]+/)) {
    const cleaned = normalizeText(piece);
    if (cleaned) variants.add(cleaned);
  }

  const parenPattern = /\(([^)]+)\)/g;
  let match: RegExpExecArray | null;
  while ((match = parenPattern.exec(value))) {
    const cleaned = normalizeText(match[1]);
    if (cleaned) variants.add(cleaned);
  }
  const withoutParens = normalizeText(value.replace(/\([^)]*\)/g, " "));
  if (withoutParens) variants.add(withoutParens);

  return [...variants];
}

function romanForMark(mark: string): string | null {
  const normalized = mark.toUpperCase();
  const byNumber: Record<string, string> = {
    "2": "II",
    "3": "III",
    "4": "IV",
    "5": "V",
    "6": "VI",
    "7": "VII",
  };
  return byNumber[normalized] ?? null;
}

function addGenerated(entries: TermEntry[], term: string | null | undefined): void {
  if (term && normalizeText(term)) {
    entries.push({ term, reason: "generated alias" });
  }
}

function addCompact(entries: TermEntry[], term: string | null | undefined): void {
  if (term && normalizeText(term)) {
    entries.push({ term, reason: "compact alias" });
  }
}

function expandCameraTerms(camera: Camera | CameraCandidate): TermEntry[] {
  const rawTerms = [
    camera.display_name,
    camera.model,
    camera.brand,
    camera.series,
    `${camera.brand} ${camera.model}`,
    `${camera.brand} ${camera.display_name}`,
    ...camera.aliases,
    ...flattenRegionalNames(camera.regional_names),
  ];
  const baseTerms = dedupe(rawTerms.flatMap((term) => splitNameVariants(term ?? "")));
  const expanded: TermEntry[] = baseTerms.map((term) => ({ term, reason: "exact alias" }));

  for (const term of baseTerms) {
    const noPowerShot = term.replace(/\bPowerShot\b/gi, "").replace(/\s+/g, " ").trim();
    if (noPowerShot !== term) addGenerated(expanded, noPowerShot);

    const compactG = term.replace(/\b(G\d+)\s+X\b/gi, "$1X");
    if (compactG !== term) addGenerated(expanded, compactG);

    const markMatch = term.match(/\b(.+?)\s+Mark\s+(II|III|IV|V|VI|VII)\b/i);
    if (markMatch) {
      addGenerated(expanded, `${markMatch[1]} ${markMatch[2]}`);
      addGenerated(expanded, `${markMatch[1].replace(/\s+/g, "")} ${markMatch[2]}`);
    }

    const rxMatch = term.match(/\bRX100M([2-7])A?\b/i);
    if (rxMatch) {
      const roman = romanForMark(rxMatch[1]);
      if (roman) {
        addGenerated(expanded, `RX100 ${roman}`);
        addGenerated(expanded, `Sony RX100 ${roman}`);
        addGenerated(expanded, `Sony Cyber-shot RX100 ${roman}`);
        addGenerated(expanded, `DSC-RX100 ${roman}`);
        addGenerated(expanded, `RX100 ${rxMatch[1]}`);
        addGenerated(expanded, `Sony RX100 ${rxMatch[1]}`);
      }
    }

    addCanonGeneratedTerms(expanded, term, camera.brand);
    addSonyGeneratedTerms(expanded, term);
    addNikonGeneratedTerms(expanded, term);
    addPanasonicGeneratedTerms(expanded, term);
    addFujifilmGeneratedTerms(expanded, term, camera.brand);
    addCasioGeneratedTerms(expanded, term);
    addOlympusGeneratedTerms(expanded, term);
  }

  return dedupeTermEntries(expanded);
}

function addCanonGeneratedTerms(entries: TermEntry[], term: string, brand: string): void {
  const ixy = term.match(/\bIXY\s+(?:DIGITAL\s+)?([A-Z]?\d+[A-Z]?)\b/i);
  if (ixy && !hasCanonShortAliasBlockingSuffix(term, ixy)) {
    const code = ixy[1].toUpperCase();
    addGenerated(entries, `IXY ${code}`);
    addCompact(entries, `IXY${code}`);
    addGenerated(entries, `${brand} IXY ${code}`);
    addCompact(entries, `${brand} IXY${code}`);
  }

  const ixus = term.match(/\b(?:DIGITAL\s+)?IXUS\s+([A-Z]?\d+[A-Z]?)\b/i);
  if (ixus && !hasCanonShortAliasBlockingSuffix(term, ixus)) {
    const code = ixus[1].toUpperCase();
    addGenerated(entries, `IXUS ${code}`);
    addCompact(entries, `IXUS${code}`);
    addGenerated(entries, `${brand} IXUS ${code}`);
    addCompact(entries, `${brand} IXUS${code}`);
    addGenerated(entries, `Digital IXUS ${code}`);
    addCompact(entries, `Digital IXUS${code}`);
  }

  const powershot = term.match(/\bPowerShot\s+([A-Z]\d+[A-Z]?)\b/i);
  const elph = term.match(/\b([A-Z]\d+[A-Z]?)\s+(?:DIGITAL\s+)?ELPH\b/i);
  const code = (powershot?.[1] ?? elph?.[1])?.toUpperCase();
  if (code) {
    addGenerated(entries, `PowerShot ${code}`);
    addGenerated(entries, code);
    addGenerated(entries, `${code} ELPH`);
    addGenerated(entries, `${code} DIGITAL ELPH`);
    addGenerated(entries, `${brand} PowerShot ${code}`);
  }
}

function hasCanonShortAliasBlockingSuffix(term: string, match: RegExpMatchArray): boolean {
  const index = match.index ?? 0;
  const suffix = term.slice(index + match[0].length).trim();
  return /^(HS|IS|Ti|Mark|MK|II|III|IV|V|VI|VII)\b/i.test(suffix);
}

function addSonyGeneratedTerms(entries: TermEntry[], term: string): void {
  const dscMatches = [...term.matchAll(/\bDSC[-\s]?([A-Z]+\d+[A-Z0-9]*)\b/gi)];
  for (const match of dscMatches) {
    const code = match[1].toUpperCase();
    addGenerated(entries, code);
    addGenerated(entries, `Sony ${code}`);
    addGenerated(entries, `DSC ${code}`);
    addCompact(entries, `DSC${code}`);
    addGenerated(entries, `Sony DSC ${code}`);
    addCompact(entries, `Sony DSC${code}`);
    addGenerated(entries, `Cyber-shot ${code}`);
    addGenerated(entries, `Cyber shot ${code}`);
    addGenerated(entries, `Sony Cyber-shot ${code}`);

    const rx100 = code.match(/^RX100M([2-7])A?$/i);
    if (rx100) {
      const roman = romanForMark(rx100[1]);
      if (roman) {
        addGenerated(entries, `RX100 ${roman}`);
        addGenerated(entries, `Sony RX100 ${roman}`);
        addGenerated(entries, `Sony Cyber-shot RX100 ${roman}`);
        addGenerated(entries, `DSC RX100 ${roman}`);
      }
      addGenerated(entries, `RX100 ${rx100[1]}`);
      addCompact(entries, `RX100M${rx100[1]}`);
    }
  }
}

function addNikonGeneratedTerms(entries: TermEntry[], term: string): void {
  const match = term.match(/\b(?:Nikon\s+)?(?:COOLPIX|Coolpix)?\s*([A-Z]\d{2,4}[A-Z]?)\b/i);
  if (!match) return;
  const code = match[1].toUpperCase();
  addGenerated(entries, code);
  addGenerated(entries, `Nikon ${code}`);
  addGenerated(entries, `Coolpix ${code}`);
  addGenerated(entries, `COOLPIX ${code}`);
  addGenerated(entries, `Nikon COOLPIX ${code}`);
}

function addPanasonicGeneratedTerms(entries: TermEntry[], term: string): void {
  const pairs: Record<string, string> = {
    TZ90: "ZS70",
    ZS70: "TZ90",
    TZ100: "ZS100",
    ZS100: "TZ100",
    TZ200: "ZS200",
    ZS200: "TZ200",
    TZ95: "ZS80",
    ZS80: "TZ95",
    TZ80: "ZS60",
    ZS60: "TZ80",
  };
  const matches = [...term.matchAll(/\b(?:DMC|DC)?[-\s]?((?:TZ|ZS)\d+[A-Z]?)\b/gi)];
  for (const match of matches) {
    const code = match[1].toUpperCase();
    addGenerated(entries, code);
    addGenerated(entries, `Panasonic ${code}`);
    addGenerated(entries, `Lumix ${code}`);
    const paired = pairs[code];
    if (paired) {
      addGenerated(entries, paired);
      addGenerated(entries, `Panasonic ${paired}`);
      addGenerated(entries, `Lumix ${paired}`);
    }
  }
}

function addFujifilmGeneratedTerms(entries: TermEntry[], term: string, brand: string): void {
  const finepix = term.match(/\bFinePix\s+([A-Z]+\d+[A-Z0-9]*)\b/i);
  const xSeries = term.match(/\b(X(?:100|70|F10)\w*)\b/i);
  const code = (finepix?.[1] ?? xSeries?.[1])?.toUpperCase();
  if (!code) return;
  addGenerated(entries, code);
  addGenerated(entries, `Fuji ${code}`);
  addGenerated(entries, `Fujifilm ${code}`);
  if (finepix) {
    addGenerated(entries, `FinePix ${code}`);
    addGenerated(entries, `Fuji FinePix ${code}`);
    addGenerated(entries, `${brand} FinePix ${code}`);
  }
}

function addCasioGeneratedTerms(entries: TermEntry[], term: string): void {
  const matches = [...term.matchAll(/\bEX[-\s]?((?:ZR|FH|FC|TR|Z|S|H)\d{2,4}[A-Z]?)\b/gi)];
  for (const match of matches) {
    const code = match[1].toUpperCase();
    addGenerated(entries, code);
    addGenerated(entries, `Casio ${code}`);
    addGenerated(entries, `Exilim ${code}`);
    addCompact(entries, `EX${code}`);
  }
}

function addOlympusGeneratedTerms(entries: TermEntry[], term: string): void {
  const match = term.match(/\bTG[-\s]?(\d{1,2})\b/i);
  if (!match) return;
  const code = `TG${match[1]}`;
  addGenerated(entries, code);
  addGenerated(entries, `Olympus ${code}`);
  addGenerated(entries, `Tough ${code}`);
}

function expandBatteryTerms(battery: Battery): TermEntry[] {
  const terms = dedupe([
    battery.model,
    battery.brand,
    `${battery.brand} ${battery.model}`,
    ...battery.aliases,
    battery.battery_id.replace(/_/g, " "),
  ]);
  const expanded: TermEntry[] = terms.map((term) => ({ term, reason: "exact alias" }));
  for (const term of terms) {
    const compact = compactToken(term);
    if (compact.length >= 4) addCompact(expanded, compact);
    const hyphenless = term.replace(/-/g, "");
    if (hyphenless !== term) addCompact(expanded, hyphenless);
  }
  return dedupeTermEntries(expanded);
}

function makeCameraSearchItem(
  camera: Camera | CameraCandidate,
  type: "camera" | "unresolved_candidate",
): SearchIndexItem {
  const termEntries = expandCameraTerms(camera);
  const terms = termEntries.map((entry) => entry.term);
  const compactTermReasons = compactReasonMap(termEntries);
  return {
    type,
    id: camera.camera_id,
    label: camera.display_name,
    subtitle: `${camera.brand} · ${camera.series}${camera.release_year ? ` · ${camera.release_year}` : ""}`,
    terms,
    searchText: terms.join(" "),
    compactTerms: Object.keys(compactTermReasons),
    compactTermReasons,
  };
}

function makeBatterySearchItem(battery: Battery): SearchIndexItem {
  const termEntries = expandBatteryTerms(battery);
  const terms = termEntries.map((entry) => entry.term);
  const compactTermReasons = compactReasonMap(termEntries);
  return {
    type: "battery",
    id: battery.battery_id,
    label: battery.model,
    subtitle: `${battery.brand}${battery.chemistry ? ` · ${battery.chemistry}` : ""}`,
    terms,
    searchText: terms.join(" "),
    compactTerms: Object.keys(compactTermReasons),
    compactTermReasons,
  };
}

function compactReasonMap(entries: TermEntry[]): Record<string, string> {
  const rank: Record<string, number> = {
    "exact alias": 4,
    "generated alias": 3,
    "compact alias": 2,
    "compact contains": 1,
  };
  const result: Record<string, string> = {};
  for (const entry of entries) {
    const compact = compactToken(entry.term);
    if (!compact) continue;
    const current = result[compact];
    if (!current || rank[entry.reason] > rank[current]) {
      result[compact] = entry.reason;
    }
  }
  return result;
}

function makeFuse(items: SearchIndexItem[]): Fuse<SearchIndexItem> {
  return new Fuse(items, {
    keys: [
      { name: "label", weight: 0.35 },
      { name: "terms", weight: 0.45 },
      { name: "searchText", weight: 0.2 },
    ],
    includeScore: true,
    includeMatches: true,
    ignoreLocation: true,
    minMatchCharLength: 2,
    threshold: 0.34,
  });
}

function itemToMatch(item: SearchIndexItem, score: number, exact: boolean, matchReason = "exact token"): SearchMatch {
  return {
    type: item.type,
    id: item.id,
    label: item.label,
    subtitle: item.subtitle,
    score,
    exact,
    matchReason,
  };
}

function compactExactMatches(items: SearchIndexItem[], compactQuery: string): SearchMatch[] {
  if (!compactQuery) return [];
  return items
    .filter((item) => item.compactTerms.includes(compactQuery))
    .map((item) => itemToMatch(item, -1, true, item.compactTermReasons[compactQuery] ?? "compact alias"));
}

function compactContainmentMatches(items: SearchIndexItem[], compactQuery: string): SearchMatch[] {
  if (!compactQuery || compactQuery.length < 6) return [];
  const matches: SearchMatch[] = [];
  for (const item of items) {
    for (const compactTerm of item.compactTerms) {
      if (compactTerm === compactQuery) continue;
      if (isSafeCompactContainment(compactQuery, compactTerm)) {
        matches.push(itemToMatch(item, 0.05, false, "compact alias"));
        break;
      }
    }
  }
  return matches;
}

function isSafeCompactContainment(compactQuery: string, compactTerm: string): boolean {
  const shorter = compactQuery.length <= compactTerm.length ? compactQuery : compactTerm;
  const longer = compactQuery.length > compactTerm.length ? compactQuery : compactTerm;
  if (shorter.length < 6 || !longer.includes(shorter)) return false;
  if (isRiskyShortModelCompact(shorter)) return false;
  return true;
}

function isRiskyShortModelCompact(value: string): boolean {
  return /^[A-Z]{0,3}\d{1,2}[A-Z]?$/.test(value);
}

function reasonFromFuseResult(result: { matches?: readonly { key?: string }[] }): string {
  const key = result.matches?.[0]?.key ?? "";
  if (key.includes("label")) return "display/model";
  if (key.includes("terms")) return "alias/model/brand";
  if (key.includes("searchText")) return "combined text";
  return "fuzzy match";
}

function runSearch(fuse: Fuse<SearchIndexItem>, items: SearchIndexItem[], query: string, limit: number): SearchMatch[] {
  const cleaned = cleanQuery(query);
  if (!cleaned || compactToken(cleaned).length < 2) {
    return [];
  }

  const compactQuery = compactToken(cleaned);
  const exactMatches = compactExactMatches(items, compactQuery);
  const containsMatches = compactContainmentMatches(items, compactQuery);

  const fuzzyMatches = fuse.search(cleaned, { limit: limit * 3 }).map((result) => {
    const exact = Boolean(compactQuery && result.item.compactTerms.includes(compactQuery));
    return itemToMatch(
      result.item,
      result.score ?? 1,
      exact,
      exact ? result.item.compactTermReasons[compactQuery] ?? "compact alias" : `fuzzy fallback: ${reasonFromFuseResult(result)}`,
    );
  });

  const byKey = new Map<string, SearchMatch>();
  for (const match of [...exactMatches, ...containsMatches, ...fuzzyMatches]) {
    const key = `${match.type}:${match.id}`;
    const previous = byKey.get(key);
    if (!previous || match.score < previous.score || (match.exact && !previous.exact)) {
      byKey.set(key, match);
    }
  }

  return [...byKey.values()]
    .sort((a, b) => Number(b.exact) - Number(a.exact) || a.score - b.score || a.label.localeCompare(b.label))
    .slice(0, limit);
}
