export type LensType = "fixed_lens";

export type BatterySystem =
  | "proprietary_li_ion"
  | "aa"
  | "aaa"
  | "built_in"
  | "special"
  | "unknown";

export type CompatibilityStatus =
  | "fully_compatible"
  | "partially_compatible"
  | "uses_aa"
  | "uses_aaa"
  | "built_in_battery"
  | "unknown";

export type Confidence = "high" | "medium" | "low";

export type SourceType =
  | "official_manual"
  | "official_accessory_page"
  | "trusted_database"
  | "manual_mirror"
  | "retailer"
  | "third_party_chart"
  | "unknown";

export type CandidateStatus = "verified_battery" | "unresolved";

export interface Camera {
  camera_id: string;
  brand: string;
  series: string;
  model: string;
  display_name: string;
  aliases: string[];
  regional_names: Record<string, string[]>;
  release_year: number | null;
  category: string;
  lens_type: LensType;
  battery_system: BatterySystem;
  notes: string;
}

export interface Battery {
  battery_id: string;
  brand: string;
  model: string;
  aliases: string[];
  chemistry: string | null;
  voltage: number | null;
  capacity_mah: number | null;
  notes: string;
}

export interface Compatibility {
  camera_id: string;
  battery_id: string;
  status: CompatibilityStatus;
  quantity_required: number | null;
  note: string;
  source_name: string;
  source_url: string;
  source_type: SourceType;
  confidence: Confidence;
  last_verified: string;
}

export interface CameraCandidate extends Camera {
  candidate_source_name: string;
  candidate_source_url: string;
  candidate_source_type: SourceType;
  candidate_batch: string;
  candidate_status: CandidateStatus;
}

export interface Source {
  source_id: string;
  source_name: string;
  source_url: string;
  source_type: SourceType;
  publisher: string;
  last_verified: string;
  notes: string;
}

export interface UnresolvedModel {
  camera_id: string;
  display_name: string;
  brand: string;
  series: string;
  release_year: number | null;
  reason: string;
  candidate_source_name: string;
  candidate_source_url: string;
  checked_source_urls: string[];
  last_checked: string;
}

export interface GroupedCompatibilitySource {
  source_name: string;
  source_url: string;
  source_type: SourceType;
  confidence: Confidence;
  last_verified: string;
  note: string;
}

export interface GroupedCompatibility {
  camera_id: string;
  battery_id: string;
  status: CompatibilityStatus;
  quantity_required: number | null;
  notes: string[];
  sources: GroupedCompatibilitySource[];
  best_confidence: Confidence;
  best_source_type: SourceType;
}

export type SearchEntityType = "camera" | "battery" | "unresolved_candidate";

export interface SearchMatch {
  type: SearchEntityType;
  id: string;
  label: string;
  subtitle: string;
  score: number;
  exact: boolean;
  matchReason: string;
}

export interface DataBundle {
  cameras: Camera[];
  batteries: Battery[];
  compatibility: Compatibility[];
  cameraCandidates: CameraCandidate[];
  sources: Source[];
  unresolvedModels: UnresolvedModel[];
}

export type LookupResult =
  | {
      kind: "camera";
      camera: Camera;
      compatibility: GroupedCompatibility[];
    }
  | {
      kind: "battery";
      battery: Battery;
      cameras: Array<{ camera: Camera; compatibility: GroupedCompatibility[] }>;
    }
  | {
      kind: "unresolved";
      candidate: CameraCandidate;
      unresolved?: UnresolvedModel;
    }
  | {
      kind: "unknown";
      query: string;
    };

export interface RuntimeValidationIssue {
  severity: "warning" | "error";
  message: string;
  rowId?: string;
}
