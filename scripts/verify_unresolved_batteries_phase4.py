from __future__ import annotations

import argparse
import importlib
import json
import sys
import traceback
from collections import Counter
from pathlib import Path

from import_missing_user_queries import main as import_manual_missing_queries
from importers.common import ImportContext, dedupe_compatibility_for_app_output
from validate_and_export import validate


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports"

PRIORITY_BRANDS = [
    "Kodak",
    "Kodak PIXPRO",
    "Fujifilm",
    "Casio",
    "Olympus",
    "OM System",
    "Panasonic",
    "Samsung",
    "Sony",
    "Nikon",
    "Pentax",
    "HP",
    "Ricoh",
]

PRIORITY_SERIES_KEYWORDS = [
    ("Kodak EasyShare C", ["Kodak", "EasyShare C"]),
    ("Kodak EasyShare M", ["Kodak", "EasyShare M"]),
    ("Kodak EasyShare Z", ["Kodak", "EasyShare Z"]),
    ("Kodak EasyShare CD/CX/DX", ["Kodak", "EasyShare CD", "EasyShare CX", "EasyShare DX"]),
    ("Fujifilm FinePix A/F/S/Z/XP", ["Fujifilm", "FinePix A", "FinePix F", "FinePix S", "FinePix Z", "FinePix XP"]),
    ("Casio Exilim Z/F/S/H/QV", ["Casio", "Exilim Z", "Exilim F", "Exilim S", "Exilim H", "QV"]),
    ("Olympus C/FE/SP/Tough/TG", ["Olympus", " C", "FE", "SP", "Tough", "TG"]),
    ("Panasonic Lumix FP/FS/FX/FZ/TZ/ZS", ["Panasonic", "Lumix FP", "Lumix FS", "Lumix FX", "Lumix FZ", "Lumix TZ", "Lumix ZS"]),
    ("Samsung Digimax/ST/WB/PL/DV", ["Samsung", "Digimax", "ST", "WB", "PL", "DV"]),
    ("Sony DSC-W/T/H/HX", ["Sony", "DSC-W", "DSC-T", "DSC-H", "DSC-HX"]),
    ("Nikon COOLPIX S/L/P/2xxx/3xxx/4xxx", ["Nikon", "COOLPIX S", "COOLPIX L", "COOLPIX P", "COOLPIX 2", "COOLPIX 3", "COOLPIX 4"]),
    ("Pentax Optio", ["Pentax", "Optio"]),
    ("Ricoh Caplio/CX", ["Ricoh", "Caplio", "CX"]),
]

ONLINE_VERIFIER_MODULES = [
    "verifiers.verify_kodak_batteries",
    "verifiers.verify_fujifilm_batteries",
    "verifiers.verify_casio_batteries",
    "verifiers.verify_olympus_batteries",
    "verifiers.verify_panasonic_batteries",
    "verifiers.verify_samsung_batteries",
    "verifiers.verify_sony_batteries",
    "verifiers.verify_nikon_batteries",
    "verifiers.verify_pentax_ricoh_batteries",
    "verifiers.verify_hp_batteries",
]


def counts(ctx: ImportContext) -> dict[str, int]:
    return {
        "verified_cameras": len(ctx.cameras),
        "batteries": len(ctx.batteries),
        "compatibility_rows": len(ctx.compatibility),
        "candidates": len(ctx.candidates),
        "unresolved": len(ctx.unresolved),
        "sources": len(ctx.sources),
    }


def run_online_verifier(ctx: ImportContext, module_name: str) -> dict:
    module = importlib.import_module(module_name)
    snapshot = ctx.snapshot()
    try:
        result = module.run(ctx)
        result["module"] = module_name
        return result
    except Exception as exc:
        ctx.restore(snapshot)
        return {
            "module": module_name,
            "verifier": module_name,
            "processed": 0,
            "verified": 0,
            "still_unresolved": 0,
            "warnings": [
                {
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                }
            ],
            "checked_urls": [],
            "verified_camera_ids": [],
        }


def priority_brand_score(brand: str) -> int:
    try:
        return len(PRIORITY_BRANDS) - PRIORITY_BRANDS.index(brand)
    except ValueError:
        return 0


def series_bucket(row: dict) -> str:
    text = f"{row.get('brand', '')} {row.get('series', '')} {row.get('display_name', '')} {row.get('model', '')}"
    for label, tokens in PRIORITY_SERIES_KEYWORDS:
        if any(token.lower() in text.lower() for token in tokens[1:]) and tokens[0].lower() in text.lower():
            return label
    return f"{row.get('brand', 'Unknown')} / {row.get('series', 'Unknown')}"


