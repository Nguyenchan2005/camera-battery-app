from __future__ import annotations

import argparse
import copy
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from importers.common import (
    CANDIDATE_FIELDS,
    ImportContext,
    add_compatibility_source_backed,
    add_or_update_camera_candidate,
    battery_record,
    dedupe_aliases,
    dedupe_compatibility_for_app_output,
    exact_model_match,
    normalize_for_match,
    register_source,
    validate_url,
    write_json,
)
from validate_and_export import validate


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
REPORT_DIR = ROOT / "reports"
EVIDENCE_PATH = DATA_DIR / "researched_battery_evidence.json"
OVERRIDES_PATH = DATA_DIR / "manual_research_overrides.json"
SUGGESTIONS_PATH = DATA_DIR / "battery_suggestions.json"

PROMOTION_LEVELS = {
    "verified_high": ({"official_manual", "official_accessory_page"}, "high"),
    "verified_medium": ({"manual_mirror", "trusted_database"}, "medium"),
}
SUGGESTION_LEVELS = {"suggestion_medium": "medium", "suggestion_low": "low"}
SUGGESTION_WARNING = "Not verified official compatibility; do not treat this suggestion as a confirmed compatible battery."

POPULAR_BRAND_SCORES = {
    "Sony": 85,
    "Nikon": 82,
    "Fujifilm": 80,
    "Panasonic": 78,
    "Olympus": 76,
    "Samsung": 74,
    "Casio": 70,
    "Kodak": 66,
    "Pentax": 62,
    "Ricoh": 60,
    "HP": 50,
    "Minolta": 45,
    "Konica Minolta": 45,
    "Leica": 42,
    "Sigma": 40,
}
POPULAR_SERIES_TERMS = [
    "RX",
    "HX",
    "WX",
    "DSC-T",
    "COOLPIX P",
    "COOLPIX S",
    "COOLPIX AW",
    "FINEPIX F",
    "FINEPIX XP",
    "TZ",
    "ZS",
    "LX",
    "FZ",
    "TG",
    "TOUGH",
    "XZ",
    "WB",
    "ST",
    "EX-ZR",
    "EASYSHARE C",
]
INITIAL_CASES = [
    ("Samsung WB1000", "samsung_wb1000"),
    ("Samsung TL320", "samsung_wb1000"),
    ("Sony DSC-RX10", "sony_cyber_shot_dsc_rx10"),
    ("Sony DSC-HX30V", "sony_cyber_shot_dsc_hx30v"),
    ("Sony DSC-W530", "sony_cyber_shot_dsc_w530"),
    ("Fujifilm FinePix F31fd", "fujifilm_finepix_f31fd"),
    ("Panasonic TZ70 / ZS50", "panasonic_lumix_dmc_zs50"),
    ("Nikon Coolpix S9500", "nikon_coolpix_s9500"),
    ("Casio Exilim EX-ZR1000", "casio_exilim_ex_zr1000"),
    ("Kodak EasyShare C613", "kodak_easyshare_c613"),
]


