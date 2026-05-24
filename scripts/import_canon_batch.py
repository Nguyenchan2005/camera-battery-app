from __future__ import annotations

import html
import json
import re
import time
import urllib.request
from collections import defaultdict
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
REPORT_DIR = ROOT / "reports"
INDEX_CACHE = ROOT / "canon_camera_index.html"
INDEX_URL = "https://global.canon/en/c-museum/camera.html?s=dcc"
TODAY = date.today().isoformat()
BATCH_ID = "canon_compact_1998_2026_batch_1"

SERIES_CODES = {
    "psa": "PowerShot A",
    "pselph": "PowerShot ELPH / PowerShot SD / Digital IXUS / IXY Digital",
    "pss": "PowerShot S",
    "psg": "PowerShot G",
    "pssx": "PowerShot SX",
    "psd": "PowerShot D",
    "psn": "PowerShot N",
}

BATTERY_FAQ_SOURCES = [
    (
        "canon_nb_4l_faq",
        "Canon Japan NB-4L product specification FAQ",
        "https://faq.canon.jp/app/answers/detail/a_id/54063/~/%E3%80%90%E3%82%B3%E3%83%B3%E3%83%91%E3%82%AF%E3%83%88%E3%83%87%E3%82%B8%E3%82%BF%E3%83%AB%E3%82%AB%E3%83%A1%E3%83%A9%E3%80%91%E3%83%90%E3%83%83%E3%83%86%E3%83%AA%E3%83%BC%E3%83%91%E3%83%83%E3%82%AF-nb-4l-%E8%A3%BD%E5%93%81%E4%BB%95%E6%A7%98",
        ["NB-4L"],
    ),
    (
        "canon_nb_5l_faq",
        "Canon Japan NB-5L product specification FAQ",
        "https://faq.canon.jp/app/answers/detail/a_id/54125/~/%E3%80%90%E3%82%B3%E3%83%B3%E3%83%91%E3%82%AF%E3%83%88%E3%83%87%E3%82%B8%E3%82%BF%E3%83%AB%E3%82%AB%E3%83%A1%E3%83%A9%E3%80%91%E3%83%90%E3%83%83%E3%83%86%E3%83%AA%E3%83%BC%E3%83%91%E3%83%83%E3%82%AF-nb-5l-%E8%A3%BD%E5%93%81%E4%BB%95%E6%A7%98",
        ["NB-5L"],
    ),
    (
        "canon_nb_6l_faq",
        "Canon Japan NB-6L product specification FAQ",
        "https://faq.canon.jp/app/answers/detail/a_id/54124/~/%E3%80%90%E3%82%B3%E3%83%B3%E3%83%91%E3%82%AF%E3%83%88%E3%83%87%E3%82%B8%E3%82%BF%E3%83%AB%E3%82%AB%E3%83%A1%E3%83%A9%E3%80%91%E3%83%90%E3%83%83%E3%83%86%E3%83%AA%E3%83%BC%E3%83%91%E3%83%83%E3%82%AF-nb-6l-%E8%A3%BD%E5%93%81%E4%BB%95%E6%A7%98",
        ["NB-6L"],
    ),
    (
        "canon_nb_6lh_faq",
        "Canon Japan NB-6LH product specification FAQ",
        "https://faq.canon.jp/app/answers/detail/a_id/75432/~/%E3%80%90%E3%82%B3%E3%83%B3%E3%83%91%E3%82%AF%E3%83%88%E3%83%87%E3%82%B8%E3%82%BF%E3%83%AB%E3%82%AB%E3%83%A1%E3%83%A9%E3%80%91%E3%83%90%E3%83%83%E3%83%86%E3%83%AA%E3%83%BC%E3%83%91%E3%83%83%E3%82%AF-nb-6lh-%E8%A3%BD%E5%93%81%E4%BB%95%E6%A7%98",
        ["NB-6LH"],
    ),
    (
        "canon_nb_10l_faq",
        "Canon Japan NB-10L product specification FAQ",
        "https://faq.canon.jp/app/answers/detail/a_id/67499/~/%E3%80%90%E3%82%B3%E3%83%B3%E3%83%91%E3%82%AF%E3%83%88%E3%83%87%E3%82%B8%E3%82%BF%E3%83%AB%E3%82%AB%E3%83%A1%E3%83%A9%E3%80%91%E3%83%90%E3%83%83%E3%83%86%E3%83%AA%E3%83%BC%E3%83%91%E3%83%83%E3%82%AF-nb-10l-%E8%A3%BD%E5%93%81%E4%BB%95%E6%A7%98",
        ["NB-10L"],
    ),
    (
        "canon_nb_11l_faq",
        "Canon Japan NB-11L product specification FAQ",
        "https://faq.canon.jp/app/answers/detail/a_id/67500/~/%E3%80%90%E3%82%B3%E3%83%B3%E3%83%91%E3%82%AF%E3%83%88%E3%83%87%E3%82%B8%E3%82%BF%E3%83%AB%E3%82%AB%E3%83%A1%E3%83%A9%E3%80%91%E3%83%90%E3%83%83%E3%83%86%E3%83%AA%E3%83%BC%E3%83%91%E3%83%83%E3%82%AF-nb-11l-%E8%A3%BD%E5%93%81%E4%BB%95%E6%A7%98",
        ["NB-11L"],
    ),
    (
        "canon_nb_11lh_faq",
        "Canon Japan NB-11LH product specification FAQ",
        "https://faq.canon.jp/app/answers/detail/a_id/77952/~/%E3%80%90%E3%82%B3%E3%83%B3%E3%83%91%E3%82%AF%E3%83%88%E3%83%87%E3%82%B8%E3%82%BF%E3%83%AB%E3%82%AB%E3%83%A1%E3%83%A9%E3%80%91%E3%83%90%E3%83%83%E3%83%86%E3%83%AA%E3%83%BC%E3%83%91%E3%83%83%E3%82%AF-nb-11lh-%E8%A3%BD%E5%93%81%E4%BB%95%E6%A7%98",
        ["NB-11LH"],
    ),
    (
        "canon_nb_12l_faq",
        "Canon Japan NB-12L product specification FAQ",
        "https://faq.canon.jp/app/answers/detail/a_id/78193/~/%E3%80%90%E3%82%B3%E3%83%B3%E3%83%91%E3%82%AF%E3%83%88%E3%83%87%E3%82%B8%E3%82%BF%E3%83%AB%E3%82%AB%E3%83%A1%E3%83%A9%E3%80%91%E3%83%90%E3%83%83%E3%83%86%E3%83%AA%E3%83%BC%E3%83%91%E3%83%83%E3%82%AF-nb-12l-%E8%A3%BD%E5%93%81%E4%BB%95%E6%A7%98",
        ["NB-12L"],
    ),
    (
        "canon_nb_13l_faq",
        "Canon Japan NB-13L product specification FAQ",
        "https://faq.canon.jp/app/answers/detail/a_id/81687/~/%E3%80%90%E3%82%B3%E3%83%B3%E3%83%91%E3%82%AF%E3%83%88%E3%83%87%E3%82%B8%E3%82%BF%E3%83%AB%E3%82%AB%E3%83%A1%E3%83%A9%E3%80%91%E3%83%90%E3%83%83%E3%83%86%E3%83%AA%E3%83%BC%E3%83%91%E3%83%83%E3%82%AF-nb-13l-%E8%A3%BD%E5%93%81%E4%BB%95%E6%A7%98",
        ["NB-13L"],
    ),
    (
        "canon_nb_15l_faq",
        "Canon Japan NB-15L product specification FAQ",
        "https://faq.canon.jp/app/answers/detail/a_id/105545/~/%E3%80%90%E3%82%B3%E3%83%B3%E3%83%91%E3%82%AF%E3%83%88%E3%83%87%E3%82%B8%E3%82%BF%E3%83%AB%E3%82%AB%E3%83%A1%E3%83%A9%E3%80%91%E3%83%90%E3%83%83%E3%83%86%E3%83%AA%E3%83%BC%E3%83%91%E3%83%83%E3%82%AF-nb-15l-%E8%A3%BD%E5%93%81%E4%BB%95%E6%A7%98",
        ["NB-15L"],
    ),
]


