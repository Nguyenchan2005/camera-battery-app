from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from importers.common import (
    ImportContext,
    add_compatibility_source_backed,
    battery_record,
    dedupe_compatibility_for_app_output,
    normalize_for_match,
    validate_url,
    write_json,
)
from llm_assisted_research_batch import source_confirms_battery, source_confirms_camera
from validate_and_export import validate


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
INPUT_DIR = ROOT / "research_inputs"
REPORT_DIR = ROOT / "reports"
CLAIMS_PATH = INPUT_DIR / "manual_battery_claims_batch_620.json"
CURATED_EVIDENCE_PATH = INPUT_DIR / "manual_battery_claims_batch_620_verified_evidence.json"
TARGET_EVIDENCE_PATH = DATA_DIR / "researched_battery_evidence.json"
REPORT_PATH = REPORT_DIR / "manual_battery_claims_batch_620_audit.md"
ATTESTED_REPORT_PATH = REPORT_DIR / "manual_battery_claims_batch_620_attested_import.md"
ATTESTED_SOURCE_NAME = "Project owner manually verified battery claims batch 620"
ATTESTED_SOURCE_URL = "https://github.com/Nguyenchan2005/camera-battery-app/blob/97bafe9/research_inputs/manual_battery_claims_batch_620.json"
ATTESTED_SOURCE_TYPE = "third_party_chart"
ATTESTED_CONFIDENCE = "low"


