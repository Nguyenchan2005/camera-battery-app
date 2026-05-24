from __future__ import annotations

import copy
import json
import re
import ssl
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import quote

from importers.common import (
    ImportContext,
    add_compatibility_source_backed,
    battery_record,
    clean_source_text,
    dedupe_compatibility_for_app_output,
    detect_battery_system,
    exact_model_match,
    fetch_text,
    parse_power_mappings,
    register_source,
    safe_extract_power_source_text,
    validate_url,
)


ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "reports"
PHASE3_BATCH_ID = "phase3_verified_from_unresolved"

CATALOG_URLS = {
    "https://camera-wiki.org/wiki/Sony",
    "https://camera-wiki.org/wiki/Nikon_Coolpix",
    "https://camera-wiki.org/wiki/Fujifilm_digital_cameras",
    "https://camera-wiki.org/wiki/Panasonic",
    "https://camera-wiki.org/wiki/Olympus",
    "https://camera-wiki.org/wiki/Olympus_Stylus_%C2%B5_digital_cameras",
    "https://camera-wiki.org/wiki/Casio",
    "https://camera-wiki.org/wiki/Kodak",
    "https://camera-wiki.org/wiki/Samsung",
    "https://camera-wiki.org/wiki/Pentax",
    "https://camera-wiki.org/wiki/Ricoh",
    "https://camera-wiki.org/wiki/Hewlett-Packard",
    "https://camera-wiki.org/wiki/Leica",
    "https://camera-wiki.org/wiki/Sigma",
    "https://camera-wiki.org/wiki/Minolta",
    "https://camera-wiki.org/wiki/Konica_Minolta",
}


def result_template(name: str) -> dict:
    return {
        "verifier": name,
        "processed": 0,
        "verified": 0,
        "still_unresolved": 0,
        "warnings": [],
        "checked_urls": [],
        "verified_camera_ids": [],
    }


def unresolved_for_brands(ctx: ImportContext, brands: set[str]) -> list[dict]:
    camera_ids = {camera["camera_id"] for camera in ctx.cameras}
    return [
        row
        for row in ctx.unresolved
        if row["brand"] in brands and row["camera_id"] not in camera_ids
    ]


def candidate_by_id(ctx: ImportContext, camera_id: str) -> dict | None:
    return next((row for row in ctx.candidates if row["camera_id"] == camera_id), None)


def candidate_names(candidate: dict) -> list[str]:
    names = [candidate["display_name"], candidate["model"], *candidate["aliases"]]
    for regional_names in candidate["regional_names"].values():
        names.extend(regional_names)
    core = re.sub(
        r"^(?:FinePix|COOLPIX|Cyber-shot|Lumix|PowerShot|EasyShare|Exilim|Optio|DiMAGE)\s+",
        "",
        candidate["model"],
        flags=re.I,
    )
    core = re.sub(r"^(?:DSC-|DMC-|DC-)", "", core, flags=re.I)
    if re.search(r"[A-Za-z]", core) and re.search(r"\d", core) and len(re.sub(r"[^A-Za-z0-9]", "", core)) >= 4:
        names.append(core)
    return [name for name in names if name]


def reader_url(source_url: str) -> str:
    return "https://r.jina.ai/http://" + source_url


def fetch_verification_text(source_url: str, use_reader: bool = False, timeout: int = 12) -> str:
    return fetch_text(reader_url(source_url) if use_reader else source_url, timeout=timeout)


