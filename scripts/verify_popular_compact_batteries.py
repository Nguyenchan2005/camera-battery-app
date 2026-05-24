from __future__ import annotations

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
    parse_power_mappings,
    validate_url,
)
from validate_and_export import validate


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
REPORT_DIR = ROOT / "reports"
INPUT_PATH = DATA_DIR / "manual_battery_sources.json"

PRIORITY_BRANDS = ["Sony", "Nikon", "Fujifilm", "Panasonic", "Olympus", "Casio", "Samsung", "Kodak"]
PRIORITY_SERIES_TERMS = [
    "Cyber-shot DSC-T",
    "Cyber-shot DSC-W",
    "Cyber-shot DSC-WX",
    "Cyber-shot DSC-HX",
    "Cyber-shot DSC-H",
    "COOLPIX S",
    "COOLPIX P",
    "COOLPIX L",
    "COOLPIX AW",
    "COOLPIX W",
    "FinePix F",
    "FinePix Z",
    "FinePix XP",
    "FinePix J",
    "FinePix A",
    "FinePix S",
    "Lumix TZ/ZS",
    "Lumix FX",
    "Lumix FS",
    "Lumix LX",
    "Lumix FZ",
    "Lumix TS/FT",
    "Tough",
    "TG",
    "Stylus",
    "mju",
    "FE",
    "SP",
    "XZ",
    "Exilim Z",
    "Exilim H",
    "Exilim FC",
    "Exilim TR",
    "QV",
    "WB",
    "ST",
    "PL",
    "DV",
    "Digimax",
    "EasyShare C",
    "EasyShare M",
    "EasyShare Z",
]

BANNED_ONLY_PATTERNS = [
    r"\bbattery charger\b",
    r"\bAC adapter\b",
    r"\binternal memory\b",
    r"\bflash memory\b",
    r"\bbuilt[- ]?in flash\b",
    r"\boptional accessor(?:y|ies)\b",
]

POWER_CONTEXT_PATTERN = (
    r"\b(?:battery|batteries|battery pack|battery system|power|supplied|included|compatible|uses|use|rechargeable)\b|"
    r"(?:batteria|batterie|bateria)|"
    "(?:\\u30d0\\u30c3\\u30c6\\u30ea\\u30fc|\\u96fb\\u6c60|\\u5145\\u96fb\\u6c60|\\u4ed8\\u5c5e|\\u5bfe\\u5fdc)"
)

EXPLICIT_BATTERY_CONTEXT_PATTERN = (
    r"\b(?:battery pack|battery system|supplied battery|uses one|compatible|rechargeable battery)\b|"
    "(?:\\u30d0\\u30c3\\u30c6\\u30ea\\u30fc\\u30d1\\u30c3\\u30af|\\u30ea\\u30c1\\u30a6\\u30e0\\u30a4\\u30aa\\u30f3|\\u5145\\u96fb\\u6c60|\\u4ed8\\u5c5e)"
)


def load_manual_sources() -> list[dict]:
    if not INPUT_PATH.exists():
        return []
    data = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("data/manual_battery_sources.json must be a JSON array")
    return data


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").casefold())


def compact_contains_model(haystack: str, needle: str) -> bool:
    if len(needle) < 5:
        return False
    start = haystack.find(needle)
    if start < 0:
        return False
    end = start + len(needle)
    if end < len(haystack) and needle[-1].isdigit() and haystack[end].isdigit():
        return False
    if start > 0 and needle[0].isdigit() and haystack[start - 1].isdigit():
        return False
    return True


def camera_aliases(candidate: dict) -> list[str]:
    aliases = [candidate["display_name"], candidate["model"], *candidate.get("aliases", [])]
    for names in (candidate.get("regional_names") or {}).values():
        aliases.extend(names)
    return [item for item in aliases if item]


def find_candidate(ctx: ImportContext, query: str) -> dict | None:
    verified_ids = {camera["camera_id"] for camera in ctx.cameras}
    candidates = sorted(
        ctx.candidates,
        key=lambda row: (
            row["camera_id"] in verified_ids,
            0 if row["brand"] in PRIORITY_BRANDS else 1,
            row["display_name"],
        ),
    )
    q = normalize(query)
    mentioned_brands = {normalize(brand) for brand in PRIORITY_BRANDS if normalize(brand) in q}
    for candidate in candidates:
        if q in {normalize(alias) for alias in camera_aliases(candidate)}:
            return candidate
    for candidate in candidates:
        brand_key = normalize(candidate["brand"])
        if mentioned_brands and brand_key not in mentioned_brands:
            continue
        for alias in camera_aliases(candidate):
            alias_key = normalize(alias)
            if compact_contains_model(q, alias_key) or compact_contains_model(alias_key, q):
                return candidate
        model_key = normalize(candidate["model"])
        if compact_contains_model(q, model_key):
            return candidate
    return None


