from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from collections import Counter
from pathlib import Path

from importers.common import (
    ImportContext,
    add_compatibility_source_backed,
    battery_record,
    dedupe_compatibility_for_app_output,
    exact_model_match,
    register_source,
    validate_url,
)
from validate_and_export import validate


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
REPORT_DIR = ROOT / "reports"
EVIDENCE_PATH = DATA_DIR / "web_assisted_battery_evidence.json"
SUGGESTIONS_PATH = DATA_DIR / "battery_suggestions.json"
MANUAL_SOURCES_PATH = DATA_DIR / "manual_battery_sources.json"

PRIORITY_BRANDS = ["Sony", "Nikon", "Fujifilm", "Panasonic", "Olympus", "Casio", "Samsung", "Kodak"]
POPULAR_TERMS = [
    "HX95",
    "HX90V",
    "HX80",
    "HX50V",
    "WX500",
    "WX350",
    "P1000",
    "P950",
    "P900",
    "F31FD",
    "F200EXR",
    "XP140",
    "XP130",
    "XP120",
    "TZ90",
    "ZS70",
    "LX7",
    "FZ200",
    "TG-5",
    "TG-4",
    "EX-ZR",
    "WB350",
    "DV300",
    "C713",
    "M530",
]

DIRECT_VERIFIED_TYPES = {"official_manual", "official_accessory_page"}
MEDIUM_VERIFIED_TYPES = {"manual_mirror", "trusted_database"}
SUGGESTION_TYPES = {"retailer", "third_party_chart"}
WARNING_TEXT = "Not verified official compatibility; do not treat this suggestion as a confirmed compatible battery."


def load_array(path: Path) -> list[dict]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{path.relative_to(ROOT)} must contain a JSON array")
    return data


def write_array(path: Path, rows: list[dict]) -> None:
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").casefold())


def camera_aliases(candidate: dict) -> list[str]:
    aliases = [candidate["display_name"], candidate["model"], *candidate.get("aliases", [])]
    for names in (candidate.get("regional_names") or {}).values():
        aliases.extend(names)
    return [value for value in aliases if value]


def evidence_text(evidence: dict, candidate: dict) -> str:
    return evidence["source_text_template"].format(
        display_name=candidate["display_name"],
        model=candidate["model"],
    )


def source_text_confirms_model(candidate: dict, text: str) -> bool:
    return exact_model_match(candidate["model"], text, camera_aliases(candidate))


def source_text_confirms_battery(evidence: dict, text: str) -> bool:
    model = evidence.get("battery_model", "").strip()
    if not model:
        return False
    if normalize(model) == "aa":
        battery_match = bool(re.search(r"\bAA\b", text, re.I))
    elif normalize(model) == "aaa":
        battery_match = bool(re.search(r"\bAAA\b", text, re.I))
    else:
        battery_match = normalize(model) in normalize(text)
    if not battery_match:
        return False
    if not re.search(r"\b(?:battery|batteries|power|compatible|uses|rechargeable)\b", text, re.I):
        return False
    negative_only = re.search(r"\b(?:battery charger|AC adapter|internal memory|flash memory|built-in flash)\b", text, re.I)
    direct_battery = re.search(r"\b(?:battery pack|battery type|power|compatible|uses|rechargeable (?:lithium[- ]ion )?battery|batteries AA)\b", text, re.I)
    return not negative_only or bool(direct_battery)


def allowed_decision(evidence: dict) -> tuple[str, str]:
    source_type = evidence.get("source_type")
    confidence = evidence.get("confidence")
    decision = evidence.get("decision")
    if decision == "promote_verified":
        if source_type in DIRECT_VERIFIED_TYPES and confidence == "high":
            return decision, "Official manufacturer/manual/accessory source explicitly identifies the camera and battery."
        if source_type in MEDIUM_VERIFIED_TYPES and confidence == "medium":
            return decision, "Clear manual mirror or trusted database evidence permits medium-confidence verified mapping."
        return "keep_unresolved", "Verified promotion rejected: source type/confidence does not meet promotion policy."
    if decision == "add_suggestion" and source_type in SUGGESTION_TYPES and confidence in {"low", "medium"}:
        return decision, "Retailer or third-party evidence is retained only as an unverified suggestion."
    return "keep_unresolved", "Evidence decision or source classification is outside the accepted policy."