def load_array(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{path.relative_to(ROOT)} must contain an array")
    return data


def compact(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


def normalize_claim_battery(model: str) -> tuple[str, int | None]:
    cell = re.fullmatch(r"\s*(\d+)\s*x\s*(AA|AAA)\s*", model or "", flags=re.I)
    if cell:
        return cell.group(2).upper(), int(cell.group(1))
    return model.strip(), 1


def canonical_claim_battery(model: str) -> tuple[str, str, int | None, str]:
    battery_model, quantity = normalize_claim_battery(model)
    battery_model = battery_model.upper()
    if battery_model == "AA":
        return battery_model, "uses_aa", quantity, "Generic"
    if battery_model == "AAA":
        return battery_model, "uses_aaa", quantity, "Generic"
    if battery_model in {"2CR5", "CR-V3", "CRV3", "CR123A"}:
        normalized = "CR-V3" if battery_model == "CRV3" else battery_model
        return normalized, "fully_compatible", 1, "Generic"
    return battery_model, "fully_compatible", 1, ""


def markdown_cell(value: Any) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")


def audit_claims(
    claims: list[dict[str, Any]],
    curated: list[dict[str, Any]],
    ctx: ImportContext,
) -> tuple[list[dict[str, Any]], list[dict[str, str]], dict[str, int]]:
    candidate_by_id = {row["camera_id"]: row for row in ctx.candidates}
    verified_ids = {row["camera_id"] for row in ctx.cameras}
    unresolved_ids = {row["camera_id"] for row in ctx.unresolved}
    battery_by_id = {row["battery_id"]: row["model"] for row in ctx.batteries}
    compat_by_camera: dict[str, set[str]] = defaultdict(set)
    for row in ctx.compatibility:
        model = battery_by_id.get(row["battery_id"])
        if model:
            compat_by_camera[row["camera_id"]].add(compact(model))

    claim_by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in claims:
        claim_by_id[row.get("camera_id", "")].append(row)
    accepted: list[dict[str, Any]] = []
    review: list[dict[str, str]] = []
    for evidence in curated:
        cid = evidence.get("camera_id", "")
        candidate = candidate_by_id.get(cid)
        claim_rows = claim_by_id.get(cid, [])
        result = {
            "camera_id": cid,
            "display_name": evidence.get("display_name", cid),
            "submitted_battery": ", ".join(sorted({row.get("battery_model", "") for row in claim_rows})),
            "source_battery": evidence.get("battery_model", ""),
            "source_url": evidence.get("source_url", ""),
            "status": "",
            "reason": "",
        }
        if not claim_rows:
            result.update(status="rejected_not_submitted", reason="No corresponding row exists in the submitted claims file.")
        elif candidate is None:
            result.update(status="rejected_no_candidate", reason="No existing camera candidate matches this camera_id.")
        elif not validate_url(evidence.get("source_url", "")):
            result.update(status="rejected_invalid_source_url", reason="The evidence URL is missing or invalid.")
        elif not source_confirms_camera(candidate, evidence):
            result.update(status="rejected_model_not_proven", reason="Evidence text does not identify the exact candidate model.")
        elif not source_confirms_battery(evidence):
            result.update(status="rejected_battery_not_proven", reason="Evidence text does not explicitly identify the battery or power source.")
        elif cid in verified_ids and compact(evidence["battery_model"]) in compat_by_camera[cid]:
            result.update(status="already_imported_source_evidence", reason="This source-backed mapping is already present in verified compatibility data.")
            accepted.append(evidence)
        elif cid not in unresolved_ids:
            result.update(status="rejected_not_unresolved", reason="The candidate is not unresolved and has no matching verified battery mapping.")
        else:
            claimed_model, claimed_qty = normalize_claim_battery(claim_rows[0]["battery_model"])
            source_qty = evidence.get("quantity_required", 1)
            corrected = compact(claimed_model) != compact(evidence["battery_model"]) or claimed_qty != source_qty
            status = "accepted_source_correction" if corrected else "accepted_source_confirmed"
            reason = "Source-backed evidence corrects the submitted value." if corrected else "Explicit source text confirms the submitted mapping."
            result.update(status=status, reason=reason)
            accepted.append(evidence)
        review.append(result)

    duplicate_claim_ids = sum(1 for rows in claim_by_id.values() if len(rows) > 1)
    raw_status = Counter()
    conflicting_verified = 0
    for cid, rows in claim_by_id.items():
        if cid not in candidate_by_id:
            raw_status["missing_candidate"] += 1
        elif cid in unresolved_ids:
            raw_status["unresolved"] += 1
        elif cid in verified_ids:
            raw_status["already_verified"] += 1
            for row in rows:
                submitted_model, _ = normalize_claim_battery(row["battery_model"])
                if compat_by_camera[cid] and compact(submitted_model) not in compat_by_camera[cid]:
                    conflicting_verified += 1
                    break
        else:
            raw_status["candidate_other"] += 1
    metrics = {
        "submitted_rows": len(claims),
        "submitted_camera_ids": len(claim_by_id),
        "duplicate_claim_ids": duplicate_claim_ids,
        "rows_with_source_url": sum(1 for row in claims if row.get("source_url")),
        "rows_with_source_text": sum(1 for row in claims if row.get("source_text") or row.get("evidence_text")),
        "raw_unresolved": raw_status["unresolved"],
        "raw_already_verified": raw_status["already_verified"],
        "raw_missing_candidate": raw_status["missing_candidate"],
        "raw_candidate_other": raw_status["candidate_other"],
        "raw_verified_conflicts": conflicting_verified,
        "curated_rows": len(curated),
        "accepted_curated_rows": len(accepted),
    }
    return accepted, review, metrics


def append_evidence(accepted: list[dict[str, Any]], apply: bool) -> list[dict[str, Any]]:
    existing = load_array(TARGET_EVIDENCE_PATH)
    existing_keys = {
        (row.get("camera_id"), compact(row.get("battery_model", "")), row.get("source_url"))
        for row in existing
    }
    additions = [
        row
        for row in accepted
        if (row["camera_id"], compact(row["battery_model"]), row["source_url"]) not in existing_keys
    ]
    if apply and additions:
        write_json(TARGET_EVIDENCE_PATH, [*existing, *additions])
    return additions


def write_report(metrics: dict[str, int], review: list[dict[str, str]], additions: list[dict[str, Any]], apply: bool) -> None:
    statuses = Counter(row["status"] for row in review)
    brands = Counter(row["brand"] for row in additions)
    lines = [
        "# Manual Battery Claims Batch 620 Audit",
        "",
        f"Mode: {'apply' if apply else 'dry-run'}",
        "",
        "The submitted file is retained as a claim queue. It contains camera and battery values but no source evidence, so it is never imported directly into verified compatibility data.",
        "",
        "## Raw Input",
        "",
        f"- submitted_rows: {metrics['submitted_rows']}",
        f"- submitted_camera_ids: {metrics['submitted_camera_ids']}",
        f"- duplicate_claim_ids: {metrics['duplicate_claim_ids']}",
        f"- rows_with_source_url: {metrics['rows_with_source_url']}",
        f"- rows_with_source_text: {metrics['rows_with_source_text']}",
        f"- raw_unresolved_claims: {metrics['raw_unresolved']}",
        f"- raw_already_verified_claims: {metrics['raw_already_verified']}",
        f"- raw_missing_candidate_claims: {metrics['raw_missing_candidate']}",
        f"- raw_verified_mapping_conflicts: {metrics['raw_verified_conflicts']}",
        "",
        "## Source-Checked Subset",
        "",
        f"- curated_evidence_rows: {metrics['curated_rows']}",
        f"- accepted_curated_rows: {metrics['accepted_curated_rows']}",
        f"- accepted_source_confirmed: {statuses['accepted_source_confirmed']}",
        f"- accepted_source_correction: {statuses['accepted_source_correction']}",
        f"- already_imported_source_evidence: {statuses['already_imported_source_evidence']}",
        f"- appended_to_researched_evidence: {len(additions)}",
        "",
        "| Brand | Evidence appended |",
        "| --- | ---: |",
    ]
    for brand, count in sorted(brands.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"| {brand} | {count} |")
    lines.extend(
        [
            "",
            "## Evidence Review",
            "",
            "| Camera | Submitted value | Source-backed value | Result | Reason | Source |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in review:
        lines.append(
            "| "
            + " | ".join(
                [
                    markdown_cell(row["display_name"]),
                    markdown_cell(row["submitted_battery"]),
                    markdown_cell(row["source_battery"]),
                    markdown_cell(row["status"]),
                    markdown_cell(row["reason"]),
                    markdown_cell(row["source_url"]),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Import Rule",
            "",
            "Rows not listed in the evidence review remain pending manual/source research. A battery value in the claim queue alone is not accepted as compatibility evidence.",
        ]
    )
    REPORT_DIR.mkdir(exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def execute(apply: bool) -> None:
    claims = load_array(CLAIMS_PATH)
    curated = load_array(CURATED_EVIDENCE_PATH)
    ctx = ImportContext.load(ROOT)
    accepted, review, metrics = audit_claims(claims, curated, ctx)
    additions = append_evidence(accepted, apply)
    write_report(metrics, review, additions, apply)
    mode = "Applied" if apply else "Dry-run"
    print(f"{mode}: {metrics['submitted_rows']} raw claims; {len(accepted)} source-backed evidence rows accepted; {len(additions)} new evidence rows.")
    print(f"Report: {REPORT_PATH.relative_to(ROOT)}")


def existing_models_by_camera(ctx: ImportContext) -> dict[str, set[str]]:
    battery_models = {row["battery_id"]: row["model"] for row in ctx.batteries}
    result: dict[str, set[str]] = defaultdict(set)
    for row in ctx.compatibility:
        model = battery_models.get(row["battery_id"])
        if model:
            result[row["camera_id"]].add(compact(model))
    return result


def write_attested_report(
    mode: str,
    before: dict[str, int],
    after: dict[str, int],
    decisions: list[dict[str, str]],
) -> None:
    status_counts = Counter(row["status"] for row in decisions)
    imported_by_brand = Counter(row["brand"] for row in decisions if row["status"] == "imported_user_attested")
    lines = [
        "# Manual Battery Claims Batch 620 - User-Attested Import",
        "",
        f"Mode: {mode}",
        "",
        "The project owner instructed that this hand-verified batch be imported without original verification URLs.",
        "Imported mappings are therefore labelled `third_party_chart` with `low` confidence.",
        "The recorded URL links to the submitted claim artifact for provenance only; it is not represented as an official or independent battery source.",
        "",
        "## Before / After",
        "",
        "| Metric | Before | After | Delta |",
        "| --- | ---: | ---: | ---: |",
    ]
    for key in ["verified_cameras", "unresolved_models", "compatibility_rows", "batteries", "sources"]:
        lines.append(f"| {key} | {before[key]} | {after[key]} | {after[key] - before[key]} |")
    lines.extend(
        [
            "",
            "## Import Decisions",
            "",
            f"- imported_user_attested: {status_counts['imported_user_attested']}",
            f"- already_verified_consistent: {status_counts['already_verified_consistent']}",
            f"- skipped_existing_conflict: {status_counts['skipped_existing_conflict']}",
            f"- skipped_missing_candidate: {status_counts['skipped_missing_candidate']}",
            f"- skipped_duplicate_claim: {status_counts['skipped_duplicate_claim']}",
            "",
            "| Brand | Imported mappings |",
            "| --- | ---: |",
        ]
    )
    for brand, count in sorted(imported_by_brand.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"| {brand} | {count} |")
    lines.extend(
        [
            "",
            "## Detail",
            "",
            "| Camera ID | Brand | Submitted battery | Normalized mapping | Decision | Reason |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in decisions:
        lines.append(
            "| "
            + " | ".join(
                [
                    markdown_cell(row["camera_id"]),
                    markdown_cell(row["brand"]),
                    markdown_cell(row["submitted_battery"]),
                    markdown_cell(row["normalized_mapping"]),
                    markdown_cell(row["status"]),
                    markdown_cell(row["reason"]),
                ]
            )
            + " |"
        )
    REPORT_DIR.mkdir(exist_ok=True)
    ATTESTED_REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def execute_attested(apply: bool) -> None:
    claims = load_array(CLAIMS_PATH)
    ctx = ImportContext.load(ROOT)
    suggestions = load_array(DATA_DIR / "battery_suggestions.json")
    before = {
        "verified_cameras": len(ctx.cameras),
        "unresolved_models": len(ctx.unresolved),
        "compatibility_rows": len(ctx.compatibility),
        "batteries": len(ctx.batteries),
        "sources": len(ctx.sources),
    }
    candidate_by_id = {row["camera_id"]: row for row in ctx.candidates}
    verified_ids = {row["camera_id"] for row in ctx.cameras}
    unresolved_ids = {row["camera_id"] for row in ctx.unresolved}
    existing_models = existing_models_by_camera(ctx)
    decisions: list[dict[str, str]] = []
    seen_claims: set[tuple[str, str]] = set()

    for row in claims:
        camera_id = row.get("camera_id", "")
        submitted_battery = row.get("battery_model", "")
        model, status, quantity, generic_brand = canonical_claim_battery(submitted_battery)
        claim_key = (camera_id, compact(model))
        candidate = candidate_by_id.get(camera_id)
        brand = candidate["brand"] if candidate else ""
        decision = {
            "camera_id": camera_id,
            "brand": brand,
            "submitted_battery": submitted_battery,
            "normalized_mapping": f"{model} ({status}, quantity={quantity})",
            "status": "",
            "reason": "",
        }
        if claim_key in seen_claims:
            decision.update(status="skipped_duplicate_claim", reason="Duplicate camera/battery claim in the submitted batch.")
            decisions.append(decision)
            continue
        seen_claims.add(claim_key)
        if candidate is None:
            decision.update(status="skipped_missing_candidate", reason="No camera candidate record exists; a battery-only claim cannot construct camera metadata.")
            decisions.append(decision)
            continue
        if camera_id in verified_ids:
            if compact(model) in existing_models.get(camera_id, set()):
                decision.update(status="already_verified_consistent", reason="A compatible mapping for this battery model already exists.")
            else:
                decision.update(status="skipped_existing_conflict", reason="The camera already has a different source-backed verified mapping; it is not overwritten by an unlinked attestation.")
            decisions.append(decision)
            continue
        if camera_id not in unresolved_ids:
            decision.update(status="skipped_existing_conflict", reason="Candidate is not in the unresolved queue and is not eligible for attested promotion.")
            decisions.append(decision)
            continue

        battery_brand = generic_brand or candidate["brand"]
        note = (
            f"Project owner manually attested {candidate['display_name']} uses {model}"
            f"{f' (quantity {quantity})' if status in {'uses_aa', 'uses_aaa'} else ''}. "
            "Original verification URL was not supplied; provenance URL records the submitted batch only."
        )
        battery = battery_record(battery_brand, model, "Added from project-owner manual attestation without an original source URL.")
        add_compatibility_source_backed(
            ctx,
            candidate,
            battery,
            status,
            quantity,
            note,
            ATTESTED_SOURCE_NAME,
            ATTESTED_SOURCE_URL,
            ATTESTED_SOURCE_TYPE,
            ATTESTED_CONFIDENCE,
            "Project owner",
        )
        decision.update(status="imported_user_attested", reason="Imported at low confidence from project-owner manual attestation; original URL not provided.")
        decisions.append(decision)

    dedupe_compatibility_for_app_output(ctx)
    validate(ctx.cameras, ctx.batteries, ctx.compatibility, ctx.candidates, ctx.sources, ctx.unresolved, suggestions)
    after = {
        "verified_cameras": len(ctx.cameras),
        "unresolved_models": len(ctx.unresolved),
        "compatibility_rows": len(ctx.compatibility),
        "batteries": len(ctx.batteries),
        "sources": len(ctx.sources),
    }
    write_attested_report("apply" if apply else "dry-run", before, after, decisions)
    if apply:
        ctx.write_all()
    imported = sum(1 for row in decisions if row["status"] == "imported_user_attested")
    skipped = len(decisions) - imported
    print(f"{'Applied' if apply else 'Dry-run'} user-attested import: {imported} mappings imported; {skipped} rows skipped or already covered.")
    for key in before:
        print(f"{key}: {before[key]} -> {after[key]}")
    print(f"Report: {ATTESTED_REPORT_PATH.relative_to(ROOT)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit a source-less manual battery claim batch and append only independently source-backed evidence.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--dry-run", action="store_true")
    action.add_argument("--apply", action="store_true")
    action.add_argument("--dry-run-attested", action="store_true", help="Simulate importing remaining manual claims using the project owner's attestation at low confidence.")
    action.add_argument("--apply-attested", action="store_true", help="Import remaining manual claims using the project owner's attestation at low confidence.")
    args = parser.parse_args()
    if args.dry_run_attested or args.apply_attested:
        execute_attested(apply=args.apply_attested)
    else:
        execute(apply=args.apply)


if __name__ == "__main__":
    main()
