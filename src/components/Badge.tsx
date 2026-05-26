import type React from "react";
import type { Confidence, CompatibilityStatus, SourceType } from "../types/database";

type BadgeTone = "green" | "yellow" | "orange" | "gray" | "red" | "blue";

const toneClass: Record<BadgeTone, string> = {
  green: "border-emerald-200 bg-emerald-50 text-emerald-700",
  yellow: "border-amber-200 bg-amber-50 text-amber-800",
  orange: "border-orange-200 bg-orange-50 text-orange-700",
  gray: "border-slate-200 bg-slate-100 text-slate-700",
  red: "border-rose-200 bg-rose-50 text-rose-700",
  blue: "border-sky-200 bg-sky-50 text-sky-700",
};

export function Badge({ children, tone }: { children: React.ReactNode; tone: BadgeTone }) {
  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-medium ${toneClass[tone]}`}>
      {children}
    </span>
  );
}

export function ConfidenceBadge({ confidence }: { confidence: Confidence }) {
  const tone: BadgeTone = confidence === "high" ? "green" : confidence === "medium" ? "yellow" : "orange";
  return <Badge tone={tone}>{confidenceLabel(confidence)}</Badge>;
}

export function StatusBadge({ status }: { status: CompatibilityStatus }) {
  const tone: BadgeTone =
    status === "fully_compatible" || status === "uses_aa" || status === "uses_aaa" ? "green" : status === "unknown" ? "gray" : "blue";
  return <Badge tone={tone}>{statusLabel(status)}</Badge>;
}

export function SourceBadge({ sourceType }: { sourceType: SourceType }) {
  const tone: BadgeTone = sourceType.startsWith("official") ? "green" : sourceType === "trusted_database" ? "yellow" : "orange";
  return <Badge tone={tone}>{sourceTypeLabel(sourceType)}</Badge>;
}

export function confidenceLabel(confidence: Confidence): string {
  return {
    high: "Tin cậy cao",
    medium: "Tin cậy vừa",
    low: "Tin cậy thấp",
  }[confidence];
}

export function statusLabel(status: CompatibilityStatus): string {
  return {
    fully_compatible: "Tương thích",
    partially_compatible: "Tương thích một phần",
    uses_aa: "Dùng pin AA",
    uses_aaa: "Dùng pin AAA",
    built_in_battery: "Pin tích hợp",
    unknown: "Chưa rõ",
  }[status];
}

export function sourceTypeLabel(sourceType: SourceType): string {
  return {
    official_manual: "Hướng dẫn chính hãng",
    official_accessory_page: "Trang phụ kiện chính hãng",
    trusted_database: "Cơ sở dữ liệu uy tín",
    manual_mirror: "Bản sao hướng dẫn",
    retailer: "Nhà bán lẻ",
    third_party_chart: "Nguồn bên thứ ba",
    unknown: "Nguồn chưa rõ",
  }[sourceType];
}