def mapping_for(evidence: dict) -> tuple[dict, str, int | None]:
    battery_model = evidence["battery_model"]
    status = evidence.get("status") or "fully_compatible"
    quantity = evidence.get("quantity_required", 1)
    if normalize(battery_model) == "aa":
        status = "uses_aa"
        quantity = evidence.get("quantity_required")
        return battery_record("Generic", "AA", "Source-backed AA battery format."), status, quantity
    if normalize(battery_model) == "aaa":
        status = "uses_aaa"
        quantity = evidence.get("quantity_required")
        return battery_record("Generic", "AAA", "Source-backed AAA battery format."), status, quantity
    return (
        battery_record(
            evidence.get("battery_brand") or "Generic",
            battery_model,
            "Added by web-assisted verifier from an explicit source-backed battery mapping.",
        ),
        status,
        quantity,
    )


def priority_score(row: dict) -> int:
    text = f"{row.get('display_name', '')} {row.get('series', '')}".upper()
    brand_score = 0
    if row["brand"] in PRIORITY_BRANDS:
        brand_score = (len(PRIORITY_BRANDS) - PRIORITY_BRANDS.index(row["brand"])) * 1000
    practical_score = sum(300 for term in POPULAR_TERMS if term in text)
    year_score = row.get("release_year") or 0
    return brand_score + practical_score + year_score


def build_search_queries(row: dict) -> list[str]:
    display = row["display_name"]
    brand = row["brand"]
    model = row["display_name"].removeprefix(f"{brand} ").strip()
    return [
        f"{display} battery",
        f"{brand} {model} battery",
        f"{display} battery pack",
        f"{display} power source",
        f"{display} specifications battery",
        f"{display} manual battery",
        f"{model} battery type",
        f"{model} compatible battery",
    ]


def suggestion_row(evidence: dict, candidate: dict, text: str, ctx: ImportContext) -> dict:
    battery_id = None
    target = normalize(evidence["battery_model"])
    for battery in ctx.batteries:
        if normalize(battery["model"]) == target:
            battery_id = battery["battery_id"]
            break
    return {
        "camera_id": candidate["camera_id"],
        "display_name": candidate["display_name"],
        "brand": candidate["brand"],
        "suggested_battery_model": evidence["battery_model"],
        "suggested_battery_id": battery_id,
        "evidence_type": evidence["evidence_type"],
        "source_name": evidence["source_name"],
        "source_url": evidence["source_url"],
        "source_text": text,
        "confidence": evidence["confidence"],
        "warning": WARNING_TEXT,
        "last_checked": ctx.today,
    }


def update_unresolved_checked_source(ctx: ImportContext, camera_id: str, url: str) -> None:
    for row in ctx.unresolved:
        if row["camera_id"] != camera_id:
            continue
        row["checked_source_urls"] = list(dict.fromkeys([*row.get("checked_source_urls", []), url]))
        row["last_checked"] = ctx.today
        return