def load_json(name: str, default: list[dict] | None = None) -> list[dict]:
    path = DATA_DIR / name
    if not path.exists():
        return [] if default is None else default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: list[dict]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fetch_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "camera-battery-db/1.0"})
    with urllib.request.urlopen(request, timeout=40) as response:
        content_type = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(content_type, errors="replace")


def strip_tags(value: str) -> str:
    value = re.sub(r"<br\s*/?>", " ", value, flags=re.I)
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def normalize_alias(value: str) -> str:
    value = html.unescape(value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def slugify(value: str) -> str:
    value = value.lower()
    value = value.replace("&", " and ")
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value


def camera_id_for(display_name: str) -> str:
    return "canon_" + slugify(display_name)


def battery_id_for(model: str) -> str:
    if model == "AA":
        return "generic_aa"
    if model == "AAA":
        return "generic_aaa"
    if model == "2CR5":
        return "generic_2cr5"
    return "canon_" + slugify(model)


def category_for(series_code: str, name: str) -> str:
    if series_code == "psd":
        return "waterproof_compact"
    if series_code in {"psg", "pss"}:
        return "premium_compact"
    if series_code == "pssx":
        bridge_markers = [
            "SX1 ",
            "SX10 ",
            "SX20 ",
            "SX30 ",
            "SX40 ",
            "SX50 ",
            "SX60 ",
            "SX70 ",
            "SX400",
            "SX410",
            "SX420",
            "SX430",
            "SX500",
            "SX510",
            "SX520",
            "SX530",
            "SX540",
        ]
        if any(marker in name for marker in bridge_markers):
            return "bridge_superzoom"
        return "travel_zoom"
    return "point_and_shoot"


def parse_index(index_html: str) -> list[dict]:
    pattern = re.compile(
        r'<div class="product_box dcc ([^"]*)">.*?'
        r'<a href="([^"]+)" class="animsition-link"><p class="pro_name"><span class="en">([^<]+)</span></p></a>'
        r'<p class="pro_mak"><span class="en">\((\d{4})\)</span></p></div>',
        re.S,
    )
    rows = []
    for match in pattern.finditer(index_html):
        classes = match.group(1).strip().split()
        series_code = next((code for code in SERIES_CODES if code in classes), None)
        if not series_code:
            continue
        name = normalize_alias(match.group(3))
        year = int(match.group(4))
        if not 1998 <= year <= 2026:
            continue
        rows.append(
            {
                "series_code": series_code,
                "index_name": name,
                "release_year": year,
                "product_url": "https://global.canon" + match.group(2),
            }
        )
    return rows


def parse_regional_names(product_html: str, fallback_name: str) -> dict[str, list[str]]:
    icon_to_region = {"07": "japan", "08": "americas", "09": "europe_asia_oceania"}
    regional: dict[str, list[str]] = {"japan": [], "americas": [], "europe_asia_oceania": []}
    pattern = re.compile(r'<p class="title_i">(.*?)<img src="/ja/c-museum/common/img/icon_(\d+)\.png"', re.S)
    for match in pattern.finditer(product_html):
        name = strip_tags(match.group(1))
        region = icon_to_region.get(match.group(2))
        if region and name and name not in regional[region]:
            regional[region].append(name)
    if not any(regional.values()):
        regional["americas"].append(fallback_name)
    return {key: value for key, value in regional.items() if value}


def display_name_from_regions(index_name: str, regional: dict[str, list[str]]) -> str:
    for region in ("americas", "europe_asia_oceania", "japan"):
        for name in regional.get(region, []):
            if name.startswith("PowerShot"):
                return name
    return index_name


def extract_power_source(product_html: str) -> str | None:
    labels = ["Power Source", "Power Supply", "Power"]
    for label in labels:
        pattern = re.compile(
            rf"<td[^>]*>\s*{re.escape(label)}\s*:?\s*</td>\s*<td[^>]*>(.*?)</td>",
            re.S | re.I,
        )
        match = pattern.search(product_html)
        if match:
            return strip_tags(match.group(1))
        pattern_colspan = re.compile(
            rf"<td[^>]*>\s*{re.escape(label)}\s*:?\s*</td>\s*<td[^>]*colspan=\"2\"[^>]*>(.*?)</td>",
            re.S | re.I,
        )
        match = pattern_colspan.search(product_html)
        if match:
            return strip_tags(match.group(1))
    section_pattern = re.compile(
        r'<td[^>]*colspan="2"[^>]*>\s*(?:<strong>)?\s*\[?\s*(?:Power Source|Power Supply)\s*\]?\s*(?:</strong>)?\s*</td>\s*</tr>\s*'
        r'<tr>\s*<td[^>]*>\s*(?:Batteries|Battery)\s*</td>\s*<td[^>]*>(.*?)</td>',
        re.S | re.I,
    )
    match = section_pattern.search(product_html)
    if match:
        return strip_tags(match.group(1))
    text = strip_tags(product_html)
    match = re.search(r"(?<!AC )\b(Power Source|Power Supply)\b\s*:?\s+(.{1,220}?)(Operating|Dimensions|Weight|Shooting|Playback|$)", text)
    if match:
        return match.group(2).strip()
    return None


def parse_power_mapping(power_source: str) -> list[tuple[str, str, int | None]]:
    source = power_source.replace("‑", "-").replace("–", "-").replace("—", "-")
    source = re.sub(r"\s+", " ", source)
    mappings: list[tuple[str, str, int | None]] = []

    if re.search(r"\bAA\b|AA-size", source, re.I):
        quantity = parse_cell_quantity(source, "AA")
        mappings.append(("AA", "uses_aa", quantity))

    if re.search(r"\bAAA\b|AAA-size", source, re.I):
        quantity = parse_cell_quantity(source, "AAA")
        mappings.append(("AAA", "uses_aaa", quantity))

    if "2CR5" in source:
        mappings.append(("2CR5", "fully_compatible", 1))

    for model in sorted(set(re.findall(r"\b(?:NB|BP)-\d+[A-Z]*\b", source)), key=source.find):
        mappings.append((model, "fully_compatible", 1))

    deduped = []
    seen = set()
    for model, status, quantity in mappings:
        key = (model, status, quantity)
        if key not in seen:
            seen.add(key)
            deduped.append((model, status, quantity))
    return deduped


def parse_cell_quantity(source: str, cell_name: str) -> int | None:
    number_words = {
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
    }
    cell_pattern = rf"(?:{re.escape(cell_name)}(?:-size)?|size[-\s]?{re.escape(cell_name)})"
    digit_match = re.search(rf"\b([1-4])\s*(?:x|×)?\s*{cell_pattern}\b", source, re.I)
    if digit_match:
        return int(digit_match.group(1))
    suffix_digit_match = re.search(rf"\b{cell_pattern}\s*(?:x|×)\s*([1-4])\b", source, re.I)
    if suffix_digit_match:
        return int(suffix_digit_match.group(1))
    nearby_suffix_match = re.search(rf"\b{cell_pattern}\b.{{0,90}}?(?:x|×)\s*([1-4])\b", source, re.I)
    if nearby_suffix_match:
        return int(nearby_suffix_match.group(1))
    word_match = re.search(
        rf"\b({'|'.join(number_words)})\s+{cell_pattern}\b",
        source,
        re.I,
    )
    if word_match:
        return number_words[word_match.group(1).lower()]
    return None


def source_record(source_id: str, name: str, url: str, source_type: str, notes: str = "") -> dict:
    return {
        "source_id": source_id,
        "source_name": name,
        "source_url": url,
        "source_type": source_type,
        "publisher": "Canon",
        "last_verified": TODAY,
        "notes": notes,
    }


def ensure_battery(batteries: list[dict], model: str) -> str:
    battery_id = battery_id_for(model)
    if any(row["battery_id"] == battery_id for row in batteries):
        return battery_id

    if model == "2CR5":
        row = {
            "battery_id": battery_id,
            "brand": "Generic",
            "model": "2CR5",
            "aliases": ["2CR5 lithium"],
            "chemistry": "lithium",
            "voltage": None,
            "capacity_mah": None,
            "notes": "Special camera lithium battery format; voltage/capacity intentionally left blank until source-backed.",
        }
    else:
        row = {
            "battery_id": battery_id,
            "brand": "Canon",
            "model": model,
            "aliases": [],
            "chemistry": "lithium-ion",
            "voltage": None,
            "capacity_mah": None,
            "notes": "Added from Canon Batch 1 import; electrical details left blank unless separately source-backed.",
        }
    batteries.append(row)
    return battery_id


def compatibility_key(row: dict) -> tuple[str, str | None, str, str]:
    return (row["camera_id"], row["battery_id"], row["status"], row["source_url"])


def add_compatibility(compat: list[dict], row: dict) -> None:
    keys = {compatibility_key(item) for item in compat}
    if compatibility_key(row) not in keys:
        compat.append(row)


def plain_text(value: str) -> str:
    return strip_tags(value).replace("／", " / ")


def exact_model_name_in_text(model_name: str, text: str) -> bool:
    normalized_name = re.sub(r"\s+", " ", model_name.lower()).strip()
    if not normalized_name:
        return False
    escaped = re.escape(normalized_name).replace(r"\ ", r"\s+")
    return re.search(rf"(?<![a-z0-9]){escaped}(?!\s*[a-z0-9])", text) is not None


def compatibility_quantity(status: str, parsed_quantity: int | None) -> int | None:
    if status in {"uses_aa", "uses_aaa"}:
        return parsed_quantity
    return parsed_quantity or 1


def main() -> None:
    if INDEX_CACHE.exists():
        index_html = INDEX_CACHE.read_text(encoding="utf-8", errors="replace")
    else:
        index_html = fetch_text(INDEX_URL)
        INDEX_CACHE.write_text(index_html, encoding="utf-8")

    index_rows = parse_index(index_html)
    cameras = load_json("cameras.json")
    batteries = load_json("batteries.json")
    compat = load_json("compatibility.json")
    previous_candidates = load_json("camera_candidates.json")
    previous_batch_ids = {
        row["camera_id"]
        for row in previous_candidates
        if row.get("candidate_batch") == BATCH_ID
    }
    batch_source_urls = {row["product_url"] for row in index_rows}
    batch_source_urls.update(source_url for _, _, source_url, _ in BATTERY_FAQ_SOURCES)
    if previous_batch_ids:
        compat = [
            row
            for row in compat
            if not (row["camera_id"] in previous_batch_ids and row["source_url"] in batch_source_urls)
        ]
    existing_cameras = {row["camera_id"]: row for row in cameras}

    sources = {
        "canon_camera_museum_index": source_record(
            "canon_camera_museum_index",
            "Canon Camera Museum Digital Compact Cameras index",
            INDEX_URL,
            "official_manual",
            "Official source for Canon compact camera candidates and release years.",
        )
    }

    candidates: list[dict] = []
    camera_alias_lookup: dict[str, str] = {}
    camera_source_urls: dict[str, str] = {}
    direct_power_by_camera: dict[str, str] = {}

    for position, row in enumerate(index_rows, start=1):
        product_html = fetch_text(row["product_url"])
        regional = parse_regional_names(product_html, row["index_name"])
        display_name = display_name_from_regions(row["index_name"], regional)
        camera_id = camera_id_for(display_name)
        aliases = sorted(
            {
                name
                for names in regional.values()
                for name in names
                if name != display_name
            }
        )
        series = SERIES_CODES[row["series_code"]]
        power_source = extract_power_source(product_html)
        battery_system = "unknown"
        if power_source:
            if re.search(r"\bAA\b|AA-size", power_source, re.I):
                battery_system = "aa"
            elif re.search(r"\bAAA\b|AAA-size", power_source, re.I):
                battery_system = "aaa"
            elif "2CR5" in power_source:
                battery_system = "special"
            elif re.search(r"\b(?:NB|BP)-\d+[A-Z]*\b", power_source):
                battery_system = "proprietary_li_ion"

        candidate = {
            "camera_id": camera_id,
            "brand": "Canon",
            "series": series,
            "model": display_name.replace("Canon ", "").replace("PowerShot ", ""),
            "display_name": display_name,
            "aliases": aliases,
            "regional_names": regional,
            "release_year": row["release_year"],
            "category": category_for(row["series_code"], display_name),
            "lens_type": "fixed_lens",
            "battery_system": battery_system,
            "notes": "",
            "candidate_source_name": "Canon Camera Museum",
            "candidate_source_url": row["product_url"],
            "candidate_source_type": "official_manual",
            "candidate_batch": BATCH_ID,
        }
        candidates.append(candidate)
        camera_source_urls[camera_id] = row["product_url"]
        sources["canon_camera_museum_" + slugify(display_name)] = source_record(
            "canon_camera_museum_" + slugify(display_name),
            f"Canon Camera Museum {display_name}",
            row["product_url"],
            "official_manual",
            "Official product page used for candidate metadata and direct power-source extraction when present.",
        )

        for alias in [display_name] + aliases + [row["index_name"]]:
            camera_alias_lookup[alias.lower()] = camera_id
            camera_alias_lookup[alias.replace("Canon ", "").lower()] = camera_id

        if power_source:
            direct_power_by_camera[camera_id] = power_source
            for model, status, quantity in parse_power_mapping(power_source):
                battery_id = ensure_battery(batteries, model)
                add_compatibility(
                    compat,
                    {
                        "camera_id": camera_id,
                        "battery_id": battery_id,
                        "status": status,
                        "quantity_required": compatibility_quantity(status, quantity),
                        "note": f"Canon Camera Museum power source: {power_source}",
                        "source_name": f"Canon Camera Museum {display_name}",
                        "source_url": row["product_url"],
                        "source_type": "official_manual",
                        "confidence": "high",
                        "last_verified": TODAY,
                    },
                )

        if camera_id not in existing_cameras and any(item["camera_id"] == camera_id for item in compat):
            camera_record = {key: candidate[key] for key in [
                "camera_id",
                "brand",
                "series",
                "model",
                "display_name",
                "aliases",
                "regional_names",
                "release_year",
                "category",
                "lens_type",
                "battery_system",
                "notes",
            ]}
            cameras.append(camera_record)
            existing_cameras[camera_id] = camera_record

        if position % 25 == 0:
            time.sleep(0.5)

    for source_id, source_name, source_url, battery_models in BATTERY_FAQ_SOURCES:
        try:
            source_html = fetch_text(source_url)
        except Exception:
            continue
        text = re.sub(r"\s+", " ", plain_text(source_html).lower())
        sources[source_id] = source_record(source_id, source_name, source_url, "official_accessory_page")
        for candidate in candidates:
            camera_id = candidate["camera_id"]
            aliases = [candidate["display_name"], *candidate["aliases"]]
            aliases.extend(name for names in candidate["regional_names"].values() for name in names)
            matched = any(exact_model_name_in_text(alias, text) for alias in aliases if len(alias) >= 5)
            if not matched:
                continue
            for model in battery_models:
                battery_id = ensure_battery(batteries, model)
                status = "partially_compatible" if model == "NB-15L" else "fully_compatible"
                add_compatibility(
                    compat,
                    {
                        "camera_id": camera_id,
                        "battery_id": battery_id,
                        "status": status,
                        "quantity_required": 1,
                        "note": f"{source_name} lists this model as compatible with Battery Pack {model}.",
                        "source_name": source_name,
                        "source_url": source_url,
                        "source_type": "official_accessory_page",
                        "confidence": "high",
                        "last_verified": TODAY,
                    },
                )
                if camera_id not in existing_cameras:
                    camera_record = {key: candidate[key] for key in [
                        "camera_id",
                        "brand",
                        "series",
                        "model",
                        "display_name",
                        "aliases",
                        "regional_names",
                        "release_year",
                        "category",
                        "lens_type",
                        "battery_system",
                        "notes",
                    ]}
                    if camera_record["battery_system"] == "unknown":
                        camera_record["battery_system"] = "proprietary_li_ion"
                    cameras.append(camera_record)
                    existing_cameras[camera_id] = camera_record

    candidate_ids = {candidate["camera_id"] for candidate in candidates}
    verified_camera_ids = {
        row["camera_id"]
        for row in compat
        if row["camera_id"] in candidate_ids and row["status"] != "unknown"
    }
    unresolved = []
    for candidate in candidates:
        camera_id = candidate["camera_id"]
        if camera_id in verified_camera_ids:
            continue
        unresolved.append(
            {
                "camera_id": camera_id,
                "display_name": candidate["display_name"],
                "brand": "Canon",
                "series": candidate["series"],
                "release_year": candidate["release_year"],
                "reason": "Camera existence is confirmed by Canon Camera Museum, but no source-backed battery mapping was extracted in this batch.",
                "candidate_source_name": candidate["candidate_source_name"],
                "candidate_source_url": candidate["candidate_source_url"],
                "checked_source_urls": [candidate["candidate_source_url"]],
                "last_checked": TODAY,
            }
        )

    for candidate in candidates:
        candidate["candidate_status"] = "verified_battery" if candidate["camera_id"] in verified_camera_ids else "unresolved"

    all_batch_ids = previous_batch_ids | candidate_ids
    cameras = [
        camera
        for camera in cameras
        if not (camera["camera_id"] in all_batch_ids and camera["camera_id"] not in verified_camera_ids)
    ]

    retained_candidates = [
        row
        for row in previous_candidates
        if row.get("candidate_batch") != BATCH_ID
    ]
    previous_unresolved = load_json("unresolved_models.json")
    retained_unresolved = [
        row
        for row in previous_unresolved
        if row["camera_id"] not in all_batch_ids
    ]
    previous_sources = load_json("sources.json")
    current_source_ids = set(sources)
    retained_sources = [
        row
        for row in previous_sources
        if row["source_id"] not in current_source_ids
    ]

    DATA_DIR.mkdir(exist_ok=True)
    REPORT_DIR.mkdir(exist_ok=True)
    write_json(DATA_DIR / "cameras.json", sorted(cameras, key=lambda item: item["camera_id"]))
    write_json(DATA_DIR / "batteries.json", sorted(batteries, key=lambda item: item["battery_id"]))
    write_json(DATA_DIR / "compatibility.json", sorted(compat, key=lambda item: (item["camera_id"], item["battery_id"] or "", item["source_url"])))
    write_json(DATA_DIR / "camera_candidates.json", sorted(retained_candidates + candidates, key=lambda item: (item["brand"], item["series"], item["release_year"] or 0, item["display_name"])))
    write_json(DATA_DIR / "unresolved_models.json", sorted(retained_unresolved + unresolved, key=lambda item: (item["brand"], item["series"], item["display_name"])))
    write_json(DATA_DIR / "sources.json", sorted(retained_sources + list(sources.values()), key=lambda item: item["source_id"]))

    print(f"Canon candidates: {len(candidates)}")
    print(f"Canon verified camera IDs: {len(verified_camera_ids)}")
    print(f"Canon unresolved: {len(unresolved)}")


if __name__ == "__main__":
    main()