def normalize_power_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def extract_power_source_text(page_text: str) -> str:
    table_text = safe_extract_power_source_text(page_text)
    if table_text:
        return normalize_power_text(table_text)

    plain = clean_source_text(page_text)
    plain = re.sub(r"\s+", " ", plain)
    snippets = []
    patterns = [
        r"(?:Power comes from|powered by|power is supplied by|uses|takes|requires).{0,220}?(?:batter(?:y|ies)|AA|AAA|NP-[A-Z0-9]+|EN-EL\d+[a-z]?|KLIC-\d+|D-LI\d+|DMW-[A-Z0-9]+|LI-\d+[A-Z]?|CR-?V3|2CR5|CR123A).{0,220}",
        r"(?:Battery(?: System| Type)?|Supplied Battery|Rechargeable battery pack|Batteries).{0,260}",
        r"(?:電源|使用電池|付属品).{0,260}",
        r"(?:Li-ionリチャージャブルバッテリー|リチャージャブルバッテリー).{0,160}",
        r"(?:アルカリ単3形電池|単3形電池|単4形電池).{0,180}",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, plain, flags=re.I):
            snippets.append(match.group(0))
    seen = set()
    useful = []
    for snippet in snippets:
        key = snippet.casefold()
        if key in seen:
            continue
        seen.add(key)
        if parse_power_mappings(snippet):
            useful.append(snippet)
    return normalize_power_text(" ".join(useful[:4]))


def source_mentions_model(candidate: dict, text: str, source_url: str) -> bool:
    aliases = candidate_names(candidate)
    if exact_model_match(candidate["model"], text, aliases):
        return True
    url_key = re.sub(r"[^a-z0-9]+", "", source_url.casefold())
    for name in aliases:
        key = re.sub(r"[^a-z0-9]+", "", name.casefold())
        if key and len(key) >= 6 and key in url_key:
            return True
    return False


def promote_candidate(
    ctx: ImportContext,
    candidate: dict,
    mappings: list[dict],
    power_text: str,
    source_name: str,
    source_url: str,
    source_type: str,
    confidence: str,
    publisher: str,
) -> None:
    for mapping in mappings:
        battery = battery_record(
            mapping.get("brand", candidate["brand"]),
            mapping["model"],
            "Added by Phase 3 unresolved verifier; electrical details left blank unless source-backed.",
        )
        note = power_text
        if mapping["status"] in {"uses_aa", "uses_aaa"} and mapping.get("quantity_required") is None:
            note += " Source confirms AA/AAA battery type but does not state quantity."
        add_compatibility_source_backed(
            ctx,
            candidate,
            battery,
            mapping["status"],
            mapping.get("quantity_required"),
            note,
            source_name,
            source_url,
            source_type,
            confidence,
            publisher,
        )

    system = detect_battery_system(power_text, [mapping["model"] for mapping in mappings])
    for row in ctx.candidates:
        if row["camera_id"] == candidate["camera_id"]:
            row["candidate_status"] = "verified_battery"
            row["candidate_batch"] = PHASE3_BATCH_ID
            row["candidate_source_name"] = source_name
            row["candidate_source_url"] = source_url
            row["candidate_source_type"] = source_type
            row["battery_system"] = system
            break
    for row in ctx.cameras:
        if row["camera_id"] == candidate["camera_id"]:
            row["battery_system"] = system
            break


def verify_from_source(
    ctx: ImportContext,
    unresolved: dict,
    source_url: str,
    source_name: str,
    source_type: str,
    confidence: str,
    publisher: str,
    use_reader: bool = False,
    page_text: str | None = None,
) -> tuple[bool, str]:
    candidate = candidate_by_id(ctx, unresolved["camera_id"])
    if not candidate or candidate["camera_id"] in {camera["camera_id"] for camera in ctx.cameras}:
        return False, "Candidate missing or already verified."
    if not validate_url(source_url):
        return False, "Invalid source URL."
    if source_url in unresolved.get("checked_source_urls", []):
        return False, "Already checked source."

    try:
        text = page_text if page_text is not None else fetch_verification_text(source_url, use_reader=use_reader)
    except Exception as exc:
        update_unresolved_checked(ctx, unresolved["camera_id"], [source_url], f"Battery source check failed: {type(exc).__name__}: {exc}")
        return False, f"{type(exc).__name__}: {exc}"

    plain = clean_source_text(text)
    if not source_mentions_model(candidate, plain, source_url):
        update_unresolved_checked(ctx, unresolved["camera_id"], [source_url], "Checked source but exact model match was not confirmed.")
        return False, "Exact model match failed."

    power_text = extract_power_source_text(text)
    mappings = parse_power_mappings(power_text, candidate["brand"]) if power_text else []
    if not mappings:
        update_unresolved_checked(ctx, unresolved["camera_id"], [source_url], "Checked source but no explicit battery/power mapping was extracted.")
        return False, "No battery mapping extracted."

    register_source(ctx, source_name, source_url, source_type, publisher, "Phase 3 verifier source.")
    promote_candidate(ctx, copy.deepcopy(candidate), mappings, power_text, source_name, source_url, source_type, confidence, publisher)
    return True, "verified"