def text_confirms_model(candidate: dict, source_text: str, source_url: str) -> bool:
    aliases = camera_aliases(candidate)
    if exact_model_match(candidate["model"], source_text, aliases):
        return True
    compact_url = normalize(source_url)
    for alias in aliases:
        key = normalize(alias)
        if key and len(key) >= 6 and key in compact_url:
            return True
    return False


def text_confirms_battery(entry: dict) -> bool:
    source_text = entry.get("source_text", "")
    battery_model = entry.get("battery_model", "")
    if not source_text or not battery_model:
        return False
    source_key = normalize(source_text)
    battery_key = normalize(battery_model)
    if battery_key not in source_key:
        return False
    has_positive_power_context = bool(re.search(POWER_CONTEXT_PATTERN, source_text, re.I))
    if not has_positive_power_context:
        return False
    if any(re.search(pattern, source_text, re.I) for pattern in BANNED_ONLY_PATTERNS):
        return bool(re.search(EXPLICIT_BATTERY_CONTEXT_PATTERN, source_text, re.I))
    return True


def source_type_confidence_ok(entry: dict) -> bool:
    return entry.get("source_type") in {
        "official_manual",
        "official_accessory_page",
        "trusted_database",
        "manual_mirror",
        "retailer",
        "third_party_chart",
    } and entry.get("confidence") in {"high", "medium", "low"}


def mapping_from_entry(entry: dict, candidate: dict) -> dict:
    source_text = entry["source_text"]
    parsed = [mapping for mapping in parse_power_mappings(source_text, entry.get("battery_brand") or candidate["brand"]) if normalize(mapping["model"]) == normalize(entry["battery_model"])]
    if parsed:
        mapping = parsed[0]
    else:
        model = entry["battery_model"]
        if normalize(model) == "aa":
            mapping = {"brand": "Generic", "model": "AA", "status": "uses_aa", "quantity_required": entry.get("quantity_required")}
        elif normalize(model) == "aaa":
            mapping = {"brand": "Generic", "model": "AAA", "status": "uses_aaa", "quantity_required": entry.get("quantity_required")}
        elif normalize(model) in {"builtin", "builtinbattery"}:
            mapping = {"brand": "Generic", "model": "Built-in", "status": "built_in_battery", "quantity_required": 1}
        else:
            mapping = {"brand": entry.get("battery_brand") or candidate["brand"], "model": model, "status": "fully_compatible", "quantity_required": 1}
    if entry.get("compatibility_status"):
        mapping["status"] = entry["compatibility_status"]
    if "quantity_required" in entry:
        mapping["quantity_required"] = entry["quantity_required"]
    return mapping


def popular_score(row: dict) -> int:
    score = 0
    if row["brand"] in PRIORITY_BRANDS:
        score += (len(PRIORITY_BRANDS) - PRIORITY_BRANDS.index(row["brand"])) * 100
    text = f"{row.get('series', '')} {row.get('display_name', '')}"
    for index, term in enumerate(PRIORITY_SERIES_TERMS):
        if term.lower() in text.lower():
            score += max(1, len(PRIORITY_SERIES_TERMS) - index)
            break
    if isinstance(row.get("release_year"), int):
        score += max(0, row["release_year"] - 1998)
    return score