def process_evidence(ctx: ImportContext, evidence_rows: list[dict], suggestions: list[dict], apply: bool) -> tuple[list[dict], list[dict]]:
    candidates = {row["camera_id"]: row for row in ctx.candidates}
    initially_unresolved = {row["camera_id"] for row in ctx.unresolved}
    proposed: list[dict] = []
    additions: list[dict] = []
    suggestion_keys = {
        (row["camera_id"], normalize(row["suggested_battery_model"]), row["source_url"])
        for row in suggestions
    }

    for evidence in evidence_rows:
        source_url = evidence.get("source_url", "")
        if not validate_url(source_url):
            raise ValueError(f"Invalid evidence source URL: {source_url}")
        policy_action, policy_reason = allowed_decision(evidence)
        for camera_id in evidence.get("camera_ids", []):
            candidate = candidates.get(camera_id)
            if candidate is None:
                proposed.append({"camera_id": camera_id, "camera": camera_id, "battery": evidence.get("battery_model", ""), "source_url": source_url, "source_type": evidence.get("source_type", ""), "text": "", "action": "keep_unresolved", "reason": "Candidate ID is not present in camera_candidates.json."})
                continue
            if camera_id not in initially_unresolved and not evidence.get("apply_to_verified"):
                if evidence.get("decision") == "promote_verified":
                    expected_battery, expected_status, _ = mapping_for(evidence)
                    retained = any(
                        row["camera_id"] == camera_id
                        and row["battery_id"] == expected_battery["battery_id"]
                        and row["status"] == expected_status
                        and row["source_url"] == source_url
                        for row in ctx.compatibility
                    )
                    if retained:
                        text = evidence_text(evidence, candidate)
                        proposed.append(
                            {
                                "camera_id": camera_id,
                                "camera": candidate["display_name"],
                                "brand": candidate["brand"],
                                "series": candidate["series"],
                                "battery": evidence["battery_model"],
                                "source_url": source_url,
                                "source_name": evidence["source_name"],
                                "source_type": evidence["source_type"],
                                "confidence": evidence["confidence"],
                                "text": text,
                                "action": "promote_verified",
                                "reason": "Explicit accepted evidence was already applied; mapping retained idempotently.",
                            }
                        )
                continue
            text = evidence_text(evidence, candidate)
            action = policy_action
            reason = policy_reason
            if not source_text_confirms_model(candidate, text):
                action = "keep_unresolved"
                reason = "Evidence text does not identify the exact candidate model."
            elif not source_text_confirms_battery(evidence, text):
                action = "keep_unresolved"
                reason = "Evidence text does not explicitly identify a battery or power source."
            proposed.append(
                {
                    "camera_id": camera_id,
                    "camera": candidate["display_name"],
                    "brand": candidate["brand"],
                    "series": candidate["series"],
                    "battery": evidence["battery_model"],
                    "source_url": source_url,
                    "source_name": evidence["source_name"],
                    "source_type": evidence["source_type"],
                    "confidence": evidence["confidence"],
                    "text": text,
                    "action": action,
                    "reason": reason,
                }
            )
            if not apply or action == "keep_unresolved":
                continue
            if action == "promote_verified":
                battery, status, quantity = mapping_for(evidence)
                existing_exact = any(
                    row["camera_id"] == camera_id
                    and row["battery_id"] == battery["battery_id"]
                    and row["status"] == status
                    and row["source_url"] == source_url
                    for row in ctx.compatibility
                )
                removed_superseded = False
                superseded_urls = set(evidence.get("supersedes_source_urls", []))
                if superseded_urls:
                    kept_rows = []
                    for row in ctx.compatibility:
                        is_superseded = (
                            row["camera_id"] == camera_id
                            and row["battery_id"] == battery["battery_id"]
                            and row["status"] == status
                            and row["source_url"] in superseded_urls
                        )
                        if is_superseded:
                            removed_superseded = True
                        else:
                            kept_rows.append(row)
                    ctx.compatibility = kept_rows
                source_candidate = copy.deepcopy(candidate)
                source_candidate["candidate_source_name"] = evidence["source_name"]
                source_candidate["candidate_source_url"] = source_url
                source_candidate["candidate_source_type"] = evidence["source_type"]
                source_candidate["candidate_batch"] = "web_assisted_battery_verification"
                note = text
                if status in {"uses_aa", "uses_aaa"} and quantity is None:
                    note += " Source confirms battery type but quantity was not explicitly extracted."
                add_compatibility_source_backed(
                    ctx,
                    source_candidate,
                    battery,
                    status,
                    quantity,
                    note,
                    evidence["source_name"],
                    source_url,
                    evidence["source_type"],
                    evidence["confidence"],
                    evidence.get("publisher") or candidate["brand"],
                )
                if not existing_exact or removed_superseded:
                    additions.append({**proposed[-1], "status": status})
            elif action == "add_suggestion":
                row = suggestion_row(evidence, candidate, text, ctx)
                key = (row["camera_id"], normalize(row["suggested_battery_model"]), row["source_url"])
                if key not in suggestion_keys:
                    suggestions.append(row)
                    suggestion_keys.add(key)
                    additions.append({**proposed[-1], "status": "suggestion_only"})
                register_source(
                    ctx,
                    evidence["source_name"],
                    source_url,
                    evidence["source_type"],
                    evidence.get("publisher") or candidate["brand"],
                    "Unverified battery suggestion only; this source does not create compatibility.",
                )
                update_unresolved_checked_source(ctx, camera_id, source_url)
    return proposed, additions


