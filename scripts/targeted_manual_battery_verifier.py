from __future__ import annotations

import argparse
import copy
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from importers.common import (
    ImportContext,
    add_compatibility_source_backed,
    battery_record,
    dedupe_compatibility_for_app_output,
    exact_model_match,
    make_battery_id,
    normalize_for_match,
    register_source,
    validate_url,
    write_json,
)
from validate_and_export import validate


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
REPORT_DIR = ROOT / "reports"
TARGET_EVIDENCE_PATH = DATA_DIR / "targeted_manual_battery_evidence.json"
RESEARCH_EVIDENCE_PATH = DATA_DIR / "researched_battery_evidence.json"
OVERRIDES_PATH = DATA_DIR / "manual_research_overrides.json"
SUGGESTIONS_PATH = DATA_DIR / "battery_suggestions.json"
STATE_PATH = REPORT_DIR / "phase10_targeted_manual_state.json"

TARGET_BRANDS = ["Nikon", "Samsung", "Kodak", "Casio", "Sony"]
AUDIT_PATHS = {
    "Nikon": REPORT_DIR / "phase10_nikon_manual_audit.md",
    "Samsung": REPORT_DIR / "phase10_samsung_manual_audit.md",
    "Kodak": REPORT_DIR / "phase10_kodak_manual_audit.md",
    "Casio": REPORT_DIR / "phase10_casio_manual_audit.md",
    "Sony": REPORT_DIR / "phase10_sony_remaining_audit.md",
}
HIGH_SOURCE_TYPES = {"official_manual", "official_accessory_page"}
MEDIUM_SOURCE_TYPES = {"manual_mirror", "trusted_database"}
SUGGESTION_SOURCE_TYPES = {"retailer", "third_party_chart"}
WARNING = "Not verified official compatibility; do not treat this suggestion as a confirmed compatible battery."


