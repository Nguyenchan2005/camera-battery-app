from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from importers.common import ImportContext, normalize_for_match, validate_url, write_json


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
REPORT_DIR = ROOT / "reports"
INPUT_DIR = ROOT / "research_inputs"
EVIDENCE_PATH = DATA_DIR / "researched_battery_evidence.json"
REPORT_PATH = REPORT_DIR / "manual_dpreview_batch_import_review.md"
INPUT_FILES = [
    INPUT_DIR / "researched_battery_evidence_batch.json",
    INPUT_DIR / "researched_battery_evidence_batch_2.json",
]
EXACT_DPREVIEW_PATH = re.compile(r"^/products/[^/]+/compacts/[^/]+/specifications/?$", re.I)


def load_array(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{path.relative_to(ROOT)} must contain an array")
    return data


def candidate_terms(candidate: dict[str, Any]) -> set[str]:
    terms = [candidate.get("model", ""), candidate.get("display_name", ""), *candidate.get("aliases", [])]
    for regional_names in (candidate.get("regional_names") or {}).values():
        terms.extend(regional_names)
    return {normalize_for_match(term) for term in terms if term}


def input_terms(row: dict[str, Any]) -> set[str]:
    model = row.get("camera_model", "")
    brand = row.get("brand", "")
    return {normalize_for_match(model), normalize_for_match(f"{brand} {model}")}


def normalized_battery(raw_model: str) -> tuple[str, str, int | None, str, str | None]:
    cell_match = re.fullmatch(r"\s*(\d+)\s*x\s*(AA|AAA)\s*", raw_model or "", flags=re.I)
    if cell_match:
        battery_model = cell_match.group(2).upper()
        status = "uses_aa" if battery_model == "AA" else "uses_aaa"
        return battery_model, status, int(cell_match.group(1)), "Generic", "various"
    return raw_model.strip(), "fully_compatible", 1, "", None


def direct_dpreview_url(url: str) -> bool:
    if not validate_url(url):
        return False
    parsed = urlparse(url)
    return parsed.netloc.casefold() == "www.dpreview.com" and bool(EXACT_DPREVIEW_PATH.fullmatch(parsed.path))


def evidence_row(source: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    battery_model, status, quantity, battery_brand, chemistry = normalized_battery(source["battery_model"])
    evidence_text = source["evidence_text"].strip()
    return {
        "camera_id": candidate["camera_id"],
        "display_name": candidate["display_name"],
        "brand": candidate["brand"],
        "aliases_found": [],
        "battery_model": battery_model,
        "battery_brand": battery_brand or candidate["brand"],
        "chemistry": chemistry,
        "voltage": None,
        "capacity_mah": None,
        "status": status,
        "quantity_required": quantity,
        "evidence_level": "verified_medium",
        "source_type": "trusted_database",
        "source_name": f"DPReview {source['camera_model']} specifications",
        "source_url": source["source_url"],
        "source_text": f"DPReview specifications for {candidate['display_name']}: {evidence_text}",
        "cross_sources": [],
        "decision": "promote_verified",
        "notes": (
            "User-submitted hand-verified DPReview battery field. "
            "Stored as medium confidence because DPReview is a trusted database, not an official manual."
        ),
    }


def cell(value: Any) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")


def write_report(
    rows: list[dict[str, Any]],
    outcomes: list[dict[str, Any]],
    appended: list[dict[str, Any]],
    apply: bool,
) -> None:
    summary = Counter(row["result"] for row in outcomes)
    appended_by_brand = Counter(row["brand"] for row in appended)
    lines = [
        "# Manual DPReview Evidence Batch Review",
        "",
        f"Mode: {'apply' if apply else 'dry-run'}",
        "",
        "These inputs were supplied as manually verified records. Automated HTTP probes to representative DPReview URLs returned HTTP 403 on 2026-05-25, so accepted rows are retained as `trusted_database` with `medium` confidence, never `high`.",
        "",
        "Acceptance requires a direct DPReview compact-camera specification URL, one exact existing candidate match, explicit battery text, and no conflicting submitted battery for the same model.",
        "",
        "## Summary",
        "",
        f"- submitted_rows: {len(rows)}",
        f"- accepted_new_unresolved_evidence: {summary['accepted_new_unresolved_evidence']}",
        f"- already_verified_consistent: {summary['already_verified_consistent']}",
        f"- rejected_non_exact_source_url: {summary['rejected_non_exact_source_url']}",
        f"- rejected_conflicting_battery_submission: {summary['rejected_conflicting_battery_submission']}",
        f"- rejected_no_exact_candidate: {summary['rejected_no_exact_candidate']}",
        f"- appended_to_researched_evidence: {len(appended)}",
        "",
        "## Accepted New Evidence By Brand",
        "",
        "| Brand | Rows |",
        "| --- | ---: |",
    ]
    for brand, count in sorted(appended_by_brand.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"| {brand} | {count} |")
    lines.extend(
        [
            "",
            "## Review Detail",
            "",
            "| Input camera | Brand | Submitted battery | Matched camera_id | Result | Reason | Source URL |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in outcomes:
        lines.append(
            "| "
            + " | ".join(
                [
                    cell(row["camera"]),
                    cell(row["brand"]),
                    cell(row["battery"]),
                    cell(row.get("camera_id")),
                    cell(row["result"]),
                    cell(row["reason"]),
                    cell(row["source_url"]),
                ]
            )
            + " |"
        )
    REPORT_DIR.mkdir(exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def execute(apply: bool) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    submitted: list[dict[str, Any]] = []
    for path in INPUT_FILES:
        if not path.exists():
            raise FileNotFoundError(path.relative_to(ROOT))
        submitted.extend(load_array(path))
    ctx = ImportContext.load(ROOT)
    candidates_by_brand: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in ctx.candidates:
        candidates_by_brand[candidate["brand"]].append(candidate)
    cameras = {row["camera_id"] for row in ctx.cameras}
    unresolved = {row["camera_id"] for row in ctx.unresolved}
    compat_by_camera: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in ctx.compatibility:
        compat_by_camera[row["camera_id"]].append(row)
    battery_model_by_id = {row["battery_id"]: row["model"] for row in ctx.batteries}

    submission_batteries: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in submitted:
        battery_model, _, _, _, _ = normalized_battery(row.get("battery_model", ""))
        key = (row.get("brand", ""), normalize_for_match(row.get("camera_model", "")))
        submission_batteries[key].add(normalize_for_match(battery_model))

    normalized_additions: list[dict[str, Any]] = []
    outcomes: list[dict[str, Any]] = []
    for row in submitted:
        required = ["brand", "camera_model", "battery_model", "evidence_text", "source_url"]
        missing = [field for field in required if not row.get(field)]
        result: dict[str, Any] = {
            "camera": row.get("camera_model", ""),
            "brand": row.get("brand", ""),
            "battery": row.get("battery_model", ""),
            "source_url": row.get("source_url", ""),
            "camera_id": "",
        }
        key = (row.get("brand", ""), normalize_for_match(row.get("camera_model", "")))
        if missing or not direct_dpreview_url(row.get("source_url", "")):
            result.update(
                result="rejected_non_exact_source_url",
                reason="Required field missing or source URL is not an exact DPReview compact-camera specifications page.",
            )
            outcomes.append(result)
            continue
        if len(submission_batteries[key]) > 1:
            result.update(
                result="rejected_conflicting_battery_submission",
                reason="The supplied files give conflicting battery values for this exact model.",
            )
            outcomes.append(result)
            continue
        matches = [
            candidate
            for candidate in candidates_by_brand.get(row["brand"], [])
            if input_terms(row) & candidate_terms(candidate)
        ]
        if len(matches) != 1:
            result.update(
                result="rejected_no_exact_candidate",
                reason=f"Exact candidate matching returned {len(matches)} rows; no automatic merge is permitted.",
            )
            outcomes.append(result)
            continue
        candidate = matches[0]
        result["camera_id"] = candidate["camera_id"]
        normalized = evidence_row(row, candidate)
        if candidate["camera_id"] in cameras:
            normalized_model = normalize_for_match(normalized["battery_model"])
            existing_models = {
                normalize_for_match(battery_model_by_id[item["battery_id"]])
                for item in compat_by_camera[candidate["camera_id"]]
                if item["battery_id"] in battery_model_by_id
            }
            if normalized_model not in existing_models:
                result.update(
                    result="rejected_existing_mapping_conflict",
                    reason="Camera is already verified but submitted battery is not among its verified mappings.",
                )
            else:
                result.update(
                    result="already_verified_consistent",
                    reason="Camera already has this verified battery mapping; no additional promotion required.",
                )
            outcomes.append(result)
            continue
        if candidate["camera_id"] not in unresolved:
            result.update(
                result="rejected_not_unresolved",
                reason="Candidate is neither unresolved nor a verified camera; manual review required.",
            )
            outcomes.append(result)
            continue
        normalized_additions.append(normalized)
        result.update(
            result="accepted_new_unresolved_evidence",
            reason="Exact unresolved candidate and explicit battery field from a direct trusted-database specification URL.",
        )
        outcomes.append(result)

    existing = load_array(EVIDENCE_PATH)
    existing_keys = {
        (row.get("camera_id"), row.get("battery_model"), row.get("source_url"))
        for row in existing
    }
    appended = [
        row
        for row in normalized_additions
        if (row["camera_id"], row["battery_model"], row["source_url"]) not in existing_keys
    ]
    if apply and appended:
        write_json(EVIDENCE_PATH, [*existing, *appended])
    write_report(submitted, outcomes, appended, apply)
    return outcomes, appended


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize manually reviewed DPReview battery rows for the existing research importer.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    outcomes, appended = execute(args.apply)
    counts = Counter(row["result"] for row in outcomes)
    print(f"Mode: {'apply' if args.apply else 'dry-run'}")
    print(f"Submitted rows: {len(outcomes)}")
    for name, count in sorted(counts.items()):
        print(f"{name}: {count}")
    print(f"Evidence rows to append/appended: {len(appended)}")
    print(f"Report: {REPORT_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