def likely_search_score(row: dict) -> int:
    score = priority_brand_score(row.get("brand", "")) * 100
    series = series_bucket(row)
    if series in {label for label, _ in PRIORITY_SERIES_KEYWORDS}:
        score += 50
    year = row.get("release_year")
    if isinstance(year, int):
        score += max(0, min(25, year - 1998))
    text = f"{row.get('display_name', '')} {row.get('series', '')}".lower()
    for keyword in ["rx", "x100", "gr", "tough", "tg", "coolpix p", "lumix tz", "lumix zs", "finepix f", "easyshare", "exilim"]:
        if keyword in text:
            score += 8
    return score


def markdown_cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def write_count_table(lines: list[str], counts_: Counter, first_col: str, limit: int | None = None) -> None:
    lines.append(f"| {first_col} | Count |")
    lines.append("| --- | ---: |")
    items = sorted(counts_.items(), key=lambda item: (-item[1], item[0]))
    if limit is not None:
        items = items[:limit]
    for label, count in items:
        lines.append(f"| {markdown_cell(label)} | {count} |")


def write_gap_reports(
    ctx: ImportContext,
    before: dict,
    before_verified_ids: set[str],
    verifier_results: list[dict],
    online_enabled: bool,
) -> None:
    REPORT_DIR.mkdir(exist_ok=True)
    after = counts(ctx)
    verified_ids = {row["camera_id"] for row in ctx.cameras}
    unresolved = [row for row in ctx.unresolved if row["camera_id"] not in verified_ids]
    unresolved_by_brand = Counter(row["brand"] for row in unresolved)
    unresolved_by_series = Counter(series_bucket(row) for row in unresolved)
    unresolved_source_types = Counter(row.get("candidate_source_type", "unknown") for row in unresolved)
    unresolved_reasons = Counter(row.get("reason", "unknown") for row in unresolved)
    coverage = (after["verified_cameras"] / after["candidates"] * 100) if after["candidates"] else 0.0
    unresolved_pct = (after["unresolved"] / after["candidates"] * 100) if after["candidates"] else 0.0

    top_unresolved = sorted(unresolved, key=lambda row: (-likely_search_score(row), row["brand"], row["display_name"]))[:50]

    lines = [
        "# Battery Verification Gap Report",
        "",
        f"Generated: {ctx.today}",
        "",
        "## Summary",
        "",
        f"- total candidates: {after['candidates']}",
        f"- verified cameras: {after['verified_cameras']}",
        f"- unresolved cameras: {after['unresolved']}",
        f"- compatibility rows: {after['compatibility_rows']}",
        f"- batteries: {after['batteries']}",
        f"- coverage percentage: {coverage:.2f}%",
        f"- unresolved percentage: {unresolved_pct:.2f}%",
        f"- phase4 online source checks enabled: {online_enabled}",
        "",
        "## Unresolved By Brand",
        "",
    ]
    write_count_table(lines, unresolved_by_brand, "Brand")
    lines.extend(["", "## Unresolved By Series", ""])
    write_count_table(lines, unresolved_by_series, "Series", limit=120)
    lines.extend(["", "## Top 50 Likely User-Searched Unresolved Models", ""])
    lines.append("| Rank | Brand | Series | Display name | Release year | Source type | Reason | Candidate source |")
    lines.append("| ---: | --- | --- | --- | ---: | --- | --- | --- |")
    for index, row in enumerate(top_unresolved, start=1):
        lines.append(
            "| "
            + " | ".join(
                markdown_cell(value)
                for value in [
                    index,
                    row["brand"],
                    row["series"],
                    row["display_name"],
                    row["release_year"] if row["release_year"] is not None else "",
                    row.get("candidate_source_type", "unknown"),
                    row.get("reason", ""),
                    row.get("candidate_source_url", ""),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Source Type For Current Unresolved", ""])
    write_count_table(lines, unresolved_source_types, "Source type")
    lines.extend(["", "## Most Common Reasons", ""])
    write_count_table(lines, unresolved_reasons, "Reason", limit=40)
    (REPORT_DIR / "battery_verification_gap_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    priority_brand_lines = [
        "# Unresolved Priority By Brand",
        "",
        f"Generated: {ctx.today}",
        "",
        "| Priority | Brand | Unresolved | Recommended next action |",
        "| ---: | --- | ---: | --- |",
    ]
    ordered_brands = sorted(unresolved_by_brand.items(), key=lambda item: (-priority_brand_score(item[0]), -item[1], item[0]))
    for index, (brand, count) in enumerate(ordered_brands, start=1):
        action = "Find official manuals/spec pages first; use trusted database only if manual is unavailable."
        priority_brand_lines.append(f"| {index} | {markdown_cell(brand)} | {count} | {action} |")
    (REPORT_DIR / "unresolved_priority_by_brand.md").write_text("\n".join(priority_brand_lines) + "\n", encoding="utf-8")

    priority_series_lines = [
        "# Unresolved Priority By Series",
        "",
        f"Generated: {ctx.today}",
        "",
        "| Priority | Series bucket | Unresolved | Recommended next action |",
        "| ---: | --- | ---: | --- |",
    ]
    ordered_series = sorted(unresolved_by_series.items(), key=lambda item: (-item[1], item[0]))
    priority_labels = {label for label, _ in PRIORITY_SERIES_KEYWORDS}
    ordered_series = sorted(ordered_series, key=lambda item: (0 if item[0] in priority_labels else 1, -item[1], item[0]))
    for index, (series, count) in enumerate(ordered_series, start=1):
        action = "Batch official/manual lookup by exact model names in this bucket."
        priority_series_lines.append(f"| {index} | {markdown_cell(series)} | {count} | {action} |")
    (REPORT_DIR / "unresolved_priority_by_series.md").write_text("\n".join(priority_series_lines) + "\n", encoding="utf-8")

    verified_ids_after = {row["camera_id"] for row in ctx.cameras}
    promoted_ids = verified_ids_after - before_verified_ids
    verified_by_brand = Counter(row["brand"] for row in ctx.cameras if row["camera_id"] in promoted_ids)

    summary_lines = [
        "# Phase 4 Verification Summary",
        "",
        f"Generated: {ctx.today}",
        "",
        "| Metric | Before | After | Delta |",
        "| --- | ---: | ---: | ---: |",
    ]
    for key in ["verified_cameras", "batteries", "compatibility_rows", "candidates", "unresolved"]:
        summary_lines.append(f"| {key} | {before.get(key, 0)} | {after[key]} | {after[key] - before.get(key, 0)} |")
    summary_lines.extend(["", "## Verifier Mode", ""])
    summary_lines.append(f"- Online verifier modules run: {online_enabled}")
    summary_lines.append("- Default mode only promotes rows with explicit source data from manual_missing_queries.json.")
    summary_lines.extend(["", "## Current Run Online Verifiers", ""])
    if verifier_results:
        summary_lines.append("| Verifier | Processed | Verified | Still unresolved | Warnings |")
        summary_lines.append("| --- | ---: | ---: | ---: | ---: |")
        for result in verifier_results:
            summary_lines.append(f"| {result['verifier']} | {result['processed']} | {result['verified']} | {result['still_unresolved']} | {len(result.get('warnings', []))} |")
    else:
        summary_lines.append("- Not run. Use `py -3 scripts\\verify_unresolved_batteries_phase4.py --online` for bounded network checks.")
    summary_lines.extend(["", "## Verified Added By Brand", ""])
    if verified_by_brand:
        write_count_table(summary_lines, verified_by_brand, "Brand")
    else:
        summary_lines.append("- None in this run.")
    summary_lines.extend(["", "## Top 30 Remaining Unresolved", ""])
    summary_lines.append("| Rank | Brand | Series | Display name | Reason |")
    summary_lines.append("| ---: | --- | --- | --- | --- |")
    for index, row in enumerate(top_unresolved[:30], start=1):
        summary_lines.append(f"| {index} | {markdown_cell(row['brand'])} | {markdown_cell(row['series'])} | {markdown_cell(row['display_name'])} | {markdown_cell(row.get('reason', ''))} |")
    (REPORT_DIR / "phase4_verification_summary.md").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Phase 4 unresolved battery verification and coverage reports.")
    parser.add_argument("--online", action="store_true", help="Run existing network verifiers after manual source processing.")
    args = parser.parse_args(argv)

    before_ctx = ImportContext.load(ROOT)
    before = counts(before_ctx)
    before_verified_ids = {row["camera_id"] for row in before_ctx.cameras}

    import_manual_missing_queries()
    ctx = ImportContext.load(ROOT)
    verifier_results: list[dict] = []

    if args.online:
        for module_name in ONLINE_VERIFIER_MODULES:
            verifier_results.append(run_online_verifier(ctx, module_name))

    dedupe_compatibility_for_app_output(ctx)
    ctx.sort_all()

    try:
        validate(ctx.cameras, ctx.batteries, ctx.compatibility, ctx.candidates, ctx.sources, ctx.unresolved)
    except Exception as exc:
        print("Phase 4 verification failed validation; data/*.json was not modified by this runner.")
        print(str(exc))
        return 1

    ctx.write_all()
    write_gap_reports(ctx, before, before_verified_ids, verifier_results, args.online)

    after = counts(ctx)
    print(json.dumps({"before": before, "after": after, "online": args.online}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