def write_report(
    ctx: ImportContext,
    before: dict,
    after: dict,
    evidence_rows: list[dict],
    proposed: list[dict],
    additions: list[dict],
    suggestions: list[dict],
    queue: list[tuple[dict, list[str]]],
    mode: str,
    manual_count: int,
) -> None:
    promoted = [row for row in additions if row.get("action") == "promote_verified"]
    new_suggestions = [row for row in additions if row.get("action") == "add_suggestion"]
    brand_counts = Counter(row["brand"] for row in promoted)
    source_counts = Counter((row["source_type"], row["confidence"]) for row in promoted)
    still_unresolved = sorted(ctx.unresolved, key=lambda row: (-priority_score(row), row["brand"], row["display_name"]))
    evidence_sources = {(row.get("source_name"), row.get("source_url")) for row in evidence_rows if row.get("decision") == "promote_verified"}
    cumulative_rows = [
        row for row in ctx.compatibility if (row["source_name"], row["source_url"]) in evidence_sources
    ]
    cumulative_camera_ids = {row["camera_id"] for row in cumulative_rows}
    camera_by_id = {row["camera_id"]: row for row in ctx.cameras}
    cumulative_brand_counts = Counter(camera_by_id[camera_id]["brand"] for camera_id in cumulative_camera_ids)
    cumulative_source_counts = Counter((row["source_type"], row["confidence"]) for row in cumulative_rows)
    cumulative_battery_ids = {row["battery_id"] for row in cumulative_rows}
    non_phase_battery_ids = {
        row["battery_id"]
        for row in ctx.compatibility
        if (row["source_name"], row["source_url"]) not in evidence_sources
    }
    phase_new_battery_count = len(cumulative_battery_ids - non_phase_battery_ids)
    cumulative_suggestions = [
        row for row in suggestions
        if any(row["source_name"] == evidence.get("source_name") and row["source_url"] == evidence.get("source_url") for evidence in evidence_rows)
    ]
    cumulative_before = {
        "verified_cameras": after["verified_cameras"] - len(cumulative_camera_ids),
        "unresolved": after["unresolved"] + len(cumulative_camera_ids),
        "compatibility_rows": after["compatibility_rows"] - len(cumulative_rows),
        "batteries": after["batteries"] - phase_new_battery_count,
        "suggestions": after["suggestions"] - len(cumulative_suggestions),
    }
    lines = [
        "# Web-Assisted Verification Candidates",
        "",
        f"Generated: {ctx.today}",
        f"Mode: {mode}",
        "",
        "## Policy",
        "",
        "- `promote_verified`: official source or explicit accepted manual/trusted evidence only.",
        "- `add_suggestion`: retailer/third-party evidence remains unverified and never creates compatibility.",
        "- Matching is by existing `camera_id` plus exact model token in evidence; no series inference is performed.",
        "",
        "## Cumulative Phase 6 Summary",
        "",
        "| Metric | Before | After | Delta |",
        "| --- | ---: | ---: | ---: |",
    ]
    for key in ["verified_cameras", "unresolved", "compatibility_rows", "batteries", "suggestions"]:
        lines.append(f"| {key} | {cumulative_before[key]} | {after[key]} | {after[key] - cumulative_before[key]} |")
    lines.extend(
        [
            "",
            "## Current Run",
            "",
            "| Metric | Before | After | Delta |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for key in ["verified_cameras", "unresolved", "compatibility_rows", "batteries", "suggestions"]:
        lines.append(f"| {key} | {before[key]} | {after[key]} | {after[key] - before[key]} |")
    lines.extend(
        [
            "",
            f"- Reviewed evidence actions: {len(proposed)}",
            f"- Applied verified promotions: {len(promoted)}",
            f"- Applied unverified suggestions: {len(new_suggestions)}",
            f"- Existing manual battery inputs read: {manual_count}",
            f"- Priority unresolved search queues generated: {len(queue)} models / {len(queue) * 8} queries",
            "",
            "## Verified Additions By Brand",
            "",
            "| Brand | Models promoted |",
            "| --- | ---: |",
        ]
    )
    if cumulative_brand_counts:
        lines.extend(f"| {brand} | {count} |" for brand, count in cumulative_brand_counts.most_common())
    else:
        lines.append("| None | 0 |")
    lines.extend(["", "## Verified Source Quality", "", "| Source type | Confidence | Rows |", "| --- | --- | ---: |"])
    if cumulative_source_counts:
        lines.extend(f"| {source_type} | {confidence} | {count} |" for (source_type, confidence), count in cumulative_source_counts.most_common())
    else:
        lines.append("| None |  | 0 |")
    lines.extend(
        [
            "",
            "## Evidence Decisions",
            "",
            "| Camera | Proposed battery | Source type | Confidence | Action | Evidence text | Source URL | Reason |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in proposed:
        fields = [row.get(key, "") for key in ["camera", "battery", "source_type", "confidence", "action", "text", "source_url", "reason"]]
        clean = [str(value).replace("|", "/").replace("\n", " ") for value in fields]
        lines.append("| " + " | ".join(clean) + " |")
    lines.extend(["", "## Cumulative Verified Rows From Phase Evidence", "", "| Camera | Battery ID | Source type | Confidence | Source URL |", "| --- | --- | --- | --- | --- |"])
    for row in sorted(cumulative_rows, key=lambda item: (item["camera_id"], item["battery_id"], item["source_url"])):
        lines.append(f"| {camera_by_id[row['camera_id']]['display_name']} | {row['battery_id']} | {row['source_type']} | {row['confidence']} | {row['source_url']} |")
    lines.extend(["", "## Unverified Suggestions Stored", "", "| Camera | Suggested battery | Source | Confidence | Warning |", "| --- | --- | --- | --- | --- |"])
    if suggestions:
        for row in suggestions:
            lines.append(f"| {row['display_name']} | {row['suggested_battery_model']} | {row['source_url']} | {row['confidence']} | {row['warning']} |")
    else:
        lines.append("| None |  |  |  |  |")
    lines.extend(["", "## Priority Search Query Queue Sample", "", "| Camera | Example generated queries |", "| --- | --- |"])
    for row, queries in queue[:20]:
        lines.append(f"| {row['display_name']} | {queries[0]}; {queries[2]}; {queries[5]} |")
    lines.extend(["", "## Popular Models Still Unresolved", "", "| Camera | Brand | Series | Candidate source |", "| --- | --- | --- | --- |"])
    for row in still_unresolved[:20]:
        lines.append(f"| {row['display_name']} | {row['brand']} | {row['series']} | {row['candidate_source_url']} |")
    REPORT_DIR.mkdir(exist_ok=True)
    (REPORT_DIR / "web_assisted_verification_candidates.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(apply: bool) -> dict:
    ctx = ImportContext.load(ROOT)
    evidence_rows = load_array(EVIDENCE_PATH)
    suggestions = load_array(SUGGESTIONS_PATH)
    manual_sources = load_array(MANUAL_SOURCES_PATH)
    before = {
        "verified_cameras": len(ctx.cameras),
        "unresolved": len(ctx.unresolved),
        "compatibility_rows": len(ctx.compatibility),
        "batteries": len(ctx.batteries),
        "suggestions": len(suggestions),
    }
    priority_rows = sorted(ctx.unresolved, key=lambda row: (-priority_score(row), row["display_name"]))[:200]
    queue = [(row, build_search_queries(row)) for row in priority_rows]
    proposed, additions = process_evidence(ctx, evidence_rows, suggestions, apply)
    if apply:
        dedupe_compatibility_for_app_output(ctx)
        ctx.sort_all()
        suggestions.sort(key=lambda row: (row["brand"], row["display_name"], row["suggested_battery_model"], row["source_url"]))
        validate(ctx.cameras, ctx.batteries, ctx.compatibility, ctx.candidates, ctx.sources, ctx.unresolved, suggestions)
        ctx.write_all()
        write_array(SUGGESTIONS_PATH, suggestions)
    after = {
        "verified_cameras": len(ctx.cameras),
        "unresolved": len(ctx.unresolved),
        "compatibility_rows": len(ctx.compatibility),
        "batteries": len(ctx.batteries),
        "suggestions": len(suggestions),
    }
    write_report(ctx, before, after, evidence_rows, proposed, additions, suggestions, queue, "apply" if apply else "dry-run", len(manual_sources))
    return {"mode": "apply" if apply else "dry-run", "before": before, "after": after, "reviewed": len(proposed), "applied": len(additions)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Review curated web-assisted battery evidence without inferring compatibility.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Generate a report without modifying JSON data (default).")
    mode.add_argument("--apply", action="store_true", help="Apply accepted verified mappings and suggestions.")
    args = parser.parse_args()
    try:
        summary = run(apply=args.apply)
    except Exception as exc:
        print(f"Web-assisted verifier failed without committing partial writes: {exc}")
        return 1
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