def update_unresolved_checked(ctx: ImportContext, camera_id: str, urls: list[str], reason: str) -> None:
    for row in ctx.unresolved:
        if row["camera_id"] != camera_id:
            continue
        existing = list(row.get("checked_source_urls", []))
        for url in urls:
            if validate_url(url) and url not in existing:
                existing.append(url)
        row["checked_source_urls"] = existing
        row["reason"] = reason
        row["last_checked"] = ctx.today
        break


def sony_support_url(model: str) -> str | None:
    code = model.lower().replace(" ", "")
    if code.startswith("dsc-wx"):
        series = "compact-cameras-dscwx-series"
    elif code.startswith("dsc-w"):
        series = "compact-cameras-dscw-series"
    elif code.startswith("dsc-hx"):
        series = "compact-cameras-dschx-series"
    elif code.startswith("dsc-h"):
        series = "compact-cameras-dsch-series"
    elif code.startswith("dsc-tx"):
        series = "compact-cameras-dsctx-series"
    elif code.startswith("dsc-t"):
        series = "compact-cameras-dsct-series"
    elif code.startswith("dsc-rx"):
        series = "compact-cameras-dscrx-series"
    elif code.startswith("zv-"):
        series = "vlog-cameras-zv-series"
    else:
        return None
    return f"https://www.sony.co.id/en/electronics/support/{series}/{quote(code)}/specifications"


def risky_short_sony_model(model: str) -> bool:
    core = re.sub(r"^DSC-", "", model, flags=re.I)
    return bool(re.fullmatch(r"[A-Z]{1,2}\d{1,2}[A-Z]?", core, flags=re.I))


def nikon_japan_spec_url(model: str) -> str | None:
    code = re.sub(r"^COOLPIX\s+", "", model, flags=re.I).lower()
    code = re.sub(r"[^a-z0-9]+", "", code)
    if not code or code in {"100", "300", "600", "700", "800", "900", "950", "990", "995"}:
        return None
    return f"https://nij.nikon.com/products/lineup/compact/{code}/spec.html"


def fujifilm_manual_urls(model: str) -> list[str]:
    token = re.sub(r"^(FinePix|FUJIFILM|Fujifilm)\s+", "", model, flags=re.I)
    token = token.replace("Real 3D", "real3d").replace("REAL 3D", "real3d")
    token = re.sub(r"[^A-Za-z0-9]+", "", token).lower()
    if not token:
        return []
    folder = token[0]
    return [
        f"https://dl.fujifilm-x.com/support/manual/{folder}/fujifilm_{token}_manual_01.pdf",
        f"https://dl.fujifilm-x.com/support/manual/{folder}/finepix_{token}_manual_01.pdf",
        f"https://dl.fujifilm-x.com/support/manual/{folder}/{token}_manual_01.pdf",
    ]


def camera_wiki_individual_source(unresolved: dict) -> str | None:
    url = unresolved.get("candidate_source_url", "")
    if not url.startswith("https://camera-wiki.org/wiki/"):
        return None
    if url in CATALOG_URLS:
        return None
    return url


def verify_from_camera_wiki_page(ctx: ImportContext, unresolved: dict) -> tuple[bool, str]:
    url = camera_wiki_individual_source(unresolved)
    if not url:
        return False, "No individual Camera-wiki page."
    return verify_from_source(
        ctx,
        unresolved,
        url,
        f"Camera-wiki {unresolved['display_name']}",
        "trusted_database",
        "medium",
        "Camera-wiki",
    )


