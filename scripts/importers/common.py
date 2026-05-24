from __future__ import annotations

import copy
import html
import json
import re
import ssl
import urllib.request
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
REPORT_DIR = ROOT / "reports"

CAMERA_FIELDS = [
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
]

BATTERY_FIELDS = [
    "battery_id",
    "brand",
    "model",
    "aliases",
    "chemistry",
    "voltage",
    "capacity_mah",
    "notes",
]

COMPAT_FIELDS = [
    "camera_id",
    "battery_id",
    "status",
    "quantity_required",
    "note",
    "source_name",
    "source_url",
    "source_type",
    "confidence",
    "last_verified",
]

CANDIDATE_FIELDS = CAMERA_FIELDS + [
    "candidate_source_name",
    "candidate_source_url",
    "candidate_source_type",
    "candidate_batch",
    "candidate_status",
]

SOURCE_FIELDS = [
    "source_id",
    "source_name",
    "source_url",
    "source_type",
    "publisher",
    "last_verified",
    "notes",
]

UNRESOLVED_FIELDS = [
    "camera_id",
    "display_name",
    "brand",
    "series",
    "release_year",
    "reason",
    "candidate_source_name",
    "candidate_source_url",
    "checked_source_urls",
    "last_checked",
]

SOURCE_PRIORITY = {
    "official_manual": 60,
    "official_accessory_page": 55,
    "trusted_database": 40,
    "manual_mirror": 35,
    "retailer": 20,
    "third_party_chart": 15,
    "unknown": 0,
}

CONFIDENCE_PRIORITY = {"high": 30, "medium": 20, "low": 10}
SPECIAL_BATTERIES = {
    "2CR5": "generic_2cr5",
    "CR-V3": "generic_cr_v3",
    "CRV3": "generic_cr_v3",
    "CR123A": "generic_cr123a",
}


def load_json(path: Path, default: list[dict] | None = None) -> list[dict]:
    if not path.exists():
        return [] if default is None else default
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{path} must contain a JSON array")
    return data