def load_array(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{path.relative_to(ROOT)} must contain a JSON array")
    return data


def state_counts(ctx: ImportContext, suggestions: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "verified_cameras": len(ctx.cameras),
        "unresolved_models": len(ctx.unresolved),
        "compatibility_rows": len(ctx.compatibility),
        "batteries": len(ctx.batteries),
        "candidates": len(ctx.candidates),
        "suggestions": len(suggestions),
    }


def compact(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").casefold())


def candidate_terms(candidate: dict[str, Any], aliases: list[str] | None = None) -> list[str]:
    terms = [candidate["model"], candidate["display_name"], *candidate.get("aliases", []), *(aliases or [])]
    for values in (candidate.get("regional_names") or {}).values():
        terms.extend(values)
    return [value for value in terms if value]


def source_confirms_camera(candidate: dict[str, Any], evidence: dict[str, Any]) -> bool:
    return exact_model_match(
        candidate["model"],
        evidence.get("source_text", ""),
        candidate_terms(candidate, evidence.get("aliases_found", [])),
    )


def source_confirms_battery(evidence: dict[str, Any]) -> bool:
    text = evidence.get("source_text", "")
    battery_model = evidence.get("battery_model", "")
    normalized_battery = compact(battery_model)
    if normalized_battery == "aa":
        named = bool(re.search(r"\bAA(?:-size)?\b", text, flags=re.I))
    elif normalized_battery == "aaa":
        named = bool(re.search(r"\bAAA(?:-size)?\b", text, flags=re.I))
    else:
        named = normalized_battery != "" and normalized_battery in compact(text)
    has_power_context = bool(
        re.search(r"\b(?:battery|batteries|power|lithium|li-ion|rechargeable|supplied)\b", text, flags=re.I)
    )
    excluded = bool(re.search(r"\b(?:charger only|ac adapter only|internal memory|flash memory|built-in flash)\b", text, flags=re.I))
    return named and has_power_context and not excluded


def policy_action(evidence: dict[str, Any]) -> tuple[str, str, str]:
    decision = evidence.get("decision")
    source_type = evidence.get("source_type")
    level = evidence.get("evidence_level")
    if decision == "promote_verified" and level == "verified_high" and source_type in HIGH_SOURCE_TYPES:
        return decision, "high", "Official manual/spec/accessory evidence names the exact power source."
    if decision == "promote_verified" and level == "verified_medium" and source_type in MEDIUM_SOURCE_TYPES:
        return decision, "medium", "Readable manual mirror or trusted database names the exact power source."
    if decision == "add_suggestion" and level in {"suggestion_low", "suggestion_medium"} and source_type in SUGGESTION_SOURCE_TYPES:
        return decision, "medium" if level == "suggestion_medium" else "low", "Weak source retained as suggestion only."
    return "remain_unresolved", "low", "Evidence decision/source policy does not allow promotion."


def normalized_override(row: dict[str, Any]) -> dict[str, Any]:
    source_type = row.get("source_type")
    decision = row.get("decision", "remain_unresolved")
    if decision == "promote_verified":
        level = "verified_high" if source_type in HIGH_SOURCE_TYPES else "verified_medium"
    else:
        level = "suggestion_low"
    return {
        "camera_id": row.get("camera_id"),
        "display_name": row.get("camera_query", row.get("camera_id", "")),
        "brand": row.get("brand", ""),
        "aliases_found": row.get("aliases", []),
        "battery_model": row.get("battery_model"),
        "battery_brand": row.get("battery_brand"),
        "chemistry": row.get("chemistry"),
        "voltage": row.get("voltage"),
        "capacity_mah": row.get("capacity_mah"),
        "status": row.get("status", "fully_compatible"),
        "quantity_required": row.get("quantity_required", 1),
        "evidence_level": level,
        "source_type": source_type,
        "source_name": row.get("source_name"),
        "source_url": row.get("source_url"),
        "source_text": row.get("source_text"),
        "decision": decision,
        "notes": row.get("notes", "Manual research override."),
    }


def load_evidence() -> tuple[list[dict[str, Any]], dict[str, int]]:
    targeted = load_array(TARGET_EVIDENCE_PATH)
    previous = load_array(RESEARCH_EVIDENCE_PATH)
    overrides = [normalized_override(row) for row in load_array(OVERRIDES_PATH)]
    combined = [*targeted, *overrides, *previous]
    deduped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in combined:
        key = (row.get("camera_id", ""), row.get("battery_model", ""), row.get("source_url", ""))
        if all(key):
            deduped.setdefault(key, row)
    return list(deduped.values()), {
        "targeted_records": len(targeted),
        "manual_overrides": len(overrides),
        "prior_research_records_read": len(previous),
    }


def match_scope(row: dict[str, Any], brand: str | None, series: str | None) -> bool:
    if brand and row.get("brand", "").casefold() != brand.casefold():
        return False
    if series and series.casefold() not in row.get("series", "").casefold():
        return False
    return True


def queue_models(ctx: ImportContext, brand: str | None, series: str | None, evidence_ids: set[str], limit: int) -> list[dict[str, Any]]:
    candidates = {row["camera_id"]: row for row in ctx.candidates}
    queue = [
        candidates[row["camera_id"]]
        for row in ctx.unresolved
        if row["camera_id"] in candidates and match_scope(row, brand, series)
    ]
    queue.sort(key=lambda row: (row["camera_id"] not in evidence_ids, row["series"], row["display_name"]))
    return queue[:limit]


def build_battery(evidence: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    model = evidence["battery_model"]
    brand = evidence.get("battery_brand") or ("Generic" if model.upper() in {"AA", "AAA"} else candidate["brand"])
    battery = battery_record(brand, model, "Added from reviewed Phase 10 targeted manual evidence.")
    if evidence.get("chemistry"):
        battery["chemistry"] = evidence["chemistry"]
    if evidence.get("voltage") is not None:
        battery["voltage"] = evidence["voltage"]
    if evidence.get("capacity_mah") is not None:
        battery["capacity_mah"] = evidence["capacity_mah"]
    return battery


def suggestion_row(evidence: dict[str, Any], candidate: dict[str, Any], ctx: ImportContext, confidence: str) -> dict[str, Any]:
    battery_id = make_battery_id(evidence.get("battery_brand") or candidate["brand"], evidence["battery_model"])
    if not any(row["battery_id"] == battery_id for row in ctx.batteries):
        battery_id = None
    return {
        "camera_id": candidate["camera_id"],
        "display_name": candidate["display_name"],
        "brand": candidate["brand"],
        "suggested_battery_model": evidence["battery_model"],
        "suggested_battery_id": battery_id,
        "evidence_type": evidence["evidence_level"],
        "source_name": evidence["source_name"],
        "source_url": evidence["source_url"],
        "source_text": evidence["source_text"],
        "confidence": confidence,
        "warning": WARNING,
        "last_checked": ctx.today,
    }


def evaluate_and_apply(
    ctx: ImportContext,
    suggestions: list[dict[str, Any]],
    evidence_rows: list[dict[str, Any]],
    selected_ids: set[str],
    apply: bool,
) -> list[dict[str, Any]]:
    candidates = {row["camera_id"]: row for row in ctx.candidates}
    verified_ids = {row["camera_id"] for row in ctx.cameras}
    suggestion_keys = {(row["camera_id"], compact(row["suggested_battery_model"]), row["source_url"]) for row in suggestions}
    results: list[dict[str, Any]] = []
    required = [
        "camera_id", "display_name", "brand", "battery_model", "evidence_level", "source_type",
        "source_name", "source_url", "source_text", "decision",
    ]
    for evidence in evidence_rows:
        camera_id = evidence.get("camera_id", "")
        if camera_id not in selected_ids:
            continue
        candidate = candidates.get(camera_id)
        missing = [field for field in required if not evidence.get(field)]
        action, confidence, reason = policy_action(evidence)
        if candidate is None:
            action, reason = "remain_unresolved", "Evidence camera_id has no matching catalog candidate."
        elif missing or not validate_url(evidence.get("source_url", "")):
            action, reason = "remain_unresolved", f"Invalid evidence fields or URL: {', '.join(missing)}."
        elif not source_confirms_camera(candidate, evidence):
            action, reason = "remain_unresolved", "Source text does not identify this exact model; no loose match allowed."
        elif not source_confirms_battery(evidence):
            action, reason = "remain_unresolved", "Source text does not explicitly state the battery/power source."
        existing = camera_id in verified_ids
        status = "already_verified" if existing and action == "promote_verified" else ("would_apply" if not apply and action != "remain_unresolved" else ("applied" if apply and action != "remain_unresolved" else "unresolved"))
        result = {
            "camera_id": camera_id,
            "camera": candidate["display_name"] if candidate else evidence.get("display_name", camera_id),
            "brand": candidate["brand"] if candidate else evidence.get("brand", ""),
            "battery": evidence.get("battery_model", ""),
            "source_type": evidence.get("source_type", ""),
            "source_url": evidence.get("source_url", ""),
            "source_text": evidence.get("source_text", ""),
            "evidence_level": evidence.get("evidence_level", ""),
            "decision": action,
            "status": status,
            "reason": reason,
        }
        results.append(result)
        if not apply or action == "remain_unresolved" or candidate is None:
            continue
        if action == "promote_verified":
            battery = build_battery(evidence, candidate)
            add_compatibility_source_backed(
                ctx,
                copy.deepcopy(candidate),
                battery,
                evidence.get("status", "fully_compatible"),
                evidence.get("quantity_required", 1),
                evidence["source_text"],
                evidence["source_name"],
                evidence["source_url"],
                evidence["source_type"],
                confidence,
                candidate["brand"],
            )
            suggestions[:] = [row for row in suggestions if row["camera_id"] != candidate["camera_id"]]
        elif action == "add_suggestion":
            suggestion = suggestion_row(evidence, candidate, ctx, confidence)
            key = (suggestion["camera_id"], compact(suggestion["suggested_battery_model"]), suggestion["source_url"])
            if key not in suggestion_keys:
                suggestions.append(suggestion)
                suggestion_keys.add(key)
            register_source(ctx, evidence["source_name"], evidence["source_url"], evidence["source_type"], candidate["brand"], WARNING)
    return results


def cell(value: Any) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")


def write_audit(brand: str, mode: str, selected: list[dict[str, Any]], results: list[dict[str, Any]], unresolved_lookup: dict[str, dict[str, Any]], today: str) -> None:
    path = AUDIT_PATHS.get(brand, REPORT_DIR / f"phase10_{brand.casefold()}_manual_audit.md")
    result_ids = {row["camera_id"] for row in results}
    lines = [
        f"# Phase 10 {brand} Manual Audit",
        "",
        f"Generated: {today}",
        f"Mode: {mode}",
        "",
        "| Camera | Source URL checked | Extracted battery text | Action | Reason |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in results:
        lines.append(
            f"| {cell(row['camera'])} | {cell(row['source_url'])} | {cell(row['source_text'])} | {row['decision']} | {cell(row['reason'])} |"
        )
    for candidate in selected:
        if candidate["camera_id"] in result_ids:
            continue
        unresolved = unresolved_lookup.get(candidate["camera_id"], {})
        urls = ", ".join(unresolved.get("checked_source_urls", []))
        lines.append(
            f"| {cell(candidate['display_name'])} | {cell(urls)} |  | remain_unresolved | {cell(unresolved.get('reason', 'No reviewed battery evidence recorded.'))} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def priority_remaining(ctx: ImportContext) -> list[dict[str, Any]]:
    brand_rank = {brand: position for position, brand in enumerate(TARGET_BRANDS)}
    return sorted(
        ctx.unresolved,
        key=lambda row: (brand_rank.get(row["brand"], 99), row["series"], row["display_name"]),
    )


def update_state(before: dict[str, int], after: dict[str, int], results: list[dict[str, Any]], apply: bool) -> dict[str, Any]:
    if STATE_PATH.exists():
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    else:
        state = {"before": before, "applied_camera_ids": [], "suggestion_keys": []}
    if apply:
        changed_ids = {
            row["camera_id"]
            for row in results
            if row["decision"] == "promote_verified" and row["status"] == "applied" and row["camera_id"] not in state["applied_camera_ids"]
        }
        suggestion_keys = {
            f"{row['camera_id']}|{row['source_url']}"
            for row in results
            if row["decision"] == "add_suggestion" and row["status"] == "applied"
        }
        state["applied_camera_ids"] = sorted({*state["applied_camera_ids"], *changed_ids})
        state["suggestion_keys"] = sorted({*state["suggestion_keys"], *suggestion_keys})
        state["after"] = after
        STATE_PATH.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    return state


def write_summary(ctx: ImportContext, suggestions: list[dict[str, Any]], state: dict[str, Any], evidence_meta: dict[str, int], mode: str) -> None:
    before = state.get("before", state_counts(ctx, suggestions))
    after = state_counts(ctx, suggestions)
    phase_ids = set(state.get("applied_camera_ids", []))
    compat = [row for row in ctx.compatibility if row["camera_id"] in phase_ids]
    by_brand = Counter(next((camera["brand"] for camera in ctx.cameras if camera["camera_id"] == camera_id), "Unknown") for camera_id in phase_ids)
    by_source = Counter(row["source_type"] for row in compat)
    remaining = Counter(row["brand"] for row in ctx.unresolved)
    lines = [
        "# Phase 10 Targeted Manual Verification Summary",
        "",
        f"Mode: {mode}",
        "",
        "This workflow applies only reviewed evidence with an exact model name and explicit battery/power text. It does not infer compatibility from related series.",
        "",
        "## Coverage Delta",
        "",
        "| Metric | Before | After | Delta |",
        "| --- | ---: | ---: | ---: |",
    ]
    for key in ["verified_cameras", "unresolved_models", "compatibility_rows", "batteries", "candidates", "suggestions"]:
        lines.append(f"| {key} | {before[key]} | {after[key]} | {after[key] - before[key]} |")
    lines.extend(["", "## Evidence Inputs Read", ""])
    for key, value in evidence_meta.items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Verified Added By Brand", "", "| Brand | Cameras |", "| --- | ---: |"])
    for brand, count in sorted(by_brand.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"| {brand} | {count} |")
    lines.extend(["", "## Phase 10 Compatibility Rows By Source Type", "", "| Source type | Rows |", "| --- | ---: |"])
    for source_type, count in sorted(by_source.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"| {source_type} | {count} |")
    lines.extend(["", "## Remaining Target Brands", "", "| Brand | Unresolved |", "| --- | ---: |"])
    for brand in TARGET_BRANDS:
        lines.append(f"| {brand} | {remaining.get(brand, 0)} |")
    lines.extend(["", "## Top 50 Remaining Unresolved", "", "| Camera | Brand | Series | Reason |", "| --- | --- | --- | --- |"])
    for row in priority_remaining(ctx)[:50]:
        lines.append(f"| {cell(row['display_name'])} | {row['brand']} | {cell(row['series'])} | {cell(row['reason'])} |")
    (REPORT_DIR / "phase10_targeted_manual_verification_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def execute(brand: str | None, series: str | None, limit: int, apply: bool) -> dict[str, Any]:
    ctx = ImportContext.load(ROOT)
    suggestions = load_array(SUGGESTIONS_PATH)
    evidence, evidence_meta = load_evidence()
    before = state_counts(ctx, suggestions)
    evidence_ids = {row["camera_id"] for row in evidence if row.get("camera_id")}
    selected = queue_models(ctx, brand, series, evidence_ids, limit)
    selected_ids = {row["camera_id"] for row in selected}
    unresolved_lookup = {row["camera_id"]: row for row in ctx.unresolved}
    results = evaluate_and_apply(ctx, suggestions, evidence, selected_ids, apply)
    if apply:
        dedupe_compatibility_for_app_output(ctx)
        validate(ctx.cameras, ctx.batteries, ctx.compatibility, ctx.candidates, ctx.sources, ctx.unresolved, suggestions)
        ctx.write_all()
        write_json(SUGGESTIONS_PATH, sorted(suggestions, key=lambda row: (row["camera_id"], row["source_url"])))
    after = state_counts(ctx, suggestions)
    REPORT_DIR.mkdir(exist_ok=True)
    report_brands = [brand] if brand else TARGET_BRANDS
    for report_brand in report_brands:
        if report_brand:
            brand_selected = [row for row in selected if row["brand"].casefold() == report_brand.casefold()]
            brand_results = [row for row in results if row["brand"].casefold() == report_brand.casefold()]
            write_audit(report_brand, "apply" if apply else "dry-run", brand_selected, brand_results, unresolved_lookup, ctx.today)
    state = update_state(before, after, results, apply)
    write_summary(ctx, suggestions, state, evidence_meta, "apply" if apply else "dry-run")
    return {"before": before, "after": after, "selected": selected, "results": results}


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply reviewed per-model battery evidence for remaining compact cameras.")
    parser.add_argument("--brand", help="Only attempt unresolved candidates for one brand.")
    parser.add_argument("--series", help="Only attempt candidates whose series contains this value.")
    parser.add_argument("--limit", type=int, default=100, help="Maximum unresolved candidates to audit.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Generate audit reports without mutating database JSON.")
    mode.add_argument("--apply", action="store_true", help="Apply evidence accepted by source and exact-match policy.")
    args = parser.parse_args()
    outcome = execute(args.brand, args.series, max(1, args.limit), args.apply)
    print(f"Mode: {'apply' if args.apply else 'dry-run'}")
    print(f"Scope: brand={args.brand or 'all'} series={args.series or 'all'} selected={len(outcome['selected'])}")
    for key, value in outcome["before"].items():
        print(f"{key}: {value} -> {outcome['after'][key]}")
    promoted = sum(1 for row in outcome["results"] if row["decision"] == "promote_verified" and row["status"] == "applied")
    suggested = sum(1 for row in outcome["results"] if row["decision"] == "add_suggestion" and row["status"] == "applied")
    print(f"Promoted verified: {promoted}")
    print(f"Added suggestions: {suggested}")


if __name__ == "__main__":
    main()