def load_array(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise ValueError(f"{path.relative_to(ROOT)} must contain a JSON array")
    return value


def compact(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").casefold())


def all_camera_terms(candidate: dict[str, Any], aliases: list[str] | None = None) -> list[str]:
    terms = [candidate["display_name"], candidate["model"], *candidate.get("aliases", []), *(aliases or [])]
    for names in (candidate.get("regional_names") or {}).values():
        terms.extend(names)
    identifier_patterns = [
        r"\bDSC-[A-Z0-9-]+\b",
        r"\b(?:DMC|DC)-[A-Z0-9-]+\b",
        r"\bEX-[A-Z0-9-]+\b",
    ]
    identifier_text = " ".join(str(term) for term in terms if term)
    for pattern in identifier_patterns:
        terms.extend(re.findall(pattern, identifier_text, flags=re.I))
    return dedupe_aliases([term for term in terms if term])


def source_confirms_camera(candidate: dict[str, Any], evidence: dict[str, Any]) -> bool:
    terms = all_camera_terms(candidate, evidence.get("aliases_found", []))
    if exact_model_match(candidate["model"], evidence["source_text"], terms):
        return True
    normalized_text = normalize_for_match(evidence["source_text"])
    for term in terms:
        normalized_identifier = normalize_for_match(term)
        if not re.fullmatch(r"(?:dsc|dmc|dc|ex)\s+[a-z0-9]+", normalized_identifier):
            continue
        if re.search(r"(?<![a-z0-9])" + re.escape(normalized_identifier).replace(r"\ ", r"\s+") + r"(?![a-z0-9])", normalized_text):
            return True
    return False


def source_confirms_battery(evidence: dict[str, Any]) -> bool:
    text = evidence["source_text"]
    model = evidence["battery_model"]
    normalized_model = compact(model)
    if normalized_model == "aa":
        has_model = bool(re.search(r"\bAA\b", text, flags=re.I))
    elif normalized_model == "aaa":
        has_model = bool(re.search(r"\bAAA\b", text, flags=re.I))
    else:
        has_model = normalized_model in compact(text)
    if not has_model:
        return False
    context = re.search(r"\b(?:battery|batteries|power|rechargeable|supplied)\b", text, flags=re.I)
    excluded_only = re.search(r"\b(?:charger only|AC adapter only|internal memory|flash memory|built-in flash)\b", text, flags=re.I)
    return bool(context) and not excluded_only


def state_counts(ctx: ImportContext, suggestions: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "verified_cameras": len(ctx.cameras),
        "unresolved_models": len(ctx.unresolved),
        "compatibility_rows": len(ctx.compatibility),
        "batteries": len(ctx.batteries),
        "candidates": len(ctx.candidates),
        "suggestions": len(suggestions),
    }


def normalize_override(row: dict[str, Any]) -> dict[str, Any]:
    required = ["camera_id", "battery_model", "source_url", "source_name", "source_type", "source_text", "decision"]
    missing = [field for field in required if not row.get(field)]
    if missing:
        raise ValueError(f"manual override for {row.get('camera_query', row.get('camera_id', 'unknown'))} missing: {', '.join(missing)}")
    source_type = row["source_type"]
    if row["decision"] == "promote_verified":
        evidence_level = "verified_high" if source_type in {"official_manual", "official_accessory_page"} else "verified_medium"
    else:
        evidence_level = "suggestion_medium" if source_type in {"manual_mirror", "trusted_database"} else "suggestion_low"
    return {
        "camera_id": row["camera_id"],
        "display_name": row.get("camera_query", row["camera_id"]),
        "brand": row.get("battery_brand", ""),
        "aliases_found": row.get("aliases", []),
        "battery_model": row["battery_model"],
        "battery_brand": row.get("battery_brand", "Generic"),
        "chemistry": row.get("chemistry"),
        "voltage": row.get("voltage"),
        "capacity_mah": row.get("capacity_mah"),
        "status": row.get("status", "fully_compatible"),
        "quantity_required": row.get("quantity_required", 1),
        "evidence_level": evidence_level,
        "source_type": source_type,
        "source_name": row["source_name"],
        "source_url": row["source_url"],
        "source_text": row["source_text"],
        "cross_sources": row.get("cross_sources", []),
        "decision": row["decision"],
        "notes": row.get("notes", "Manual research override."),
    }


def load_evidence() -> tuple[list[dict[str, Any]], list[str]]:
    evidence = load_array(EVIDENCE_PATH)
    errors: list[str] = []
    for row in load_array(OVERRIDES_PATH):
        try:
            evidence.append(normalize_override(row))
        except ValueError as exc:
            errors.append(str(exc))
    return evidence, errors


def evidence_policy(evidence: dict[str, Any]) -> tuple[str, str]:
    if evidence.get("decision") == "promote_verified":
        rule = PROMOTION_LEVELS.get(evidence.get("evidence_level"))
        if rule and evidence.get("source_type") in rule[0]:
            return "promote_verified", f"{evidence['evidence_level']} source satisfies promotion policy."
        return "keep_unresolved", "Promotion rejected: evidence level and source type are inconsistent."
    if evidence.get("decision") == "add_suggestion":
        expected_confidence = SUGGESTION_LEVELS.get(evidence.get("evidence_level"))
        if expected_confidence:
            return "add_suggestion", "Evidence is recorded as suggestion only; it is not compatible verified data."
    return "keep_unresolved", "No accepted source-backed promotion or suggestion decision."


def evidence_confidence(evidence: dict[str, Any]) -> str:
    if evidence["evidence_level"] == "verified_high":
        return "high"
    if evidence["evidence_level"] in {"verified_medium", "suggestion_medium"}:
        return "medium"
    return "low"


def candidate_from_evidence(ctx: ImportContext, evidence: dict[str, Any]) -> dict[str, Any] | None:
    existing = next((row for row in ctx.candidates if row["camera_id"] == evidence["camera_id"]), None)
    if existing is not None:
        return copy.deepcopy(existing)
    patch = evidence.get("candidate_patch")
    if patch and set(CANDIDATE_FIELDS).issubset(patch):
        return copy.deepcopy(patch)
    return None


def enrich_candidate(candidate: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(candidate)
    aliases = evidence.get("aliases_found", [])
    result["aliases"] = dedupe_aliases([*result.get("aliases", []), *aliases])
    if aliases:
        regional = copy.deepcopy(result.get("regional_names", {}))
        regional["research_aliases"] = dedupe_aliases([*regional.get("research_aliases", []), *aliases])
        result["regional_names"] = regional
    return result


def apply_alias_corrections(ctx: ImportContext, evidence: dict[str, Any]) -> list[str]:
    applied: list[str] = []
    for correction in evidence.get("alias_corrections", []):
        camera_id = correction["camera_id"]
        removals = {normalize_for_match(value) for value in correction.get("remove_aliases", [])}
        for collection in (ctx.candidates, ctx.cameras):
            row = next((item for item in collection if item["camera_id"] == camera_id), None)
            if row is None:
                continue
            row["aliases"] = [alias for alias in row.get("aliases", []) if normalize_for_match(alias) not in removals]
            for region, names in list((row.get("regional_names") or {}).items()):
                row["regional_names"][region] = [name for name in names if normalize_for_match(name) not in removals]
                if not row["regional_names"][region]:
                    del row["regional_names"][region]
        applied.append(f"Removed conflicting ZS50 alias from {camera_id}; Panasonic manual associates ZS50 with TZ70.")
    return applied


def build_battery(evidence: dict[str, Any]) -> dict[str, Any]:
    battery = battery_record(
        evidence.get("battery_brand") or "Generic",
        evidence["battery_model"],
        "Added from reviewed LLM-assisted research evidence with a recorded source.",
    )
    if evidence.get("chemistry"):
        battery["chemistry"] = evidence["chemistry"]
    if evidence.get("voltage") is not None:
        battery["voltage"] = evidence["voltage"]
    if evidence.get("capacity_mah") is not None:
        battery["capacity_mah"] = evidence["capacity_mah"]
    return battery


def build_search_queries(candidate: dict[str, Any]) -> list[str]:
    display = candidate["display_name"]
    brand = candidate["brand"]
    model = candidate["model"]
    queries = [
        f"{display} battery",
        f"{display} battery type",
        f"{display} user manual battery",
        f"{display} specifications battery",
        f"{display} power source",
        f"{display} replacement battery",
        f"{brand} {model} battery",
        f"{brand} {model} manual pdf",
        f"{brand} {model} DPReview specifications",
    ]
    for alias in candidate.get("aliases", [])[:3]:
        queries.extend([f"{alias} battery", f"{alias} manual", f"{alias} specifications"])
    return list(dict.fromkeys(queries))


def priority_score(candidate: dict[str, Any], evidence_ids: set[str], manual_queries: str) -> int:
    text = f"{candidate['display_name']} {candidate.get('series', '')}".upper()
    score = POPULAR_BRAND_SCORES.get(candidate["brand"], 0)
    score += 20 if any(term in text for term in POPULAR_SERIES_TERMS) else 0
    score += 10 if candidate.get("regional_names") else 0
    score += 30 if compact(candidate["display_name"]) in compact(manual_queries) else 0
    score += 500 if candidate["camera_id"] in evidence_ids else 0
    return score


def build_queue(ctx: ImportContext, evidence: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    evidence_ids = {row["camera_id"] for row in evidence}
    manual_queries = json.dumps(load_array(DATA_DIR / "manual_missing_queries.json"), ensure_ascii=False)
    candidates = {row["camera_id"]: row for row in ctx.candidates}
    unresolved_candidates = [candidates[row["camera_id"]] for row in ctx.unresolved if row["camera_id"] in candidates]
    ranked = sorted(
        unresolved_candidates,
        key=lambda row: (-priority_score(row, evidence_ids, manual_queries), row["brand"], row["display_name"]),
    )
    selected = [row for row in ranked if row["camera_id"] in evidence_ids][:limit]
    selected_ids = {row["camera_id"] for row in selected}
    for row in evidence:
        patch = row.get("candidate_patch")
        if patch and row["camera_id"] not in selected_ids and len(selected) < limit:
            selected.append(patch)
            selected_ids.add(row["camera_id"])
    brand_order = list(POPULAR_BRAND_SCORES)
    remaining_by_brand: dict[str, list[dict[str, Any]]] = {brand: [] for brand in brand_order}
    remaining_other: list[dict[str, Any]] = []
    for row in ranked:
        if row["camera_id"] in selected_ids:
            continue
        if row["brand"] in remaining_by_brand:
            remaining_by_brand[row["brand"]].append(row)
        else:
            remaining_other.append(row)
    while len(selected) < limit and any(remaining_by_brand.values()):
        for brand in brand_order:
            if remaining_by_brand[brand] and len(selected) < limit:
                row = remaining_by_brand[brand].pop(0)
                selected.append(row)
                selected_ids.add(row["camera_id"])
    for row in remaining_other:
        if len(selected) >= limit:
            break
        selected.append(row)
        selected_ids.add(row["camera_id"])
    return selected


def suggestion_row(evidence: dict[str, Any], candidate: dict[str, Any], ctx: ImportContext) -> dict[str, Any]:
    wanted = compact(evidence["battery_model"])
    battery_id = next((row["battery_id"] for row in ctx.batteries if compact(row["model"]) == wanted), None)
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
        "confidence": evidence_confidence(evidence),
        "warning": SUGGESTION_WARNING,
        "last_checked": ctx.today,
    }


def apply_research(
    ctx: ImportContext,
    evidence_rows: list[dict[str, Any]],
    suggestions: list[dict[str, Any]],
    selected_ids: set[str],
    apply: bool,
) -> tuple[list[dict[str, Any]], list[str]]:
    results: list[dict[str, Any]] = []
    corrections: list[str] = []
    suggestion_keys = {(row["camera_id"], compact(row["suggested_battery_model"]), row["source_url"]) for row in suggestions}
    for evidence in evidence_rows:
        if evidence["camera_id"] not in selected_ids:
            continue
        missing = [
            key
            for key in ["camera_id", "display_name", "battery_model", "evidence_level", "source_type", "source_name", "source_url", "source_text", "decision"]
            if not evidence.get(key)
        ]
        if missing or not validate_url(evidence.get("source_url", "")):
            results.append({"camera": evidence.get("display_name", evidence.get("camera_id", "unknown")), "status": "invalid_evidence", "battery": evidence.get("battery_model", ""), "level": evidence.get("evidence_level", ""), "source": evidence.get("source_url", ""), "text": evidence.get("source_text", ""), "decision": "keep_unresolved", "reason": f"Invalid evidence fields or URL: {', '.join(missing)}"})
            continue
        candidate = candidate_from_evidence(ctx, evidence)
        if candidate is None:
            results.append({"camera": evidence["display_name"], "status": "not_in_catalog", "battery": evidence["battery_model"], "level": evidence["evidence_level"], "source": evidence["source_url"], "text": evidence["source_text"], "decision": "keep_unresolved", "reason": "No existing candidate or official candidate patch was supplied."})
            continue
        current_verified = any(row["camera_id"] == candidate["camera_id"] for row in ctx.cameras)
        action, reason = evidence_policy(evidence)
        if not source_confirms_camera(candidate, evidence):
            action, reason = "keep_unresolved", "Source text does not identify the exact camera model or recorded alias."
        elif not source_confirms_battery(evidence):
            action, reason = "keep_unresolved", "Source text does not explicitly identify a camera battery or power source."
        battery = build_battery(evidence)
        same_mapping = any(
            row["camera_id"] == candidate["camera_id"] and row["battery_id"] == battery["battery_id"] and row["status"] == evidence.get("status", "fully_compatible")
            for row in ctx.compatibility
        )
        outcome = "already_verified" if current_verified and same_mapping and action == "promote_verified" else ("proposed" if not apply else "applied")
        results.append({"camera_id": candidate["camera_id"], "camera": candidate["display_name"], "status": outcome, "battery": evidence["battery_model"], "level": evidence["evidence_level"], "source_type": evidence["source_type"], "source": evidence["source_url"], "text": evidence["source_text"], "decision": action, "reason": reason, "aliases": evidence.get("aliases_found", [])})
        if not apply or action == "keep_unresolved":
            continue
        if action == "promote_verified":
            if evidence.get("alias_corrections"):
                corrections.extend(apply_alias_corrections(ctx, evidence))
            candidate = enrich_candidate(candidate, evidence)
            if evidence.get("candidate_patch"):
                add_or_update_camera_candidate(ctx, candidate)
            for source in evidence.get("cross_sources", []):
                if source.get("source_url") and validate_url(source["source_url"]):
                    register_source(ctx, source["source_name"], source["source_url"], "trusted_database", evidence.get("brand", candidate["brand"]), source["source_text"])
            add_compatibility_source_backed(
                ctx,
                candidate,
                battery,
                evidence.get("status", "fully_compatible"),
                evidence.get("quantity_required", 1),
                evidence["source_text"],
                evidence["source_name"],
                evidence["source_url"],
                evidence["source_type"],
                evidence_confidence(evidence),
                evidence.get("brand", candidate["brand"]),
            )
        elif action == "add_suggestion":
            row = suggestion_row(evidence, candidate, ctx)
            key = (row["camera_id"], compact(row["suggested_battery_model"]), row["source_url"])
            if key not in suggestion_keys:
                suggestions.append(row)
                suggestion_keys.add(key)
            register_source(ctx, evidence["source_name"], evidence["source_url"], evidence["source_type"], candidate["brand"], "Unverified research suggestion only.")
    return results, corrections


def initial_case_status(ctx: ImportContext, results: list[dict[str, Any]]) -> list[dict[str, str]]:
    result_by_id = {row.get("camera_id"): row for row in results}
    output = []
    for query, camera_id in INITIAL_CASES:
        applied = result_by_id.get(camera_id)
        camera = next((row for row in ctx.cameras if row["camera_id"] == camera_id), None)
        compatibility = [row for row in ctx.compatibility if row["camera_id"] == camera_id]
        if camera and compatibility:
            battery = ", ".join(sorted({row["battery_id"] for row in compatibility}))
            decision = "promoted_verified" if applied and applied["status"] != "already_verified" else "already_verified"
            reason = applied["reason"] if applied else "Verified mapping already existed before this research batch."
        elif query == "Samsung TL320" and applied and applied["decision"] == "promote_verified":
            battery = applied["battery"]
            decision = "proposed_alias"
            reason = "TL320 will be searchable as a source-backed alias of Samsung WB1000 after applying its battery evidence."
        elif applied and applied["decision"] == "promote_verified":
            battery = applied["battery"]
            decision = "proposed_verified"
            reason = applied["reason"]
        elif query == "Samsung TL320":
            battery, decision, reason = "", "alias_pending", "TL320 is handled as an alias of Samsung WB1000, not a second camera row."
        else:
            battery, decision, reason = "", "still_unresolved", "No accepted mapping in this batch."
        output.append({"query": query, "camera_id": camera_id, "battery": battery, "decision": decision, "reason": reason})
    return output


def markdown_cell(value: Any) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")


def write_report(
    path: Path,
    mode: str,
    ctx: ImportContext,
    before: dict[str, int],
    after: dict[str, int],
    queue: list[dict[str, Any]],
    results: list[dict[str, Any]],
    corrections: list[str],
    override_errors: list[str],
) -> None:
    promoted = [row for row in results if row["decision"] == "promote_verified" and row["status"] == "applied"]
    suggested = [row for row in results if row["decision"] == "add_suggestion" and row["status"] == "applied"]
    researched_ids = {row.get("camera_id") for row in results}
    no_evidence = [row for row in queue if row["camera_id"] not in researched_ids]
    lines = [
        "# LLM-Assisted Manual Research Batch",
        "",
        f"Generated: {ctx.today}",
        f"Mode: {mode}",
        "",
        "The agent researches sources outside this script. The script only validates recorded evidence and applies source-backed decisions; it never invents a battery mapping.",
        "",
        "## Summary",
        "",
        "| Metric | Before | After | Delta |",
        "| --- | ---: | ---: | ---: |",
    ]
    for field in ["verified_cameras", "unresolved_models", "compatibility_rows", "batteries", "candidates", "suggestions"]:
        lines.append(f"| {field} | {before[field]} | {after[field]} | {after[field] - before[field]} |")
    lines.extend(
        [
            "",
            f"- Priority tasks selected: {len(queue)}",
            f"- Evidence records reviewed in selected batch: {len(results)}",
            f"- Promoted in this run: {len(promoted)}",
            f"- Suggestions added in this run: {len(suggested)}",
            "",
            "## Research Decisions",
            "",
            "| Camera | Current/apply status | Proposed battery | Evidence level | Source | Source text | Decision | Reason |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in results:
        lines.append(
            "| "
            + " | ".join(
                [
                    markdown_cell(row["camera"]),
                    markdown_cell(row["status"]),
                    markdown_cell(row["battery"]),
                    markdown_cell(row["level"]),
                    markdown_cell(f"{row.get('source_type', '')}: {row['source']}"),
                    markdown_cell(row["text"]),
                    markdown_cell(row["decision"]),
                    markdown_cell(row["reason"]),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Initial Test Cases", "", "| Query | Camera ID | Resulting battery ID | Decision | Reason |", "| --- | --- | --- | --- | --- |"])
    for row in initial_case_status(ctx, results):
        lines.append(f"| {markdown_cell(row['query'])} | {row['camera_id']} | {row['battery']} | {row['decision']} | {markdown_cell(row['reason'])} |")
    if corrections:
        lines.extend(["", "## Alias Corrections", ""])
        lines.extend(f"- {line}" for line in corrections)
    if override_errors:
        lines.extend(["", "## Invalid Manual Overrides", ""])
        lines.extend(f"- {line}" for line in override_errors)
    lines.extend(
        [
            "",
            "## Selected Tasks Still Awaiting Evidence",
            "",
            "| Camera | Brand | Search queries prepared | Reason |",
            "| --- | --- | ---: | --- |",
        ]
    )
    for row in no_evidence:
        lines.append(f"| {markdown_cell(row['display_name'])} | {row['brand']} | {len(build_search_queries(row))} | Research task generated; no reviewed battery evidence recorded in this batch. |")
    lines.extend(["", "## Twenty Popular Models Still Unresolved", "", "| Camera | Brand | Current reason |", "| --- | --- | --- |"])
    remaining = sorted(ctx.unresolved, key=lambda row: (-priority_score(row, set(), ""), row["brand"], row["display_name"]))[:20]
    for row in remaining:
        lines.append(f"| {markdown_cell(row['display_name'])} | {row['brand']} | {markdown_cell(row['reason'])} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def execute(limit: int, apply: bool, camera_ids: set[str] | None = None) -> dict[str, Any]:
    ctx = ImportContext.load(ROOT)
    suggestions = load_array(SUGGESTIONS_PATH)
    evidence, override_errors = load_evidence()
    before = state_counts(ctx, suggestions)
    queue = build_queue(ctx, evidence, limit)
    if camera_ids is not None:
        selected_ids = set(camera_ids)
        queue = [row for row in [candidate_from_evidence(ctx, evidence_row) for evidence_row in evidence if evidence_row["camera_id"] in selected_ids] if row]
    else:
        selected_ids = {row["camera_id"] for row in queue}
    results, corrections = apply_research(ctx, evidence, suggestions, selected_ids, apply)
    if apply:
        dedupe_compatibility_for_app_output(ctx)
        validate(ctx.cameras, ctx.batteries, ctx.compatibility, ctx.candidates, ctx.sources, ctx.unresolved, suggestions)
        ctx.write_all()
        write_json(SUGGESTIONS_PATH, sorted(suggestions, key=lambda row: (row["camera_id"], row["suggested_battery_model"], row["source_url"])))
    after = state_counts(ctx, suggestions)
    REPORT_DIR.mkdir(exist_ok=True)
    candidates_report = REPORT_DIR / "llm_research_batch_candidates.md"
    write_report(candidates_report, "apply" if apply else "dry-run", ctx, before, after, queue, results, corrections, override_errors)
    if apply:
        applied_report = REPORT_DIR / "llm_research_batch_applied.md"
        changed = before != after
        if changed or not applied_report.exists():
            write_report(applied_report, "apply", ctx, before, after, queue, results, corrections, override_errors)
    return {"before": before, "after": after, "results": results, "corrections": corrections, "report": str(candidates_report.relative_to(ROOT))}


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply human/LLM-reviewed battery research evidence without inferring compatibility.")
    parser.add_argument("--limit", type=int, default=50, help="Maximum priority research tasks included in this batch.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Write review report only; do not update database JSON.")
    mode.add_argument("--apply", action="store_true", help="Apply accepted source-backed evidence to database JSON.")
    args = parser.parse_args()
    apply = bool(args.apply)
    outcome = execute(max(1, args.limit), apply)
    print(f"Mode: {'apply' if apply else 'dry-run'}")
    for key, value in outcome["before"].items():
        print(f"{key}: {value} -> {outcome['after'][key]}")
    promoted = sum(1 for row in outcome["results"] if row["decision"] == "promote_verified" and row["status"] == "applied")
    suggestions = sum(1 for row in outcome["results"] if row["decision"] == "add_suggestion" and row["status"] == "applied")
    print(f"Applied verified promotions: {promoted}")
    print(f"Applied suggestions: {suggestions}")
    print(f"Report: {outcome['report']}")


if __name__ == "__main__":
    main()
