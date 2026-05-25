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
    dedupe_aliases,
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
EVIDENCE_PATH = DATA_DIR / "direct_research_battery_evidence.json"
SUGGESTIONS_PATH = DATA_DIR / "battery_suggestions.json"
STATE_PATH = REPORT_DIR / "direct_agent_research_state.json"
DRY_RUN_REPORT = REPORT_DIR / "direct_agent_research_candidates.md"
APPLY_REPORT = REPORT_DIR / "direct_agent_research_applied.md"

HIGH_SOURCE_TYPES = {"official_manual", "official_accessory_page"}
MEDIUM_SOURCE_TYPES = {"manual_mirror", "trusted_database"}
SUGGESTION_SOURCE_TYPES = {"retailer", "third_party_chart"}
WARNING = "Not verified official compatibility; do not treat this suggestion as a confirmed compatible battery."

BRAND_QUOTAS = [("Kodak", 20), ("Casio", 20), ("Samsung", 20), ("Nikon", 20), ("Sony", 10)]
OTHER_BRANDS = ["Fujifilm", "Panasonic", "Olympus", "Pentax", "Ricoh", "HP"]
POPULAR_TERMS = {
    "Kodak": ["easyshare c", "easyshare m", "easyshare z"],
    "Casio": ["ex-zr", "ex-z", "ex-h", "ex-fc", "ex-tr"],
    "Samsung": ["wb", "st", "pl", "dv", "es", "digimax"],
    "Nikon": ["coolpix l", "coolpix s", "coolpix p", "coolpix aw", "coolpix w"],
    "Sony": ["dsc-wx", "dsc-hx", "dsc-w", "dsc-h", "dsc-t"],
}
INITIAL_TEST_IDS = [
    "samsung_wb550",
    "samsung_wb600",
    "samsung_wb650",
    "samsung_st65",
    "samsung_pl120",
    "kodak_easyshare_c653",
    "kodak_easyshare_c643",
    "kodak_easyshare_m550",
    "kodak_easyshare_z950",
    "casio_exilim_ex_h10",
    "casio_exilim_ex_fc100",
    "casio_exilim_ex_zr1000",
    "nikon_coolpix_l100",
    "nikon_coolpix_l110",
    "nikon_coolpix_l22",
    "nikon_coolpix_s6200",
    "sony_cyber_shot_dsc_wx9",
    "sony_cyber_shot_dsc_w510",
    "sony_cyber_shot_dsc_w560",
]