def write_json(path: Path, data: list[dict]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def slugify(value: str) -> str:
    value = value.casefold()
    value = value.replace("&", " and ")
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return re.sub(r"_+", "_", value).strip("_")


def normalize_model_name(value: str) -> str:
    value = html.unescape(value or "")
    value = value.replace("\u00a0", " ")
    value = value.replace("–", "-").replace("—", "-").replace("‑", "-")
    value = re.sub(r"\s+", " ", value).strip()
    return value


def make_camera_id(brand: str, display_name: str) -> str:
    cleaned = normalize_model_name(display_name)
    brand_pattern = re.compile(rf"^{re.escape(brand)}\s+", re.I)
    cleaned = brand_pattern.sub("", cleaned)
    return f"{slugify(brand)}_{slugify(cleaned)}"


def make_battery_id(brand: str, model: str) -> str:
    normalized = normalize_model_name(model).upper().replace("_", "-")
    if normalized == "AA":
        return "generic_aa"
    if normalized == "AAA":
        return "generic_aaa"
    if normalized in SPECIAL_BATTERIES:
        return SPECIAL_BATTERIES[normalized]
    if normalized in {"BUILT-IN", "BUILT IN", "INTEGRATED"}:
        return "generic_built_in_battery"
    return f"{slugify(brand)}_{slugify(model)}"


def detect_category(brand: str, series: str, model: str, display_name: str = "") -> str:
    value = " ".join([series, model, display_name]).casefold()
    if any(token in value for token in ["tough", "tg-", "waterproof", "aw", "wg", "xp", "ft", "ts"]):
        return "waterproof_compact"
    if any(token in value for token in ["rx10", "p1000", "p950", "p900", "fz", "sx", "bridge", "hs ", "sl "]):
        return "bridge_superzoom"
    if any(token in value for token in ["rx1", "q3", "q2", "q ", "x100", "x70", "xf10", "gr iii", "gr iiix", "coolpix a"]):
        return "large_sensor_compact"
    if any(token in value for token in ["rx100", "lx", "d-lux", "x100", "gr", "dp", "xz"]):
        return "premium_compact"
    if any(token in value for token in ["tz", "zs", "hx", "wx", "travel"]):
        return "travel_zoom"
    if "3d" in value:
        return "3d_compact"
    return "point_and_shoot"


def detect_battery_system(power_text: str, battery_models: list[str] | None = None) -> str:
    text = normalize_model_name(power_text).casefold()
    models = [normalize_model_name(model).upper() for model in (battery_models or [])]
    if (
        "built-in" in text
        or "built in" in text
        or "integrated battery" in text
        or "内蔵充電池" in power_text
        or "内蔵バッテリー" in power_text
    ):
        return "built_in"
    if "aaa" in text or "AAA" in models:
        return "aaa"
    if re.search(r"\bAA\b|AA-size|size-aa", power_text, re.I) or "AA" in models:
        return "aa"
    if any(model in SPECIAL_BATTERIES for model in models) or re.search(r"\b(2CR5|CR-?V3|CR123A)\b", power_text, re.I):
        return "special"
    if battery_models or re.search(r"\b(NP|BP|DB|D-LI|EN-EL|LI-|KLIC)-?[A-Z0-9]+", power_text, re.I):
        return "proprietary_li_ion"
    return "unknown"


def exact_model_match(model: str, text: str, aliases: list[str] | None = None) -> bool:
    normalized_text = normalize_for_match(text)
    trailing_model_qualifier = r"(?!\s+(?:pro|mark|m\d+|ii|iii|iv|v|vi|vii|x|is|hs|fd|exr|zoom)\b)"
    for candidate in [model, *(aliases or [])]:
        normalized_model = normalize_for_match(candidate)
        if not normalized_model:
            continue
        pattern = (
            r"(?<![a-z0-9])"
            + re.escape(normalized_model).replace(r"\ ", r"\s+")
            + trailing_model_qualifier
            + r"(?![a-z0-9])"
        )
        if re.search(pattern, normalized_text):
            return True
    return False


def normalize_for_match(value: str) -> str:
    value = html.unescape(value or "").casefold()
    value = value.replace("cyber-shot", "cyber shot")
    value = value.replace("coolpix", "coolpix")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def validate_url(value: str) -> bool:
    parsed = urlparse(value or "")
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def source_priority_score(source_type: str, confidence: str | None = None) -> int:
    return SOURCE_PRIORITY.get(source_type, 0) + CONFIDENCE_PRIORITY.get(confidence or "", 0)


def dedupe_aliases(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        normalized = normalize_model_name(value)
        key = normalize_for_match(normalized)
        if normalized and key not in seen:
            seen.add(key)
            result.append(normalized)
    return result


def merge_regional_names(existing: dict[str, list[str]], incoming: dict[str, list[str]]) -> dict[str, list[str]]:
    merged = {key: list(value) for key, value in (existing or {}).items()}
    for region, names in (incoming or {}).items():
        merged[region] = dedupe_aliases([*merged.get(region, []), *names])
    return {key: value for key, value in merged.items() if value}


def strip_tags(value: str) -> str:
    value = re.sub(r"<br\s*/?>", " ", value, flags=re.I)
    value = re.sub(r"</tr\s*>", " ", value, flags=re.I)
    value = re.sub(r"</td\s*>", " ", value, flags=re.I)
    value = re.sub(r"</th\s*>", " ", value, flags=re.I)
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    value = value.replace("\u00a0", " ")
    return re.sub(r"\s+", " ", value).strip()


def clean_source_text(value: str) -> str:
    value = re.sub(r"<script\b.*?</script>", " ", value, flags=re.S | re.I)
    value = re.sub(r"<style\b.*?</style>", " ", value, flags=re.S | re.I)
    value = re.sub(r"<sup\b.*?</sup>", " ", value, flags=re.S | re.I)
    return strip_tags(value)


def extract_release_year(value: str) -> int | None:
    years = [int(item) for item in re.findall(r"\b(19\d{2}|20\d{2})\b", value or "")]
    valid = [year for year in years if 1998 <= year <= 2026]
    return valid[0] if valid else None


def remove_release_year_text(value: str) -> str:
    value = re.sub(r"\(\s*(?:19\d{2}|20\d{2})\s*\)", " ", value or "")
    value = re.sub(r"\s+[-–—]\s*(?:19\d{2}|20\d{2})\b", " ", value)
    return normalize_model_name(value)


def camera_wiki_link_texts(page_text: str, page_url: str) -> list[dict]:
    records = []
    for href, label in re.findall(r'<a\s+[^>]*href="([^"]+)"[^>]*>(.*?)</a>', page_text, flags=re.S | re.I):
        text = clean_source_text(label)
        if not text:
            continue
        if href.startswith("#") or ":" in href.split("/wiki/")[-1].split("?")[0]:
            continue
        if "redlink=1" in href:
            source_url = page_url
        else:
            source_url = urljoin(page_url, html.unescape(href))
        records.append({"text": text, "source_url": source_url})
    return records


def camera_wiki_list_item_texts(page_text: str) -> list[str]:
    records = []
    for item in re.findall(r"<li\b[^>]*>(.*?)</li>", page_text, flags=re.S | re.I):
        text = clean_source_text(item)
        if text:
            records.append(text)
    return records


def camera_wiki_find_matches(page_text: str, page_url: str, pattern: str) -> list[dict]:
    compiled = re.compile(pattern, flags=re.I)
    records: list[dict] = []

    for link in camera_wiki_link_texts(page_text, page_url):
        for match in compiled.finditer(link["text"]):
            records.append(
                {
                    "raw_name": match.group(0),
                    "context": link["text"],
                    "source_url": link["source_url"],
                }
            )

    for text in camera_wiki_list_item_texts(page_text):
        for match in compiled.finditer(text):
            records.append(
                {
                    "raw_name": match.group(0),
                    "context": text,
                    "source_url": page_url,
                }
            )
    return records


def dedupe_catalog_records(records: list[dict]) -> list[dict]:
    deduped = []
    seen = set()
    for record in records:
        names = [record["display_name"], record["model"], *record.get("aliases", [])]
        key = (record["brand"].casefold(), normalize_for_match(record["display_name"]))
        alias_key = frozenset(normalize_for_match(name) for name in names if normalize_for_match(name))
        if (key, alias_key) in seen:
            continue
        seen.add((key, alias_key))
        deduped.append(record)
    return deduped


def camera_wiki_source_name(display_name: str, list_source_name: str, source_url: str, list_url: str) -> str:
    if source_url == list_url:
        return list_source_name
    return f"Camera-wiki {display_name}"


def read_response_text(response) -> str:
    raw = response.read()
    charset = response.headers.get_content_charset()
    if charset:
        return raw.decode(charset, errors="replace")
    for fallback in ("utf-8", "shift_jis", "cp932", "latin-1"):
        try:
            return raw.decode(fallback)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def fetch_text(url: str, timeout: int = 30) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 camera-battery-db/1.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    context = ssl.create_default_context()
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
            return read_response_text(response)
    except ssl.SSLError:
        with urllib.request.urlopen(request, timeout=timeout, context=ssl._create_unverified_context()) as response:
            return read_response_text(response)


def safe_extract_power_source_text(page_text: str) -> str | None:
    labels = [
        "Power sources",
        "Power source",
        "Power supply",
        "Power",
        "Battery system",
        "Battery type",
        "Rechargeable battery",
        "Batteries",
        "Battery",
        "Supplied accessories",
        "Included accessories",
        "Accessories supplied",
        "バッテリーパック",
        "電池",
        "電源",
        "使用電池",
        "充電池",
    ]
    for label in labels:
        pattern = re.compile(
            rf"<(?:td|th)[^>]*>\s*(?:<[^>]+>\s*)*{re.escape(label)}\s*(?:</[^>]+>\s*)*</(?:td|th)>\s*"
            rf"<td[^>]*>(.*?)</td>",
            re.S | re.I,
        )
        match = pattern.search(page_text)
        if match:
            return strip_tags(match.group(1))

    section_pattern = re.compile(
        r'<(?:td|th)[^>]*colspan="[^"]+"[^>]*>\s*(?:<[^>]+>\s*)*\[?\s*(?:Power Source|Power Supply|Power)\s*\]?\s*(?:</[^>]+>\s*)*</(?:td|th)>\s*</tr>\s*'
        r'<tr>\s*<(?:td|th)[^>]*>\s*(?:Batteries|Battery|Battery Type)\s*</(?:td|th)>\s*<td[^>]*>(.*?)</td>',
        re.S | re.I,
    )
    match = section_pattern.search(page_text)
    if match:
        return strip_tags(match.group(1))

    text = strip_tags(page_text)
    text = re.sub(r"\s+", " ", text)
    fallback = re.search(
        r"(?<!AC )\b(Power sources?|Power supply|Battery system|Battery type|Battery Pack|Rechargeable Lithium-Ion Battery|Li-ion Battery Pack|Rechargeable battery|Batteries|Supplied accessories|Included accessories)\b"
        r"\s*:?\s+(.{1,420}?)(?:Operating|Dimensions|Weight|Interface|Storage|Bluetooth|Wi-Fi|WLAN|Flash|Lens|$)",
        text,
        re.I,
    )
    if fallback:
        snippet = fallback.group(2).strip()
        if re.search(r"\b(?:built[- ]?in flash|internal memory|flash memory|battery charger|AC adapter)\b", snippet, re.I) and not re.search(
            r"\b(?:NP-|BP-|DB-|D-LI|EN-EL|LI-|KLIC-|DMW-|NB-|AA|AAA|CR-?V3|CR123A|2CR5|battery pack|batteries)\b|電池|バッテリー|充電池",
            snippet,
            re.I,
        ):
            return None
        return snippet
    japanese = re.search(
        r"(?:バッテリーパック|使用電池|電池|電源|充電池)\s*:?\s*(.{1,260}?)(?:寸法|質量|重量|記録媒体|メモリー|フラッシュ|レンズ|$)",
        text,
        re.I,
    )
    if japanese:
        return japanese.group(1).strip()
    return None


def cell_quantity(source: str, cell_name: str) -> int | None:
    number_words = {"one": 1, "two": 2, "three": 3, "four": 4}
    cell_pattern = rf"(?:{re.escape(cell_name)}(?:-size)?|size[-\s]?{re.escape(cell_name)})"
    patterns = [
        rf"\b([1-4])\s*(?:x|×)?\s*{cell_pattern}\b",
        rf"\b{cell_pattern}\s*(?:x|×)\s*([1-4])\b",
        rf"\b{cell_pattern}\b.{{0,90}}?(?:x|×)\s*([1-4])\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, source, re.I)
        if match:
            return int(match.group(1))
    word_match = re.search(rf"\b({'|'.join(number_words)})\s+{cell_pattern}\b", source, re.I)
    if word_match:
        return number_words[word_match.group(1).lower()]
    return None


def parse_power_mappings(power_text: str, fallback_brand: str = "Generic") -> list[dict]:
    source = normalize_model_name(power_text)
    mappings: list[dict] = []

    aa_quantity = cell_quantity(source, "AA")
    aaa_quantity = cell_quantity(source, "AAA")
    if re.search(r"\bAA\b|AA-size|Size-AA|単3形|単三", source, re.I):
        if aa_quantity is None:
            match = re.search(r"(?:単3形|単三).{0,35}?(?:各|×|x)?\s*([1-4])\s*本", source, re.I)
            if match:
                aa_quantity = int(match.group(1))
        mappings.append({"brand": "Generic", "model": "AA", "status": "uses_aa", "quantity_required": aa_quantity})
    if re.search(r"\bAAA\b|AAA-size|Size-AAA|単4形|単四", source, re.I):
        if aaa_quantity is None:
            match = re.search(r"(?:単4形|単四).{0,35}?(?:各|×|x)?\s*([1-4])\s*本", source, re.I)
            if match:
                aaa_quantity = int(match.group(1))
        mappings.append({"brand": "Generic", "model": "AAA", "status": "uses_aaa", "quantity_required": aaa_quantity})
    if re.search(
        r"\b(?:built[- ]?in|integrated|internal|non[- ]?removable)\s+(?:rechargeable\s+)?battery\b|"
        r"\bbattery\s+(?:is\s+)?(?:built[- ]?in|integrated|internal|non[- ]?removable)\b|"
        r"(?:内蔵充電池|内蔵バッテリー|充電式内蔵電池)",
        source,
        re.I,
    ):
        mappings.append({"brand": "Generic", "model": "Built-in", "status": "built_in_battery", "quantity_required": 1})

    for model in sorted(set(re.findall(r"\b(?:2CR5|CR-?V3|CR123A)\b", source, re.I)), key=lambda item: source.upper().find(item.upper())):
        normalized = model.upper().replace("CRV3", "CR-V3")
        mappings.append({"brand": "Generic", "model": normalized, "status": "fully_compatible", "quantity_required": 1})

    battery_pattern = re.compile(
        r"\b(?:"
        r"NP-[A-Z0-9]+|BP-[A-Z0-9]+|BP-SCL\d+|DB-\d+|D-LI\d+|D-LI-\d+|EN-EL\d+[a-z]?|"
        r"LI-\d+[A-Z]?|LI\d+[A-Z]?|KLIC-\d+|DMW-[A-Z0-9]+|VW-V[A-Z0-9]+|BCN-\d+|LI-\d+B?|"
        r"NB-\d+[A-Z]*|NP-W\d+S?|NP-\d+|BLS-\d+|LI-?\d+[A-Z]*"
        r")\b",
        re.I,
    )
    for model in sorted(set(match.group(0).upper() for match in battery_pattern.finditer(source)), key=lambda item: source.upper().find(item)):
        if model in {"USB", "HDMI"}:
            continue
        brand = fallback_brand
        mappings.append({"brand": brand, "model": model, "status": "fully_compatible", "quantity_required": 1})

    deduped = []
    seen = set()
    for mapping in mappings:
        key = (mapping["brand"], mapping["model"], mapping["status"])
        if key not in seen:
            seen.add(key)
            deduped.append(mapping)
    return deduped


@dataclass
class ImportContext:
    root: Path = ROOT
    today: str = field(default_factory=lambda: date.today().isoformat())
    cameras: list[dict] = field(default_factory=list)
    batteries: list[dict] = field(default_factory=list)
    compatibility: list[dict] = field(default_factory=list)
    candidates: list[dict] = field(default_factory=list)
    sources: list[dict] = field(default_factory=list)
    unresolved: list[dict] = field(default_factory=list)
    warnings: list[dict] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)
    processed_brands: list[str] = field(default_factory=list)
    missing_source_brands: list[dict] = field(default_factory=list)
    risky_matches: list[dict] = field(default_factory=list)
    duplicate_compatibility: list[dict] = field(default_factory=list)

    @classmethod
    def load(cls, root: Path = ROOT) -> "ImportContext":
        data_dir = root / "data"
        ctx = cls(root=root)
        ctx.cameras = load_json(data_dir / "cameras.json")
        ctx.batteries = load_json(data_dir / "batteries.json")
        ctx.compatibility = load_json(data_dir / "compatibility.json")
        ctx.candidates = load_json(data_dir / "camera_candidates.json", [])
        ctx.sources = load_json(data_dir / "sources.json", [])
        ctx.unresolved = load_json(data_dir / "unresolved_models.json", [])
        return ctx

    def snapshot(self) -> dict[str, Any]:
        return {
            "cameras": copy.deepcopy(self.cameras),
            "batteries": copy.deepcopy(self.batteries),
            "compatibility": copy.deepcopy(self.compatibility),
            "candidates": copy.deepcopy(self.candidates),
            "sources": copy.deepcopy(self.sources),
            "unresolved": copy.deepcopy(self.unresolved),
            "warnings": copy.deepcopy(self.warnings),
            "errors": copy.deepcopy(self.errors),
            "processed_brands": copy.deepcopy(self.processed_brands),
            "missing_source_brands": copy.deepcopy(self.missing_source_brands),
            "risky_matches": copy.deepcopy(self.risky_matches),
            "duplicate_compatibility": copy.deepcopy(self.duplicate_compatibility),
        }

    def restore(self, snapshot: dict[str, Any]) -> None:
        for key, value in snapshot.items():
            setattr(self, key, value)

    def sort_all(self) -> None:
        self.cameras = sorted(self.cameras, key=lambda item: item["camera_id"])
        self.batteries = sorted(self.batteries, key=lambda item: item["battery_id"])
        self.compatibility = sorted(
            self.compatibility,
            key=lambda item: (item["camera_id"], item["battery_id"] or "", item["status"], item["source_url"]),
        )
        self.candidates = sorted(self.candidates, key=lambda item: (item["brand"], item["series"], item["release_year"] or 0, item["display_name"]))
        self.sources = sorted(self.sources, key=lambda item: item["source_id"])
        self.unresolved = sorted(self.unresolved, key=lambda item: (item["brand"], item["series"], item["display_name"]))

    def write_all(self) -> None:
        data_dir = self.root / "data"
        data_dir.mkdir(exist_ok=True)
        self.sort_all()
        write_json(data_dir / "cameras.json", self.cameras)
        write_json(data_dir / "batteries.json", self.batteries)
        write_json(data_dir / "compatibility.json", self.compatibility)
        write_json(data_dir / "camera_candidates.json", self.candidates)
        write_json(data_dir / "sources.json", self.sources)
        write_json(data_dir / "unresolved_models.json", self.unresolved)


def source_record(source_id: str, source_name: str, source_url: str, source_type: str, publisher: str, today: str, notes: str = "") -> dict:
    return {
        "source_id": source_id,
        "source_name": source_name,
        "source_url": source_url,
        "source_type": source_type,
        "publisher": publisher,
        "last_verified": today,
        "notes": notes,
    }


def register_source(ctx: ImportContext, source_name: str, source_url: str, source_type: str, publisher: str, notes: str = "") -> str:
    if not validate_url(source_url):
        raise ValueError(f"Invalid source_url: {source_url}")
    source_id = slugify(f"{publisher}_{source_name}_{source_url}")[:120].strip("_")
    row = source_record(source_id, source_name, source_url, source_type, publisher, ctx.today, notes)
    by_id = {source["source_id"]: source for source in ctx.sources}
    if source_id not in by_id:
        ctx.sources.append(row)
    else:
        existing = by_id[source_id]
        if source_priority_score(source_type) >= source_priority_score(existing["source_type"]):
            existing.update(row)
    return source_id


def camera_record_from_candidate(candidate: dict) -> dict:
    return {field: candidate[field] for field in CAMERA_FIELDS}


def iter_camera_names(camera: dict) -> list[str]:
    names = [camera["display_name"], camera["model"], *camera["aliases"]]
    for regional_names in camera["regional_names"].values():
        names.extend(regional_names)
    return dedupe_aliases(names)


def resolve_existing_camera_id(ctx: ImportContext, brand: str, names: list[str]) -> str | None:
    incoming = {normalize_for_match(name) for name in names if normalize_for_match(name)}
    if not incoming:
        return None
    for collection in (ctx.candidates, ctx.cameras):
        for row in collection:
            if row["brand"].casefold() != brand.casefold():
                continue
            existing = {normalize_for_match(name) for name in iter_camera_names(row) if normalize_for_match(name)}
            if incoming & existing:
                return row["camera_id"]
    return None


def clear_batch_rows(ctx: ImportContext, batch_id: str) -> None:
    batch_ids = {
        row["camera_id"]
        for row in ctx.candidates
        if row.get("candidate_batch") == batch_id
    }
    if not batch_ids:
        return
    ctx.candidates = [row for row in ctx.candidates if row.get("candidate_batch") != batch_id]
    ctx.cameras = [row for row in ctx.cameras if row["camera_id"] not in batch_ids]
    ctx.compatibility = [row for row in ctx.compatibility if row["camera_id"] not in batch_ids]
    ctx.unresolved = [row for row in ctx.unresolved if row["camera_id"] not in batch_ids]


def add_or_update_camera_candidate(ctx: ImportContext, candidate: dict) -> dict:
    for field_name in CANDIDATE_FIELDS:
        if field_name not in candidate:
            raise ValueError(f"candidate missing {field_name}: {candidate}")
    candidate = copy.deepcopy(candidate)
    candidate["aliases"] = dedupe_aliases(candidate["aliases"])
    candidate["regional_names"] = merge_regional_names({}, candidate["regional_names"])
    candidate["display_name"] = normalize_model_name(candidate["display_name"])
    candidate["model"] = normalize_model_name(candidate["model"])

    existing = next((row for row in ctx.candidates if row["camera_id"] == candidate["camera_id"]), None)
    if existing is None:
        ctx.candidates.append(candidate)
        return candidate

    existing["aliases"] = dedupe_aliases([*existing["aliases"], *candidate["aliases"]])
    existing["regional_names"] = merge_regional_names(existing["regional_names"], candidate["regional_names"])
    for key in ["brand", "series", "model", "display_name", "category", "lens_type"]:
        if not existing.get(key) and candidate.get(key):
            existing[key] = candidate[key]
    if existing["release_year"] is None and candidate["release_year"] is not None:
        existing["release_year"] = candidate["release_year"]
    if existing["battery_system"] == "unknown" and candidate["battery_system"] != "unknown":
        existing["battery_system"] = candidate["battery_system"]
    if not existing["notes"] and candidate["notes"]:
        existing["notes"] = candidate["notes"]
    if candidate["candidate_status"] == "verified_battery":
        existing["candidate_status"] = "verified_battery"
    if source_priority_score(candidate["candidate_source_type"]) >= source_priority_score(existing["candidate_source_type"]):
        existing["candidate_source_name"] = candidate["candidate_source_name"]
        existing["candidate_source_url"] = candidate["candidate_source_url"]
        existing["candidate_source_type"] = candidate["candidate_source_type"]
    existing["candidate_batch"] = existing.get("candidate_batch") or candidate["candidate_batch"]
    return existing


def add_or_update_verified_camera(ctx: ImportContext, camera: dict) -> dict:
    camera = copy.deepcopy(camera)
    camera["aliases"] = dedupe_aliases(camera["aliases"])
    camera["regional_names"] = merge_regional_names({}, camera["regional_names"])
    existing = next((row for row in ctx.cameras if row["camera_id"] == camera["camera_id"]), None)
    if existing is None:
        ctx.cameras.append(camera)
        return camera
    existing["aliases"] = dedupe_aliases([*existing["aliases"], *camera["aliases"]])
    existing["regional_names"] = merge_regional_names(existing["regional_names"], camera["regional_names"])
    if existing["release_year"] is None and camera["release_year"] is not None:
        existing["release_year"] = camera["release_year"]
    if existing["battery_system"] == "unknown" and camera["battery_system"] != "unknown":
        existing["battery_system"] = camera["battery_system"]
    if not existing["notes"] and camera["notes"]:
        existing["notes"] = camera["notes"]
    return existing


def add_or_update_battery(ctx: ImportContext, battery: dict) -> dict:
    for field_name in BATTERY_FIELDS:
        if field_name not in battery:
            raise ValueError(f"battery missing {field_name}: {battery}")
    battery = copy.deepcopy(battery)
    battery["aliases"] = dedupe_aliases(battery["aliases"])
    existing = next((row for row in ctx.batteries if row["battery_id"] == battery["battery_id"]), None)
    if existing is None:
        ctx.batteries.append(battery)
        return battery
    existing["aliases"] = dedupe_aliases([*existing["aliases"], *battery["aliases"]])
    for field_name in ["brand", "model", "chemistry", "voltage", "capacity_mah", "notes"]:
        if existing.get(field_name) in {None, ""} and battery.get(field_name) not in {None, ""}:
            existing[field_name] = battery[field_name]
    return existing


def battery_record(brand: str, model: str, notes: str = "") -> dict:
    normalized = normalize_model_name(model)
    battery_id = make_battery_id(brand, normalized)
    if battery_id == "generic_aa":
        return {"battery_id": battery_id, "brand": "Generic", "model": "AA", "aliases": ["AA cell"], "chemistry": "various", "voltage": None, "capacity_mah": None, "notes": notes}
    if battery_id == "generic_aaa":
        return {"battery_id": battery_id, "brand": "Generic", "model": "AAA", "aliases": ["AAA cell"], "chemistry": "various", "voltage": None, "capacity_mah": None, "notes": notes}
    if battery_id in {"generic_2cr5", "generic_cr_v3", "generic_cr123a"}:
        return {"battery_id": battery_id, "brand": "Generic", "model": normalized.upper(), "aliases": [], "chemistry": "lithium", "voltage": None, "capacity_mah": None, "notes": notes or "Special battery format; electrical details left blank until source-backed."}
    if battery_id == "generic_built_in_battery":
        return {"battery_id": battery_id, "brand": "Generic", "model": "Built-in battery", "aliases": ["Integrated rechargeable battery"], "chemistry": None, "voltage": None, "capacity_mah": None, "notes": notes or "Generic built-in battery placeholder used only when source confirms built-in power but no model is named."}
    return {"battery_id": battery_id, "brand": brand, "model": normalized, "aliases": [], "chemistry": "lithium-ion", "voltage": None, "capacity_mah": None, "notes": notes}


def add_compatibility_source_backed(
    ctx: ImportContext,
    candidate: dict,
    battery: dict,
    status: str,
    quantity_required: int | None,
    note: str,
    source_name: str,
    source_url: str,
    source_type: str,
    confidence: str,
    publisher: str,
) -> dict:
    if status == "unknown":
        raise ValueError("source-backed compatibility cannot use unknown status")
    if not validate_url(source_url):
        raise ValueError(f"Invalid compatibility source URL: {source_url}")
    register_source(ctx, source_name, source_url, source_type, publisher, note)

    candidate = copy.deepcopy(candidate)
    candidate["candidate_status"] = "verified_battery"
    candidate["battery_system"] = detect_battery_system(note, [battery["model"]])
    candidate = add_or_update_camera_candidate(ctx, candidate)
    add_or_update_verified_camera(ctx, camera_record_from_candidate(candidate))
    battery = add_or_update_battery(ctx, battery)
    remove_unresolved(ctx, candidate["camera_id"])

    row = {
        "camera_id": candidate["camera_id"],
        "battery_id": battery["battery_id"],
        "status": status,
        "quantity_required": quantity_required,
        "note": note,
        "source_name": source_name,
        "source_url": source_url,
        "source_type": source_type,
        "confidence": confidence,
        "last_verified": ctx.today,
    }
    existing = next(
        (
            item
            for item in ctx.compatibility
            if item["camera_id"] == row["camera_id"]
            and item["battery_id"] == row["battery_id"]
            and item["status"] == row["status"]
            and item["source_url"] == row["source_url"]
        ),
        None,
    )
    if existing is None:
        ctx.compatibility.append(row)
    else:
        existing.update(row)
    return row


def add_unresolved_model(
    ctx: ImportContext,
    candidate: dict,
    reason: str,
    checked_source_urls: list[str],
) -> dict:
    if candidate["camera_id"] in {row["camera_id"] for row in ctx.cameras}:
        return {}
    candidate = copy.deepcopy(candidate)
    candidate["candidate_status"] = "unresolved"
    candidate["battery_system"] = candidate.get("battery_system") or "unknown"
    candidate = add_or_update_camera_candidate(ctx, candidate)
    remove_unresolved(ctx, candidate["camera_id"])
    row = {
        "camera_id": candidate["camera_id"],
        "display_name": candidate["display_name"],
        "brand": candidate["brand"],
        "series": candidate["series"],
        "release_year": candidate["release_year"],
        "reason": reason,
        "candidate_source_name": candidate["candidate_source_name"],
        "candidate_source_url": candidate["candidate_source_url"],
        "checked_source_urls": checked_source_urls,
        "last_checked": ctx.today,
    }
    ctx.unresolved.append(row)
    return row


def remove_unresolved(ctx: ImportContext, camera_id: str) -> None:
    ctx.unresolved = [row for row in ctx.unresolved if row["camera_id"] != camera_id]


def dedupe_compatibility_for_app_output(ctx: ImportContext) -> list[dict]:
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for row in ctx.compatibility:
        groups[(row["camera_id"], row["battery_id"], row["status"], row["source_url"])].append(row)
    duplicates = []
    deduped = []
    for key, rows in groups.items():
        rows_sorted = sorted(
            rows,
            key=lambda row: source_priority_score(row["source_type"], row["confidence"]),
            reverse=True,
        )
        deduped.append(rows_sorted[0])
        if len(rows) > 1:
            duplicates.append(
                {
                    "key": {
                        "camera_id": key[0],
                        "battery_id": key[1],
                        "status": key[2],
                        "source_url": key[3],
                    },
                    "count": len(rows),
                    "kept": rows_sorted[0],
                    "duplicates": rows_sorted[1:],
                    "explanation": "Exact duplicate compatibility rows collapsed by import_all_remaining.py.",
                }
            )
    ctx.compatibility = deduped
    ctx.duplicate_compatibility = duplicates
    return duplicates


def backfill_sources_and_verified_candidates(ctx: ImportContext) -> None:
    camera_by_id = {camera["camera_id"]: camera for camera in ctx.cameras}
    candidate_ids = {candidate["camera_id"] for candidate in ctx.candidates}
    compat_by_camera: dict[str, list[dict]] = defaultdict(list)

    for row in ctx.compatibility:
        camera = camera_by_id.get(row["camera_id"])
        if not camera:
            continue
        register_source(
            ctx,
            row["source_name"],
            row["source_url"],
            row["source_type"],
            camera["brand"],
            "Backfilled source registry entry from an existing compatibility row.",
        )
        if row["status"] != "unknown":
            compat_by_camera[row["camera_id"]].append(row)

    for camera_id, rows in compat_by_camera.items():
        if camera_id in candidate_ids:
            continue
        camera = camera_by_id[camera_id]
        best_row = sorted(
            rows,
            key=lambda item: source_priority_score(item["source_type"], item["confidence"]),
            reverse=True,
        )[0]
        candidate = {
            **copy.deepcopy(camera),
            "candidate_source_name": best_row["source_name"],
            "candidate_source_url": best_row["source_url"],
            "candidate_source_type": best_row["source_type"],
            "candidate_batch": "backfill_existing_verified_cameras",
            "candidate_status": "verified_battery",
        }
        add_or_update_camera_candidate(ctx, candidate)


def move_unknown_only_cameras_to_unresolved(ctx: ImportContext) -> None:
    compat_by_camera: dict[str, list[dict]] = defaultdict(list)
    for row in ctx.compatibility:
        compat_by_camera[row["camera_id"]].append(row)

    unknown_only_ids = {
        camera_id
        for camera_id, rows in compat_by_camera.items()
        if rows and all(row["status"] == "unknown" for row in rows)
    }
    if not unknown_only_ids:
        return

    camera_by_id = {camera["camera_id"]: camera for camera in ctx.cameras}
    for camera_id in sorted(unknown_only_ids):
        camera = camera_by_id.get(camera_id)
        if not camera:
            continue
        source_row = compat_by_camera[camera_id][0]
        candidate = {
            **copy.deepcopy(camera),
            "battery_system": "unknown",
            "candidate_source_name": source_row["source_name"],
            "candidate_source_url": source_row["source_url"],
            "candidate_source_type": source_row["source_type"],
            "candidate_batch": "migrated_unknown_only_cameras",
            "candidate_status": "unresolved",
        }
        add_or_update_camera_candidate(ctx, candidate)
        remove_unresolved(ctx, camera_id)
        ctx.unresolved.append(
            {
                "camera_id": camera_id,
                "display_name": camera["display_name"],
                "brand": camera["brand"],
                "series": camera["series"],
                "release_year": camera["release_year"],
                "reason": "Legacy camera row had only unknown battery compatibility; moved to unresolved until a source-backed battery mapping is found.",
                "candidate_source_name": source_row["source_name"],
                "candidate_source_url": source_row["source_url"],
                "checked_source_urls": [source_row["source_url"]],
                "last_checked": ctx.today,
            }
        )

    ctx.cameras = [camera for camera in ctx.cameras if camera["camera_id"] not in unknown_only_ids]
    ctx.compatibility = [row for row in ctx.compatibility if row["camera_id"] not in unknown_only_ids]


def candidate_template(
    brand: str,
    series: str,
    model: str,
    display_name: str,
    source_name: str,
    source_url: str,
    source_type: str,
    batch_id: str,
    release_year: int | None = None,
    category: str | None = None,
    aliases: list[str] | None = None,
    regional_names: dict[str, list[str]] | None = None,
    battery_system: str = "unknown",
    notes: str = "",
) -> dict:
    return {
        "camera_id": make_camera_id(brand, display_name),
        "brand": brand,
        "series": series,
        "model": normalize_model_name(model),
        "display_name": normalize_model_name(display_name),
        "aliases": dedupe_aliases(aliases or []),
        "regional_names": merge_regional_names({}, regional_names or {}),
        "release_year": release_year,
        "category": category or detect_category(brand, series, model, display_name),
        "lens_type": "fixed_lens",
        "battery_system": battery_system,
        "notes": notes,
        "candidate_source_name": source_name,
        "candidate_source_url": source_url,
        "candidate_source_type": source_type,
        "candidate_batch": batch_id,
        "candidate_status": "unresolved",
    }


def import_official_spec_records(ctx: ImportContext, batch_id: str, records: list[dict]) -> dict:
    clear_batch_rows(ctx, batch_id)
    result = {"processed": 0, "verified": 0, "unresolved": 0, "warnings": []}
    for record in records:
        result["processed"] += 1
        source_name = record["source_name"]
        source_url = record["source_url"]
        publisher = record.get("publisher", record["brand"])
        source_type = record.get("source_type", "official_manual")
        confidence = record.get("confidence", "high")
        candidate = candidate_template(
            brand=record["brand"],
            series=record["series"],
            model=record["model"],
            display_name=record["display_name"],
            source_name=source_name,
            source_url=source_url,
            source_type=source_type,
            batch_id=batch_id,
            release_year=record.get("release_year"),
            category=record.get("category"),
            aliases=record.get("aliases", []),
            regional_names=record.get("regional_names", {}),
            notes=record.get("notes", ""),
        )
        existing_camera_id = resolve_existing_camera_id(
            ctx,
            record["brand"],
            [
                candidate["display_name"],
                candidate["model"],
                *candidate["aliases"],
                *[name for names in candidate["regional_names"].values() for name in names],
            ],
        )
        if existing_camera_id:
            candidate["camera_id"] = existing_camera_id
        try:
            page = fetch_text(source_url)
        except Exception as exc:
            add_unresolved_model(
                ctx,
                candidate,
                f"Official/trusted source could not be fetched during import: {type(exc).__name__}: {exc}",
                [source_url],
            )
            result["unresolved"] += 1
            result["warnings"].append({"camera": candidate["display_name"], "url": source_url, "error": str(exc)})
            continue

        register_source(ctx, source_name, source_url, source_type, publisher, "Source page fetched by import_all_remaining.py.")
        power_text = safe_extract_power_source_text(page) or ""
        plain = strip_tags(page)
        expected = record.get("expected_batteries")
        if expected:
            mappings = []
            for item in expected:
                model = item["model"]
                aliases = item.get("aliases", [])
                search_space = " ".join([power_text, plain])
                if not exact_model_match(model, search_space, aliases):
                    continue
                mappings.append(
                    {
                        "brand": item.get("brand", record["brand"]),
                        "model": model,
                        "status": item.get("status", "fully_compatible"),
                        "quantity_required": item.get("quantity_required", 1),
                    }
                )
        else:
            mappings = parse_power_mappings(power_text, record["brand"])

        if not mappings:
            add_unresolved_model(
                ctx,
                candidate,
                "Camera existence is confirmed by source, but no exact source-backed battery mapping was extracted.",
                [source_url],
            )
            result["unresolved"] += 1
            continue

        for mapping in mappings:
            battery = battery_record(
                mapping.get("brand", record["brand"]),
                mapping["model"],
                "Added by import_all_remaining.py; electrical details left blank unless source-backed.",
            )
            note_text = power_text or f"Source page contains exact battery token {mapping['model']} for {candidate['display_name']}."
            if mapping["status"] in {"uses_aa", "uses_aaa"} and mapping.get("quantity_required") is None:
                note_text += " Source confirms AA/AAA battery type but does not state quantity."
            add_compatibility_source_backed(
                ctx,
                candidate,
                battery,
                mapping["status"],
                mapping.get("quantity_required"),
                note_text,
                source_name,
                source_url,
                source_type,
                confidence,
                publisher,
            )
        result["verified"] += 1
    return result


def import_camera_wiki_catalog(
    ctx: ImportContext,
    batch_id: str,
    list_source_name: str,
    list_url: str,
    publisher: str,
    records: list[dict],
    verify_individual_pages: bool = False,
    max_verify_pages: int | None = None,
) -> dict:
    clear_batch_rows(ctx, batch_id)
    register_source(
        ctx,
        list_source_name,
        list_url,
        "trusted_database",
        publisher,
        "Camera-wiki catalog page used to confirm camera model existence.",
    )

    result = {
        "processed": 0,
        "verified": 0,
        "unresolved": 0,
        "warnings": [],
        "adapter_status": "real_adapter",
    }
    verified_fetches = 0

    for record in dedupe_catalog_records(records):
        result["processed"] += 1
        source_url = record.get("source_url") or list_url
        source_name = camera_wiki_source_name(record["display_name"], list_source_name, source_url, list_url)
        register_source(
            ctx,
            source_name,
            source_url,
            "trusted_database",
            publisher,
            "Camera-wiki source used to confirm camera model existence.",
        )
        candidate = candidate_template(
            brand=record["brand"],
            series=record["series"],
            model=record["model"],
            display_name=record["display_name"],
            source_name=source_name,
            source_url=source_url,
            source_type="trusted_database",
            batch_id=batch_id,
            release_year=record.get("release_year"),
            category=record.get("category"),
            aliases=record.get("aliases", []),
            regional_names=record.get("regional_names", {}),
            battery_system=record.get("battery_system", "unknown"),
            notes=record.get("notes", "Candidate existence imported from Camera-wiki; battery mapping not inferred."),
        )
        existing_camera_id = resolve_existing_camera_id(
            ctx,
            record["brand"],
            [
                candidate["display_name"],
                candidate["model"],
                *candidate["aliases"],
                *[name for names in candidate["regional_names"].values() for name in names],
            ],
        )
        if existing_camera_id:
            candidate["camera_id"] = existing_camera_id

        mappings: list[dict] = []
        power_text = ""
        if (
            verify_individual_pages
            and source_url != list_url
            and (max_verify_pages is None or verified_fetches < max_verify_pages)
            and candidate["camera_id"] not in {camera["camera_id"] for camera in ctx.cameras}
        ):
            try:
                page = fetch_text(source_url)
                verified_fetches += 1
                plain = clean_source_text(page)
                aliases = [candidate["display_name"], candidate["model"], *candidate["aliases"]]
                if exact_model_match(candidate["model"], plain, aliases):
                    power_text = safe_extract_power_source_text(page) or ""
                    mappings = parse_power_mappings(power_text, record["brand"]) if power_text else []
                else:
                    result["warnings"].append(
                        {
                            "camera": candidate["display_name"],
                            "url": source_url,
                            "warning": "Skipped battery extraction because exact model match failed on source page.",
                        }
                    )
            except Exception as exc:
                result["warnings"].append(
                    {
                        "camera": candidate["display_name"],
                        "url": source_url,
                        "warning": f"Could not fetch model page for battery extraction: {type(exc).__name__}: {exc}",
                    }
                )

        if mappings:
            for mapping in mappings:
                battery = battery_record(
                    mapping.get("brand", record["brand"]),
                    mapping["model"],
                    "Added from Camera-wiki trusted database; electrical details left blank unless source-backed.",
                )
                note_text = power_text or f"Camera-wiki page contains exact battery token {mapping['model']} for {candidate['display_name']}."
                if mapping["status"] in {"uses_aa", "uses_aaa"} and mapping.get("quantity_required") is None:
                    note_text += " Source confirms AA/AAA battery type but does not state quantity."
                add_compatibility_source_backed(
                    ctx,
                    candidate,
                    battery,
                    mapping["status"],
                    mapping.get("quantity_required"),
                    note_text,
                    source_name,
                    source_url,
                    "trusted_database",
                    "medium",
                    publisher,
                )
            result["verified"] += 1
        else:
            row = add_unresolved_model(
                ctx,
                candidate,
                "Camera existence confirmed, battery not yet source-verified",
                [source_url],
            )
            if row:
                result["unresolved"] += 1

    if verify_individual_pages:
        result["adapter_status"] = "partial_adapter"
    return result


def mark_brand_processed(ctx: ImportContext, brand: str) -> None:
    if brand not in ctx.processed_brands:
        ctx.processed_brands.append(brand)


def merge_import_results(*results: dict, adapter_status: str | None = None) -> dict:
    merged = {"processed": 0, "verified": 0, "unresolved": 0, "warnings": [], "adapter_status": adapter_status or "real_adapter"}
    for result in results:
        merged["processed"] += result.get("processed", 0)
        merged["verified"] += result.get("verified", 0)
        merged["unresolved"] += result.get("unresolved", 0)
        merged["warnings"].extend(result.get("warnings", []))
    if adapter_status is None:
        statuses = {result.get("adapter_status") for result in results if result.get("adapter_status")}
        if "partial_adapter" in statuses:
            merged["adapter_status"] = "partial_adapter"
        elif "real_adapter" in statuses:
            merged["adapter_status"] = "real_adapter"
        elif "warning_only" in statuses:
            merged["adapter_status"] = "warning_only"
    return merged


def register_missing_source_adapter(ctx: ImportContext, brand: str, reason: str, urls: list[str] | None = None) -> None:
    row = {"brand": brand, "reason": reason, "candidate_source_urls": urls or []}
    if row not in ctx.missing_source_brands:
        ctx.missing_source_brands.append(row)


def risky_short_model_name(model: str) -> bool:
    core = re.sub(r"^(DSC-|DMC-|DC-|EX-|COOLPIX\s+|FinePix\s+|PowerShot\s+)", "", model, flags=re.I)
    core = normalize_model_name(core)
    return bool(re.fullmatch(r"[A-Z]?\d{1,2}[A-Z]?(?:\s.*)?", core, re.I))


def collect_risky_match(ctx: ImportContext, candidate: dict, source_url: str, source_name: str, reason: str) -> None:
    if not risky_short_model_name(candidate["model"]):
        return
    row = {
        "camera_id": candidate["camera_id"],
        "display_name": candidate["display_name"],
        "model": candidate["model"],
        "source_name": source_name,
        "source_url": source_url,
        "reason": reason,
    }
    if row not in ctx.risky_matches:
        ctx.risky_matches.append(row)


def write_import_reports(ctx: ImportContext, before_counts: dict[str, int], importer_results: list[dict]) -> None:
    REPORT_DIR.mkdir(exist_ok=True)
    after_counts = {
        "cameras": len(ctx.cameras),
        "batteries": len(ctx.batteries),
        "compatibility": len(ctx.compatibility),
        "candidates": len(ctx.candidates),
        "unresolved": len(ctx.unresolved),
    }
    summary = {
        "generated": ctx.today,
        "before": before_counts,
        "after": after_counts,
        "processed_brands": sorted(ctx.processed_brands),
        "missing_source_brands": ctx.missing_source_brands,
        "warnings": ctx.warnings,
        "errors": ctx.errors,
        "importer_results": importer_results,
    }
    (REPORT_DIR / "import_all_remaining_report.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Import All Remaining Report",
        "",
        f"Generated: {ctx.today}",
        "",
        "## Counts",
        "",
        "| Metric | Before | After | Delta |",
        "| --- | ---: | ---: | ---: |",
    ]
    for key in ["cameras", "batteries", "compatibility", "candidates", "unresolved"]:
        lines.append(f"| {key} | {before_counts.get(key, 0)} | {after_counts[key]} | {after_counts[key] - before_counts.get(key, 0)} |")
    lines.extend(["", "## Processed Brands", ""])
    for brand in sorted(ctx.processed_brands):
        lines.append(f"- {brand}")
    lines.extend(["", "## Missing Source Adapters", ""])
    if ctx.missing_source_brands:
        for row in ctx.missing_source_brands:
            lines.append(f"- {row['brand']}: {row['reason']}")
    else:
        lines.append("- None")
    lines.extend(["", "## Importer Results", ""])
    for result in importer_results:
        lines.append(
            f"- {result['importer']}: status={result['status']}, "
            f"adapter_status={result.get('adapter_status', 'unknown')}, "
            f"processed={result.get('processed', 0)}, verified={result.get('verified', 0)}, "
            f"unresolved={result.get('unresolved', 0)}"
        )
    if ctx.errors:
        lines.extend(["", "## Errors", ""])
        for error in ctx.errors:
            lines.append(f"- {error}")
    (REPORT_DIR / "import_all_remaining_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def count_by_brand(candidates: list[dict]) -> Counter:
    return Counter(row["brand"] for row in candidates)