def merge_results(results: list[dict]) -> dict:
    merged = {
        "processed": sum(result.get("processed", 0) for result in results),
        "verified": sum(result.get("verified", 0) for result in results),
        "still_unresolved": sum(result.get("still_unresolved", 0) for result in results),
        "warnings": [warning for result in results for warning in result.get("warnings", [])],
        "checked_urls": [url for result in results for url in result.get("checked_urls", [])],
        "verified_camera_ids": [camera_id for result in results for camera_id in result.get("verified_camera_ids", [])],
    }
    return merged


def count_by_brand(rows: list[dict]) -> Counter:
    return Counter(row["brand"] for row in rows)


def run_http_status_checks(urls: list[str], extra_urls: list[str] | None = None, limit: int = 450) -> list[dict]:
    REPORT_DIR.mkdir(exist_ok=True)
    cache_path = REPORT_DIR / "http_status_report.json"
    if cache_path.exists():
        try:
            cached_rows = json.loads(cache_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            cached_rows = []
    else:
        cached_rows = []
    cache = {row["url"]: row for row in cached_rows if isinstance(row, dict) and row.get("url")}
    checked = []
    seen = set()
    for url in [*(extra_urls or []), *urls]:
        if not validate_url(url) or url in seen:
            continue
        seen.add(url)
        if len(checked) >= limit:
            break
        if url in cache:
            checked.append(cache[url])
        else:
            checked.append(check_url_status(url))
    merged_cache = {row["url"]: row for row in cached_rows if isinstance(row, dict) and row.get("url")}
    for row in checked:
        merged_cache[row["url"]] = row
    cache_path.write_text(json.dumps(list(merged_cache.values()), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return checked


def check_url_status(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 camera-battery-db/1.0"}, method="HEAD")
    context = ssl.create_default_context()
    try:
        with urllib.request.urlopen(request, timeout=6, context=context) as response:
            return {"url": url, "status": response.status, "ok": 200 <= response.status < 400, "error": ""}
    except urllib.error.HTTPError as exc:
        return {"url": url, "status": exc.code, "ok": False, "error": exc.reason}
    except Exception as exc:
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 camera-battery-db/1.0"})
            with urllib.request.urlopen(request, timeout=6, context=context) as response:
                return {"url": url, "status": response.status, "ok": 200 <= response.status < 400, "error": ""}
        except urllib.error.HTTPError as http_exc:
            return {"url": url, "status": http_exc.code, "ok": False, "error": http_exc.reason}
        except Exception as get_exc:
            return {"url": url, "status": None, "ok": False, "error": f"{type(get_exc).__name__}: {get_exc}"}


def write_phase3_reports(
    ctx: ImportContext,
    before: dict,
    verifier_results: list[dict],
    http_status_rows: list[dict],
) -> None:
    REPORT_DIR.mkdir(exist_ok=True)
    after = {
        "cameras": len(ctx.cameras),
        "batteries": len(ctx.batteries),
        "compatibility": len(ctx.compatibility),
        "candidates": len(ctx.candidates),
        "unresolved": len(ctx.unresolved),
    }
    current_run_verified_ids = set(merge_results(verifier_results)["verified_camera_ids"])
    verified_ids = {
        row["camera_id"]
        for row in ctx.candidates
        if row.get("candidate_batch") == PHASE3_BATCH_ID
        and row.get("candidate_status") == "verified_battery"
    }
    verified_by_brand = Counter()
    for camera in ctx.cameras:
        if camera["camera_id"] in verified_ids:
            verified_by_brand[camera["brand"]] += 1
    unresolved_by_brand = count_by_brand(ctx.unresolved)
    source_type_counts = Counter(row["source_type"] for row in ctx.compatibility if row["camera_id"] in verified_ids)

    summary = {
        "generated": ctx.today,
        "before": before,
        "after": after,
        "verifier_results": verifier_results,
        "current_run_verified_camera_count": len(current_run_verified_ids),
        "phase3_cumulative_verified_camera_count": len(verified_ids),
        "verified_from_unresolved_by_brand": dict(sorted(verified_by_brand.items())),
        "still_unresolved_by_brand": dict(sorted(unresolved_by_brand.items())),
        "source_type_counts_for_phase3": dict(sorted(source_type_counts.items())),
        "http_status": http_status_rows,
    }
    (REPORT_DIR / "phase3_verification_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Phase 3 Verification Summary",
        "",
        f"Generated: {ctx.today}",
        "",
        "| Metric | Before | After | Delta |",
        "| --- | ---: | ---: | ---: |",
    ]
    for key in ["cameras", "batteries", "compatibility", "candidates", "unresolved"]:
        lines.append(f"| {key} | {before.get(key, 0)} | {after[key]} | {after[key] - before.get(key, 0)} |")
    lines.extend(["", "## Verifier Results", ""])
    lines.append("| Verifier | Processed | Verified | Still unresolved | Warnings |")
    lines.append("| --- | ---: | ---: | ---: | ---: |")
    for result in verifier_results:
        lines.append(f"| {result['verifier']} | {result['processed']} | {result['verified']} | {result['still_unresolved']} | {len(result.get('warnings', []))} |")
    lines.extend(["", "## Cumulative Phase 3 Promotions", ""])
    lines.append(f"- Verified cameras promoted from unresolved: {len(verified_ids)}")
    lines.append(f"- Compatibility rows for promoted cameras: {sum(1 for row in ctx.compatibility if row['camera_id'] in verified_ids)}")
    lines.extend(["", "## Source Types Used For Phase 3 Rows", ""])
    for source_type, count in sorted(source_type_counts.items()):
        lines.append(f"- {source_type}: {count}")
    lines.extend(["", "## HTTP Status Warnings", ""])
    warnings = [row for row in http_status_rows if row["status"] == 404 or row["error"]]
    if warnings:
        for row in warnings[:80]:
            lines.append(f"- {row['url']}: status={row['status']} error={row['error']}")
    else:
        lines.append("- None")
    (REPORT_DIR / "phase3_verification_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    write_brand_count_report(REPORT_DIR / "verified_from_unresolved_by_brand.md", "Verified From Unresolved By Brand", verified_by_brand)
    write_brand_count_report(REPORT_DIR / "still_unresolved_by_brand.md", "Still Unresolved By Brand", unresolved_by_brand)
    write_battery_source_quality_report(ctx, verified_ids)
    write_http_status_report(http_status_rows)


def write_brand_count_report(path: Path, title: str, counts: Counter) -> None:
    lines = ["# " + title, "", "| Brand | Count |", "| --- | ---: |"]
    for brand, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"| {brand} | {count} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_battery_source_quality_report(ctx: ImportContext, phase3_camera_ids: set[str]) -> None:
    camera_by_id = {camera["camera_id"]: camera for camera in ctx.cameras}
    rows = [row for row in ctx.compatibility if row["camera_id"] in phase3_camera_ids]
    counts = Counter((row["source_type"], row["confidence"]) for row in rows)
    lines = [
        "# Battery Source Quality Report",
        "",
        "| Source type | Confidence | Rows |",
        "| --- | --- | ---: |",
    ]
    for (source_type, confidence), count in sorted(counts.items()):
        lines.append(f"| {source_type} | {confidence} | {count} |")
    lines.extend(["", "## Weak Sources", ""])
    weak = [row for row in rows if row["confidence"] == "low" or row["source_type"] in {"retailer", "third_party_chart"}]
    if not weak:
        lines.append("- None")
    else:
        for row in weak[:100]:
            camera = camera_by_id[row["camera_id"]]
            lines.append(f"- {camera['display_name']}: {row['source_type']} {row['confidence']} {row['source_url']}")
    (REPORT_DIR / "battery_source_quality_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_http_status_report(rows: list[dict]) -> None:
    lines = [
        "# HTTP Status Report",
        "",
        "| URL | Status | OK | Error |",
        "| --- | ---: | --- | --- |",
    ]
    for row in rows:
        lines.append(f"| {row['url']} | {row['status'] if row['status'] is not None else ''} | {row['ok']} | {str(row['error']).replace('|', '/')} |")
    (REPORT_DIR / "http_status_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
