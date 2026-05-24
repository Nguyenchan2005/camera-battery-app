import type { SearchMatch } from "../types/database";
import type { CameraBatteryDatabase } from "./database";

export interface BulkAutoMatch {
  line: string;
  match: SearchMatch;
}

export interface BulkAmbiguousMatch {
  line: string;
  options: SearchMatch[];
  reason: string;
}

export interface BulkNotFound {
  line: string;
  reason: string;
}

export interface BulkInventoryAnalysis {
  totalLines: number;
  autoMatches: BulkAutoMatch[];
  ambiguousMatches: BulkAmbiguousMatch[];
  notFound: BulkNotFound[];
}

export function parseBulkInventoryLines(input: string): string[] {
  return input
    .split(/\r?\n/)
    .map((line) => normalizeBulkLine(line))
    .filter(Boolean);
}

export function analyzeBulkInventoryInput(input: string, db: CameraBatteryDatabase, options: { limit?: number } = {}): BulkInventoryAnalysis {
  const limit = options.limit ?? 5;
  const lines = parseBulkInventoryLines(input);
  const autoMatches: BulkAutoMatch[] = [];
  const ambiguousMatches: BulkAmbiguousMatch[] = [];
  const notFound: BulkNotFound[] = [];

  for (const line of lines) {
    const matches = db.searchAll(line, limit);
    if (!matches.length) {
      notFound.push({ line, reason: "No database match." });
      continue;
    }

    const exactMatches = matches.filter((match) => match.exact);
    if (exactMatches.length === 1) {
      autoMatches.push({ line, match: exactMatches[0] });
      continue;
    }

    ambiguousMatches.push({
      line,
      options: matches,
      reason: exactMatches.length > 1 ? "Multiple exact matches." : "No exact match; manual choice required.",
    });
  }

  return {
    totalLines: lines.length,
    autoMatches,
    ambiguousMatches,
    notFound,
  };
}

function normalizeBulkLine(line: string): string {
  return line
    .trim()
    .replace(/^[-*]\s+/, "")
    .replace(/^\d+[.)]\s+/, "")
    .replace(/\s+/g, " ")
    .trim();
}