def promote_from_manual_sources(ctx: ImportContext, entries: list[dict]) -> tuple[list[dict], list[dict]]:
    promoted: list[dict] = []
    skipped: list[dict] = []
    verified_ids = {camera["camera_id"] for camera in ctx.cameras}

    for index, entry in enumerate(entries, start=1):
        query = entry.get("camera_query", "")
        source_url = entry.get("source_url", "")
        source_text = entry.get("source_text", "")
        if not query or not entry.get("battery_model") or not source_url or not source_text:
            skipped.append({"entry": index, "query": query, "reason": "missing camera_query, battery_model, source_url, or source_text"})
            continue
        if not validate_url(source_url):
            skipped.append({"entry": index, "query": query, "reason": "invalid source_url"})
            continue
        if not source_type_confidence_ok(entry):
            skipped.append({"entry": index, "query": query, "reason": "invalid source_type or confidence"})
            continue
        candidate = find_candidate(ctx, query)
        if not candidate:
            skipped.append({"entry": index, "query": query, "reason": "candidate not found"})
            continue
        if candidate["camera_id"] in verified_ids:
            skipped.append({"entry": index, "query": query, "camera_id": candidate["camera_id"], "reason": "camera already verified"})
            continue
        if not text_confirms_model(candidate, source_text, source_url):
            skipped.append({"entry": index, "query": query, "camera_id": candidate["camera_id"], "reason": "source_text/source_url does not confirm exact model"})
            continue
        if not text_confirms_battery(entry):
            skipped.append({"entry": index, "query": query, "camera_id": candidate["camera_id"], "reason": "source_text does not prove the named battery"})
            continue

        mapping = mapping_from_entry(entry, candidate)
        battery = battery_record(
            mapping.get("brand") or entry.get("battery_brand") or candidate["brand"],
            mapping["model"],
            "Added by popular compact verifier from explicit manual_battery_sources.json source text.",
        )
        if entry.get("battery_aliases"):
            battery["aliases"] = entry["battery_aliases"]

        source_candidate = dict(candidate)
        source_candidate["candidate_source_name"] = entry.get("source_name") or f"{candidate['display_name']} battery source"
        source_candidate["candidate_source_url"] = source_url
        source_candidate["candidate_source_type"] = entry["source_type"]
        source_candidate["candidate_batch"] = "popular_compact_manual_battery_sources"

        add_compatibility_source_backed(
            ctx,
            source_candidate,
            battery,
            mapping["status"],
            mapping.get("quantity_required"),
            source_text,
            source_candidate["candidate_source_name"],
            source_url,
            entry["source_type"],
            entry["confidence"],
            entry.get("publisher") or candidate["brand"],
        )
        promoted.append(
            {
                "camera_id": candidate["camera_id"],
                "display_name": candidate["display_name"],
                "brand": candidate["brand"],
                "series": candidate["series"],
                "battery_model": mapping["model"],
                "source_type": entry["source_type"],
                "confidence": entry["confidence"],
                "source_url": source_url,
            }
        )
        verified_ids.add(candidate["camera_id"])

    return promoted, skipped