def load_array(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{path.relative_to(ROOT)} must contain a JSON array")
    return data


def compact(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").casefold())


def state_counts(ctx: ImportContext, suggestions: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "verified_cameras": len(ctx.cameras),
        "unresolved_models": len(ctx.unresolved),
        "compatibility_rows": len(ctx.compatibility),
        "batteries": len(ctx.batteries),
        "candidates": len(ctx.candidates),
        "suggestions": len(suggestions),
    }


def candidate_terms(candidate: dict[str, Any], extra: list[str] | None = None) -> list[str]:
    terms = [candidate["display_name"], candidate["model"], *candidate.get("aliases", []), *(extra or [])]
    for values in (candidate.get("regional_names") or {}).values():
        terms.extend(values)
    return dedupe_aliases([value for value in terms if value])


def evidence_by_id() -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in load_array(EVIDENCE_PATH):
        grouped.setdefault(row.get("camera_id", ""), []).append(row)
    return grouped


def source_confirms_camera(candidate: dict[str, Any], evidence: dict[str, Any]) -> bool:
    return exact_model_match(
        candidate["model"],
        evidence.get("source_text", ""),
        candidate_terms(candidate, evidence.get("aliases_found", [])),
    )


def source_confirms_battery(evidence: dict[str, Any]) -> bool:
    text = evidence.get("source_text", "")
    model = compact(evidence.get("battery_model", ""))
    if model == "aa":
        named = bool(re.search(r"\bAA(?:-size)?\b", text, flags=re.I))
    elif model == "aaa":
        named = bool(re.search(r"\bAAA(?:-size)?\b", text, flags=re.I))
    else:
        named = bool(model) and model in compact(text)
    context = bool(
        re.search(
            r"\b(?:battery|batteries|power|lithium|li-ion|rechargeable|supplied)\b|"
            r"\u96fb\u6e90|\u96fb\u6c60|\u30d0\u30c3\u30c6\u30ea\u30fc|\u30ea\u30c1\u30e3\u30fc\u30b8\u30e3\u30d6\u30eb",
            text,
            flags=re.I,
        )
    )
    excluded = bool(
        re.search(r"\b(?:charger only|ac adapter only|internal memory|flash memory|built-in flash)\b", text, flags=re.I)
    )
    return named and context and not excluded


def policy_action(evidence: dict[str, Any]) -> tuple[str, str, str]:
    decision = evidence.get("decision")
    level = evidence.get("evidence_level")
    source_type = evidence.get("source_type")
    if decision == "promote_verified" and level == "verified_high" and source_type in HIGH_SOURCE_TYPES:
        return decision, "high", "Official source explicitly identifies the battery or power source."
    if decision == "promote_verified" and level == "verified_medium" and source_type in MEDIUM_SOURCE_TYPES:
        return decision, "medium", "Readable manual mirror or trusted database explicitly identifies the battery."
    if decision == "add_suggestion" and level in {"suggestion_medium", "suggestion_low"} and source_type in SUGGESTION_SOURCE_TYPES:
        confidence = "medium" if level == "suggestion_medium" else "low"
        return decision, confidence, "Weak evidence is retained only as an unverified suggestion."
    return "remain_unresolved", "low", "Source classification does not permit a verified mapping."


def preferred(candidate: dict[str, Any], evidence_ids: set[str]) -> tuple[int, int, str]:
    name = normalize_for_match(f"{candidate.get('series', '')} {candidate.get('model', '')}")
    tokens = POPULAR_TERMS.get(candidate["brand"], [])
    popularity = 0 if any(token in name for token in tokens) else 1
    return (0 if candidate["camera_id"] in evidence_ids else 1, popularity, candidate["display_name"])


def balanced_queue(ctx: ImportContext, limit: int, evidence_ids: set[str]) -> list[dict[str, Any]]:
    candidates = {row["camera_id"]: row for row in ctx.candidates}
    unresolved = [candidates[row["camera_id"]] for row in ctx.unresolved if row["camera_id"] in candidates]
    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()

    def add(rows: list[dict[str, Any]], amount: int) -> None:
        for row in sorted(rows, key=lambda item: preferred(item, evidence_ids)):
            if row["camera_id"] not in selected_ids and len([item for item in selected if item["brand"] == row["brand"]]) < amount:
                selected.append(row)
                selected_ids.add(row["camera_id"])

    for brand, quota in BRAND_QUOTAS:
        add([row for row in unresolved if row["brand"] == brand], quota)
    other_target = 10
    reviewed_other = sorted(
        [row for row in unresolved if row["brand"] in OTHER_BRANDS and row["camera_id"] in evidence_ids],
        key=lambda item: preferred(item, evidence_ids),
    )
    for row in reviewed_other[:other_target]:
        selected.append(row)
        selected_ids.add(row["camera_id"])
    while sum(1 for row in selected if row["brand"] in OTHER_BRANDS) < other_target:
        added = False
        for brand in OTHER_BRANDS:
            rows = [
                row for row in sorted(unresolved, key=lambda item: preferred(item, evidence_ids))
                if row["brand"] == brand and row["camera_id"] not in selected_ids
            ]
            if rows and sum(1 for row in selected if row["brand"] in OTHER_BRANDS) < other_target:
                selected.append(rows[0])
                selected_ids.add(rows[0]["camera_id"])
                added = True
        if not added:
            break
    if len(selected) < limit:
        for row in sorted(unresolved, key=lambda item: preferred(item, evidence_ids)):
            if row["camera_id"] not in selected_ids:
                selected.append(row)
                selected_ids.add(row["camera_id"])
            if len(selected) >= limit:
                break
    return selected[:limit]


def resolve_one(ctx: ImportContext, query: str) -> dict[str, Any] | None:
    normalized = normalize_for_match(query)
    compact_query = compact(query)
    exact: list[dict[str, Any]] = []
    compact_matches: list[dict[str, Any]] = []
    for candidate in ctx.candidates:
        terms = candidate_terms(candidate)
        if normalized in {normalize_for_match(term) for term in terms}:
            exact.append(candidate)
        elif compact_query in {compact(term) for term in terms}:
            compact_matches.append(candidate)
    matches = exact or compact_matches
    return matches[0] if len(matches) == 1 else None


def research_prompt(candidate: dict[str, Any]) -> str:
    aliases = ", ".join(candidate_terms(candidate)[2:]) or "none recorded"
    return (
        f"Research this compact digital camera and determine its battery. "
        f"camera_id={candidate['camera_id']}; display_name={candidate['display_name']}; "
        f"brand={candidate['brand']}; series={candidate['series']}; aliases={aliases}. "
        "Find exact battery/power text and URL; decide promote_verified, add_suggestion, or remain_unresolved."
    )


def build_battery(evidence: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    model = evidence["battery_model"]
    brand = evidence.get("battery_brand") or ("Generic" if model.upper() in {"AA", "AAA"} else candidate["brand"])
    battery = battery_record(brand, model, "Added from reviewed direct-agent research evidence.")
    for field in ["chemistry", "voltage", "capacity_mah"]:
        if evidence.get(field) is not None:
            battery[field] = evidence[field]
    return battery


def candidate_with_aliases(candidate: dict[str, Any], aliases: list[str]) -> dict[str, Any]:
    updated = copy.deepcopy(candidate)
    if not aliases:
        return updated
    updated["aliases"] = dedupe_aliases([*updated.get("aliases", []), *aliases])
    regional_names = copy.deepcopy(updated.get("regional_names", {}))
    regional_names["research_aliases"] = dedupe_aliases([*regional_names.get("research_aliases", []), *aliases])
    updated["regional_names"] = regional_names
    return updated


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


def evaluate(
    ctx: ImportContext,
    suggestions: list[dict[str, Any]],
    candidate: dict[str, Any],
    evidence: dict[str, Any],
    apply: bool,
) -> dict[str, Any]:
    required = [
        "camera_id", "display_name", "brand", "battery_model", "source_name", "source_url",
        "source_type", "source_text", "evidence_level", "decision", "confidence",
    ]
    missing = [field for field in required if not evidence.get(field)]
    action, confidence, reason = policy_action(evidence)
    if evidence.get("is_compact_fixed_lens") is not True:
        action, reason = "remain_unresolved", "Evidence does not confirm compact/fixed-lens scope."
    elif missing or not validate_url(evidence.get("source_url", "")):
        action, reason = "remain_unresolved", f"Evidence is missing required fields or URL: {', '.join(missing)}."
    elif evidence["camera_id"] != candidate["camera_id"] or not source_confirms_camera(candidate, evidence):
        action, reason = "remain_unresolved", "Evidence does not name the exact candidate model."
    elif not source_confirms_battery(evidence):
        action, reason = "remain_unresolved", "Evidence text does not explicitly identify a battery or power source."

    existing = any(camera["camera_id"] == candidate["camera_id"] for camera in ctx.cameras)
    if existing and action == "promote_verified":
        status = "already_verified"
    elif not apply and action == "promote_verified":
        status = "would_promote"
    elif not apply and action == "add_suggestion":
        status = "would_suggest"
    elif apply and action == "promote_verified":
        status = "promoted"
    elif apply and action == "add_suggestion":
        status = "suggested"
    else:
        status = "unresolved"

    result = {
        "camera_id": candidate["camera_id"],
        "camera": candidate["display_name"],
        "brand": candidate["brand"],
        "aliases": evidence.get("aliases_found", []),
        "battery": evidence.get("battery_model", ""),
        "source_name": evidence.get("source_name", ""),
        "source_type": evidence.get("source_type", ""),
        "source_url": evidence.get("source_url", ""),
        "source_text": evidence.get("source_text", ""),
        "decision": action,
        "confidence": confidence,
        "status": status,
        "reason": reason,
    }
    if not apply or action == "remain_unresolved" or existing:
        return result

    if action == "promote_verified":
        updated_candidate = candidate_with_aliases(candidate, evidence.get("aliases_found", []))
        add_compatibility_source_backed(
            ctx,
            updated_candidate,
            build_battery(evidence, updated_candidate),
            evidence.get("status", "fully_compatible"),
            evidence.get("quantity_required", 1),
            evidence["source_text"],
            evidence["source_name"],
            evidence["source_url"],
            evidence["source_type"],
            confidence,
            updated_candidate["brand"],
        )
        suggestions[:] = [row for row in suggestions if row["camera_id"] != candidate["camera_id"]]
    elif action == "add_suggestion":
        row = suggestion_row(evidence, candidate, ctx, confidence)
        key = (row["camera_id"], compact(row["suggested_battery_model"]), row["source_url"])
        present = {
            (item["camera_id"], compact(item["suggested_battery_model"]), item["source_url"])
            for item in suggestions
        }
        if key not in present:
            suggestions.append(row)
        register_source(ctx, evidence["source_name"], evidence["source_url"], evidence["source_type"], candidate["brand"], WARNING)
    return result


def cell(value: Any) -> str:
    if isinstance(value, list):
        value = ", ".join(value)
    return str(value or "").replace("|", "\\|").replace("\n", " ")


def initial_status(
    ctx: ImportContext,
    evidence: dict[str, list[dict[str, Any]]],
    results: dict[str, dict[str, Any]],
) -> list[dict[str, str]]:
    candidates = {row["camera_id"]: row for row in ctx.candidates}
    verified = {row["camera_id"] for row in ctx.cameras}
    battery_models = {row["battery_id"]: row["model"] for row in ctx.batteries}
    rows = []
    for camera_id in INITIAL_TEST_IDS:
        candidate = candidates.get(camera_id, {"display_name": camera_id})
        compat = [row for row in ctx.compatibility if row["camera_id"] == camera_id]
        if results.get(camera_id, {}).get("status") == "promoted":
            battery = results[camera_id]["battery"]
            status = "promoted in Phase 11 direct research"
        elif results.get(camera_id, {}).get("status") == "would_promote":
            battery = results[camera_id]["battery"]
            status = "direct evidence ready"
        elif camera_id in verified:
            battery = ", ".join(sorted({battery_models.get(row["battery_id"], row["battery_id"]) for row in compat}))
            status = "already verified before Phase 11"
        elif camera_id in evidence:
            battery = evidence[camera_id][0].get("battery_model", "")
            status = "direct evidence ready"
        else:
            battery = ""
            status = "unresolved; no reviewed evidence"
        rows.append({"camera": candidate.get("display_name", camera_id), "battery": battery, "status": status})
    return rows


def current_verified_result(ctx: ImportContext, candidate: dict[str, Any]) -> dict[str, Any] | None:
    batteries = {row["battery_id"]: row["model"] for row in ctx.batteries}
    rows = [row for row in ctx.compatibility if row["camera_id"] == candidate["camera_id"]]
    if not rows:
        return None
    row = sorted(rows, key=lambda item: (item["confidence"] != "high", item["source_type"]))[0]
    models = sorted({batteries.get(item["battery_id"], item["battery_id"]) for item in rows})
    return {
        "camera_id": candidate["camera_id"],
        "camera": candidate["display_name"],
        "brand": candidate["brand"],
        "aliases": [],
        "battery": ", ".join(models),
        "source_name": row["source_name"],
        "source_type": row["source_type"],
        "source_url": row["source_url"],
        "source_text": row.get("note", ""),
        "decision": "no_change",
        "confidence": row["confidence"],
        "status": "already_verified",
        "reason": "Camera already has source-backed compatibility in the database.",
    }


def write_report(
    path: Path,
    mode: str,
    selected: list[dict[str, Any]],
    results: list[dict[str, Any]],
    ctx: ImportContext,
    evidence: dict[str, list[dict[str, Any]]],
    before: dict[str, int],
    after: dict[str, int],
) -> None:
    by_id = {row["camera_id"]: row for row in results}
    lines = [
        "# Direct Agent Research Battery Verification",
        "",
        f"Mode: {mode}",
        f"Generated: {ctx.today}",
        "",
        "Only evidence with an exact model name, an explicit battery/power statement, and a source URL can be applied. Rows marked queued have not been researched sufficiently and do not alter verified data.",
        "",
        "## Coverage Delta",
        "",
        "| Metric | Before | After | Delta |",
        "| --- | ---: | ---: | ---: |",
    ]
    for key in ["verified_cameras", "unresolved_models", "compatibility_rows", "batteries", "candidates", "suggestions"]:
        lines.append(f"| {key} | {before[key]} | {after[key]} | {after[key] - before[key]} |")
    lines.extend(["", "## Initial Test Batch", "", "| Camera | Battery | Status |", "| --- | --- | --- |"])
    for row in initial_status(ctx, evidence, by_id):
        lines.append(f"| {cell(row['camera'])} | {cell(row['battery'])} | {cell(row['status'])} |")
    lines.extend(
        [
            "",
            "## Reviewed And Queued Candidates",
            "",
            "| Camera | Alias found | Battery found | Source | Source text | Decision | Confidence | Reason |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for candidate in selected:
        result = by_id.get(candidate["camera_id"])
        if result:
            lines.append(
                f"| {cell(result['camera'])} | {cell(result['aliases'])} | {cell(result['battery'])} | "
                f"[{cell(result['source_name'])}]({result['source_url']}) ({cell(result['source_type'])}) | {cell(result['source_text'])} | "
                f"{cell(result['decision'])} ({cell(result['status'])}) | {cell(result['confidence'])} | {cell(result['reason'])} |"
            )
        else:
            lines.append(
                f"| {cell(candidate['display_name'])} |  |  |  |  | remain_unresolved (queued) |  | "
                "Queued for direct research; no reviewed battery evidence recorded. |"
            )
    unreviewed = [row for row in selected if row["camera_id"] not in by_id][:10]
    if unreviewed:
        lines.extend(["", "## Next Research Tasks", ""])
        for candidate in unreviewed:
            lines.append(f"- `{cell(research_prompt(candidate))}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def save_state(before: dict[str, int], after: dict[str, int], results: list[dict[str, Any]]) -> None:
    if STATE_PATH.exists():
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    else:
        state = {"before": before, "promoted_camera_ids": [], "suggested_camera_ids": []}
    state["promoted_camera_ids"] = sorted(
        {
            *state["promoted_camera_ids"],
            *(row["camera_id"] for row in results if row["status"] == "promoted"),
        }
    )
    state["suggested_camera_ids"] = sorted(
        {
            *state["suggested_camera_ids"],
            *(row["camera_id"] for row in results if row["status"] == "suggested"),
        }
    )
    state["after"] = after
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def execute(limit: int, query: str | None, apply: bool) -> dict[str, Any]:
    ctx = ImportContext.load(ROOT)
    suggestions = load_array(SUGGESTIONS_PATH)
    evidence = evidence_by_id()
    before = state_counts(ctx, suggestions)
    if query:
        candidate = resolve_one(ctx, query)
        if candidate is None:
            raise ValueError(f"Query does not resolve to exactly one catalog candidate: {query}")
        selected = [candidate]
    else:
        selected = balanced_queue(ctx, limit, set(evidence))
    results = []
    for candidate in selected:
        for row in evidence.get(candidate["camera_id"], []):
            results.append(evaluate(ctx, suggestions, candidate, row, apply))
        if query and not evidence.get(candidate["camera_id"]):
            current = current_verified_result(ctx, candidate)
            if current:
                results.append(current)
    if apply:
        dedupe_compatibility_for_app_output(ctx)
        validate(ctx.cameras, ctx.batteries, ctx.compatibility, ctx.candidates, ctx.sources, ctx.unresolved, suggestions)
        ctx.write_all()
        write_json(SUGGESTIONS_PATH, sorted(suggestions, key=lambda row: (row["camera_id"], row["source_url"])))
    after = state_counts(ctx, suggestions)
    REPORT_DIR.mkdir(exist_ok=True)
    output = APPLY_REPORT if apply else DRY_RUN_REPORT
    write_report(output, "apply" if apply else "dry-run", selected, results, ctx, evidence, before, after)
    if apply:
        save_state(before, after, results)
    return {"before": before, "after": after, "selected": selected, "results": results, "report": output}


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply agent-reviewed, per-camera battery research evidence.")
    parser.add_argument("--one", help="Audit or apply one exact candidate display name/alias.")
    parser.add_argument("--limit", type=int, default=100, help="Balanced unresolved queue size for batch mode.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Write review report without changing database JSON.")
    mode.add_argument("--apply", action="store_true", help="Apply only evidence passing the strict source policy.")
    args = parser.parse_args()
    outcome = execute(max(1, args.limit), args.one, args.apply)
    print(f"Mode: {'apply' if args.apply else 'dry-run'}")
    print(f"Scope: {args.one or f'balanced batch limit={args.limit}'}")
    print(f"Selected candidates: {len(outcome['selected'])}")
    for key, value in outcome["before"].items():
        print(f"{key}: {value} -> {outcome['after'][key]}")
    for result in outcome["results"]:
        print(f"{result['camera']}: {result['decision']} ({result['status']}) -> {result['battery']} [{result['source_type']}]")
    if args.one and not outcome["results"]:
        print("No reviewed evidence is recorded for this candidate; no battery mapping proposed.")
        print(research_prompt(outcome["selected"][0]))
    print(f"Report: {outcome['report'].relative_to(ROOT)}")


if __name__ == "__main__":
    main()