def write_report(ctx: ImportContext, before: dict, promoted: list[dict], skipped: list[dict], entries: list[dict]) -> None:
    manual_source_urls = {entry["source_url"] for entry in entries if entry.get("source_url")}
    phase_rows = [row for row in ctx.compatibility if row["source_url"] in manual_source_urls]
    phase_camera_ids = {row["camera_id"] for row in phase_rows}
    rows_by_battery = {}
    for row in ctx.compatibility:
        rows_by_battery.setdefault(row["battery_id"], []).append(row)
    phase_only_battery_ids = {
        battery_id
        for battery_id, rows in rows_by_battery.items()
        if rows and all(row["source_url"] in manual_source_urls for row in rows)
    }
    camera_by_id = {row["camera_id"]: row for row in ctx.cameras}
    battery_by_id = {row["battery_id"]: row for row in ctx.batteries}
    cumulative_promoted = [
        {
            "camera_id": camera_id,
            "display_name": camera_by_id[camera_id]["display_name"],
            "brand": camera_by_id[camera_id]["brand"],
            "series": camera_by_id[camera_id]["series"],
            "battery_model": battery_by_id[phase_rows_for_camera[0]["battery_id"]]["model"] if (phase_rows_for_camera := [row for row in phase_rows if row["camera_id"] == camera_id]) else "",
            "source_type": phase_rows_for_camera[0]["source_type"] if phase_rows_for_camera else "",
            "confidence": phase_rows_for_camera[0]["confidence"] if phase_rows_for_camera else "",
            "source_url": phase_rows_for_camera[0]["source_url"] if phase_rows_for_camera else "",
        }
        for camera_id in sorted(phase_camera_ids)
        if camera_id in camera_by_id
    ]
    after = {
        "verified_cameras": len(ctx.cameras),
        "unresolved": len(ctx.unresolved),
        "compatibility_rows": len(ctx.compatibility),
        "batteries": len(ctx.batteries),
    }
    phase_before = {
        "verified_cameras": after["verified_cameras"] - len(phase_camera_ids),
        "unresolved": after["unresolved"] + len(phase_camera_ids),
        "compatibility_rows": after["compatibility_rows"] - len(phase_rows),
        "batteries": after["batteries"] - len(phase_only_battery_ids),
    }
    verified_by_brand = Counter(row["brand"] for row in cumulative_promoted)
    verified_by_series = Counter(row["series"] for row in cumulative_promoted)
    source_breakdown = Counter((row["source_type"], row["confidence"]) for row in cumulative_promoted)
    unresolved_sorted = sorted(ctx.unresolved, key=lambda row: (-popular_score(row), row["brand"], row["display_name"]))
    unresolved_by_brand_series = Counter((row["brand"], row["series"]) for row in unresolved_sorted)

    lines = [
        "# Popular Battery Verification Report",
        "",
        f"Generated: {ctx.today}",
        "",
        "## Summary",
        "",
        "| Metric | Before | After | Delta |",
        "| --- | ---: | ---: | ---: |",
    ]
    for key in ["verified_cameras", "unresolved", "compatibility_rows", "batteries"]:
        lines.append(f"| {key} | {phase_before[key]} | {after[key]} | {after[key] - phase_before[key]} |")
    lines.extend(["", "## Last Run Delta", ""])
    lines.append("| Metric | Before | After | Delta |")
    lines.append("| --- | ---: | ---: | ---: |")
    for key in ["verified_cameras", "unresolved", "compatibility_rows", "batteries"]:
        lines.append(f"| {key} | {before[key]} | {after[key]} | {after[key] - before[key]} |")
    lines.extend(["", "## Verified Added By Brand", "", "| Brand | Added |", "| --- | ---: |"])
    if verified_by_brand:
        for brand, count in sorted(verified_by_brand.items(), key=lambda item: (-item[1], item[0])):
            lines.append(f"| {brand} | {count} |")
    else:
        lines.append("| None | 0 |")
    lines.extend(["", "## Verified Added By Series", "", "| Series | Added |", "| --- | ---: |"])
    if verified_by_series:
        for series, count in sorted(verified_by_series.items(), key=lambda item: (-item[1], item[0])):
            lines.append(f"| {series} | {count} |")
    else:
        lines.append("| None | 0 |")
    lines.extend(["", "## Source Type Breakdown", "", "| Source type | Confidence | Rows |", "| --- | --- | ---: |"])
    if source_breakdown:
        for (source_type, confidence), count in sorted(source_breakdown.items()):
            lines.append(f"| {source_type} | {confidence} | {count} |")
    else:
        lines.append("| None |  | 0 |")
    lines.extend(["", "## Promoted Models", "", "| Camera | Battery | Source type | Confidence | Source URL |", "| --- | --- | --- | --- | --- |"])
    for row in cumulative_promoted:
        lines.append(f"| {row['display_name']} | {row['battery_model']} | {row['source_type']} | {row['confidence']} | {row['source_url']} |")
    lines.extend(["", "## Top Unresolved Remaining By Brand/Series", "", "| Brand | Series | Count |", "| --- | --- | ---: |"])
    for (brand, series), count in unresolved_by_brand_series.most_common(60):
        lines.append(f"| {brand} | {series} | {count} |")
    lines.extend(["", "## Popular Models Still Needing Manual Source", "", "| Camera | Brand | Series | Current reason | Candidate source |", "| --- | --- | --- | --- | --- |"])
    for row in unresolved_sorted[:40]:
        lines.append(f"| {row['display_name']} | {row['brand']} | {row['series']} | {str(row.get('reason', '')).replace('|', '/')} | {row.get('candidate_source_url', '')} |")
    lines.extend(["", "## Skipped Manual Source Rows", ""])
    if skipped:
        lines.append("| Entry | Query | Camera ID | Reason |")
        lines.append("| ---: | --- | --- | --- |")
        for row in skipped:
            lines.append(f"| {row.get('entry', '')} | {row.get('query', '')} | {row.get('camera_id', '')} | {row.get('reason', '')} |")
    else:
        lines.append("- None")

    REPORT_DIR.mkdir(exist_ok=True)
    (REPORT_DIR / "popular_battery_verification_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ctx = ImportContext.load(ROOT)
    before = {
        "verified_cameras": len(ctx.cameras),
        "unresolved": len(ctx.unresolved),
        "compatibility_rows": len(ctx.compatibility),
        "batteries": len(ctx.batteries),
    }
    entries = load_manual_sources()
    promoted, skipped = promote_from_manual_sources(ctx, entries)
    dedupe_compatibility_for_app_output(ctx)
    ctx.sort_all()

    try:
        validate(ctx.cameras, ctx.batteries, ctx.compatibility, ctx.candidates, ctx.sources, ctx.unresolved)
    except Exception as exc:
        print("Popular compact verification failed validation; data/*.json was not modified.")
        print(str(exc))
        return 1

    ctx.write_all()
    write_report(ctx, before, promoted, skipped, entries)
    after = {
        "verified_cameras": len(ctx.cameras),
        "unresolved": len(ctx.unresolved),
        "compatibility_rows": len(ctx.compatibility),
        "batteries": len(ctx.batteries),
    }
    print(json.dumps({"before": before, "after": after, "promoted": promoted, "skipped": skipped}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
