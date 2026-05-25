from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable

from importers.common import (
    ImportContext,
    add_compatibility_source_backed,
    add_or_update_camera_candidate,
    battery_record,
    clean_source_text,
    dedupe_compatibility_for_app_output,
    detect_category,
    fetch_text,
    iter_camera_names,
    make_camera_id,
    normalize_for_match,
)
from validate_and_export import validate


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
REPORT_DIR = ROOT / "reports"
SUGGESTIONS_PATH = DATA_DIR / "battery_suggestions.json"


@dataclass
class Cell:
    text: str
    rowspan: int = 1
    colspan: int = 1


@dataclass
class Pair:
    source_key: str
    source_name: str
    source_url: str
    brand: str
    raw_model: str
    battery_model: str
    battery_brand: str
    status: str = "fully_compatible"
    quantity_required: int | None = 1
    source_type: str = "official_accessory_page"
    confidence: str = "high"
    note: str = ""


@dataclass
class SourceResult:
    source_key: str
    source_name: str
    source_url: str
    brand: str
    extracted_pairs: int = 0
    matched_candidates: set[str] = field(default_factory=set)
    promoted: set[str] = field(default_factory=set)
    already_verified: set[str] = field(default_factory=set)
    new_candidates: set[str] = field(default_factory=set)
    added_compatibility: int = 0
    rejected: list[dict[str, str]] = field(default_factory=list)
    reason: str = ""


SONY_URL = "https://www.sony.jp/support/cyber-shot/accy/battery.html"
OLYMPUS_URL = "https://support.jp.omsystem.com/jp/support/cs/DI/AccM/DI000409J.html"
PANASONIC_URL = "https://help.na.panasonic.com/answers/parts-and-accessories-what-battery-is-compatible-with-my-lumix-camera/"

FUJIFILM_PAGES = [
    ("Fujifilm NP-45S official compatibility", "https://www.fujifilm-x.com/global/products/accessories/np-45s/", "NP-45S"),
    ("Fujifilm NP-50 official compatibility", "https://www.fujifilm-x.com/global/products/accessories/np-50/", "NP-50"),
    ("Fujifilm NP-95 official compatibility", "https://www.fujifilm-x.com/global/products/accessories/np-95/", "NP-95"),
    ("Fujifilm NP-W126S official compatibility", "https://www.fujifilm-x.com/global/products/accessories/np-w126s/", "NP-W126S"),
    ("Fujifilm NP-70 official compatibility", "https://www.fujifilm-x.com/global/products/accessories/np-70/", "NP-70"),
    ("Fujifilm NP-85 official compatibility", "https://www.fujifilm-x.com/global/products/accessories/np-85/", "NP-85"),
    ("Fujifilm NP-120 official compatibility", "https://www.fujifilm-x.com/global/products/accessories/np-120/", "NP-120"),
]

CASIO_PAGES = [
    ("Casio NP-130A official compatibility", "https://www.casio.com/jp/digital-cameras/options/product.NP-130A/", "NP-130A"),
    ("Casio NP-120 official compatibility", "https://www.casio.com/jp/digital-cameras/options/product.NP-120/", "NP-120"),
    ("Casio NP-110 official compatibility", "https://www.casio.com/jp/digital-cameras/options/product.NP-110/", "NP-110"),
    ("Casio NP-90 official compatibility", "https://www.casio.com/jp/digital-cameras/options/product.NP-90/", "NP-90"),
    ("Casio NP-80 official compatibility", "https://www.casio.com/jp/digital-cameras/options/product.NP-80/", "NP-80"),
    ("Casio NP-60 official compatibility", "https://www.casio.com/jp/digital-cameras/options/product.NP-60/", "NP-60"),
    ("Casio NP-40 official compatibility", "https://www.casio.com/jp/digital-cameras/options/product.NP-40/", "NP-40"),
    ("Casio NP-20 official compatibility", "https://www.casio.com/jp/digital-cameras/options/product.NP-20/", "NP-20"),
]


class TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[Cell]]] = []
        self.table_stack: list[list[list[Cell]]] = []
        self.row: list[Cell] | None = None
        self.cell_attrs: dict[str, str] | None = None
        self.cell_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lowered = tag.casefold()
        if lowered == "table":
            self.table_stack.append([])
            return
        if not self.table_stack:
            return
        if lowered == "tr":
            self.row = []
        elif lowered in {"td", "th"} and self.row is not None:
            self.cell_attrs = {key.casefold(): value or "" for key, value in attrs}
            self.cell_parts = []

    def handle_data(self, data: str) -> None:
        if self.cell_attrs is not None:
            self.cell_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.casefold()
        if self.table_stack and lowered in {"td", "th"} and self.row is not None and self.cell_attrs is not None:
            text = re.sub(r"\s+", " ", " ".join(self.cell_parts)).strip()
            self.row.append(
                Cell(
                    text=text,
                    rowspan=max(1, int(self.cell_attrs.get("rowspan", "1") or "1")),
                    colspan=max(1, int(self.cell_attrs.get("colspan", "1") or "1")),
                )
            )
            self.cell_attrs = None
            self.cell_parts = []
        elif self.table_stack and lowered == "tr" and self.row:
            self.table_stack[-1].append(self.row)
            self.row = None
        elif lowered == "table":
            if self.table_stack:
                table = self.table_stack.pop()
                if table:
                    self.tables.append(table)


def load_array(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise ValueError(f"{path.relative_to(ROOT)} must contain an array")
    return value


def state_counts(ctx: ImportContext, suggestions: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "verified_cameras": len(ctx.cameras),
        "unresolved_models": len(ctx.unresolved),
        "compatibility_rows": len(ctx.compatibility),
        "batteries": len(ctx.batteries),
        "candidates": len(ctx.candidates),
        "suggestions": len(suggestions),
    }


def parse_tables(page: str) -> list[list[list[Cell]]]:
    parser = TableParser()
    parser.feed(page)
    return parser.tables


def expand_rowspans(table: list[list[Cell]]) -> list[list[str]]:
    pending: dict[int, tuple[str, int]] = {}
    expanded: list[list[str]] = []
    width = max((sum(cell.colspan for cell in row) for row in table), default=0)
    for row in table:
        output: list[str] = []
        column = 0

        def emit_pending() -> None:
            nonlocal column
            text, remaining = pending[column]
            output.append(text)
            if remaining <= 1:
                del pending[column]
            else:
                pending[column] = (text, remaining - 1)
            column += 1

        for cell in row:
            while column in pending:
                emit_pending()
            for offset in range(cell.colspan):
                output.append(cell.text)
                if cell.rowspan > 1:
                    pending[column + offset] = (cell.text, cell.rowspan - 1)
            column += cell.colspan
        while column < width:
            if column in pending:
                emit_pending()
            else:
                output.append("")
                column += 1
        expanded.append(output)
    return expanded


def compact(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").casefold())


def model_variants(brand: str, raw_model: str) -> list[str]:
    raw = re.sub(r"\s+", " ", raw_model).strip()
    variants = [raw]
    if brand == "Sony":
        variants.extend([f"Sony {raw}", f"Sony Cyber-shot {raw}"])
        if raw.upper().startswith("DSC-"):
            short = raw[4:]
            variants.extend([short, f"Sony {short}", f"Cyber-shot {short}"])
    elif brand == "Olympus":
        base = re.sub(r"(?:\s*Wide\s+Zoom|\s*Ultra\s+Zoom|\s*ZOOM|\s*ZS)$", "", raw, flags=re.I)
        base = re.sub(r"\s*\([^)]*\)\s*$", "", base).strip()
        variants.extend([base, f"Olympus {base}", f"OM SYSTEM {base}"])
        if raw.startswith("μ"):
            variants.extend([f"Olympus {raw}", raw.replace("μ-", "μ ")])
    elif brand == "Panasonic":
        variants.extend([f"Panasonic {raw}", f"Panasonic Lumix {raw}"])
    elif brand == "Fujifilm":
        variants.extend([f"Fujifilm {raw}", f"FUJIFILM {raw}"])
        if not raw.casefold().startswith("finepix") and re.match(r"^(?:XP|F|Z|J|S)\d", raw, re.I):
            variants.append(f"FinePix {raw}")
    elif brand == "Casio":
        variants.extend([f"Casio {raw}", f"Casio Exilim {raw}"])
    return list(dict.fromkeys(variants))


def boundary_contains(container: str, identifier: str) -> bool:
    container_norm = normalize_for_match(container)
    identifier_norm = normalize_for_match(identifier)
    if not identifier_norm:
        return False
    pattern = r"(?<![a-z0-9])" + re.escape(identifier_norm).replace(r"\ ", r"\s+") + r"(?![a-z0-9])"
    return bool(re.search(pattern, container_norm))


def find_candidate(ctx: ImportContext, pair: Pair) -> tuple[dict[str, Any] | None, str]:
    variants = model_variants(pair.brand, pair.raw_model)
    exact = []
    normalized_variants = {normalize_for_match(variant) for variant in variants}
    for candidate in ctx.candidates:
        if candidate["brand"].casefold() != pair.brand.casefold():
            continue
        if normalize_for_match(candidate["model"]) in normalized_variants:
            exact.append(candidate)
    exact_unique = {candidate["camera_id"]: candidate for candidate in exact}
    if len(exact_unique) == 1:
        return next(iter(exact_unique.values())), ""
    if len(exact_unique) > 1:
        return None, "ambiguous exact model match: " + ", ".join(sorted(exact_unique))
    matches: list[dict[str, Any]] = []
    for candidate in ctx.candidates:
        if candidate["brand"].casefold() != pair.brand.casefold():
            continue
        names = iter_camera_names(candidate)
        if any(
            boundary_contains(name, variant) or boundary_contains(variant, name)
            for name in names
            for variant in variants
        ):
            matches.append(candidate)
    unique = {candidate["camera_id"]: candidate for candidate in matches}
    if len(unique) == 1:
        return next(iter(unique.values())), ""
    if len(unique) > 1:
        return None, "ambiguous match: " + ", ".join(sorted(unique))
    return None, "no candidate exact/boundary match"


def source_backed_fixed_lens_family(pair: Pair) -> bool:
    model = pair.raw_model.upper().replace(" ", "")
    if pair.brand == "Sony":
        if re.match(r"DSC-(?:QX|RX0|M)", model):
            return False
        return bool(re.match(r"DSC-(?:F|G|H|HX|L|N|P|R1|RX1|RX10|RX100|T|TX|V|W|WX)", model))
    if pair.brand == "Panasonic":
        return bool(re.match(r"(?:DMC-(?:F(?:H|P|S|X|Z)?|LF|LX|S[123]$|SZ|TS|TZ|XS|ZR|ZS)|DC-(?:LX|TS|TZ|ZS))", model))
    if pair.brand == "Olympus":
        if model.startswith("TG-TRACKER"):
            return False
        return bool(re.match(r"(?:TG-|STYLUS|XZ-|SH-|SZ-|VH-|VR-|VG-|SP-|Μ|FE-)", model))
    if pair.brand == "Fujifilm":
        return bool(re.match(r"(?:FINEPIX|XP\d|JV\d|JX\d|JZ\d|X100|X70$|XF10$|XF1$|X-S1$)", model))
    if pair.brand == "Casio":
        return model.startswith("EX-") and not model.startswith("EX-FR")
    return False


def inferred_series(pair: Pair) -> str:
    model = pair.raw_model.upper()
    if pair.brand == "Sony":
        match = re.match(r"DSC-([A-Z]+)", model)
        return f"Cyber-shot DSC-{match.group(1) if match else 'compact'}"
    if pair.brand == "Panasonic":
        match = re.match(r"(?:DMC|DC)-([A-Z]+)", model)
        return f"Lumix {match.group(1) if match else 'compact'}"
    if pair.brand == "Olympus":
        match = re.match(r"([A-Zμ]+)", pair.raw_model, re.I)
        return match.group(1) if match else "compact"
    if pair.brand == "Fujifilm":
        return "FinePix" if "FINEPIX" in model or re.match(r"XP\d", model) else "X compact"
    if pair.brand == "Casio":
        return "Exilim"
    return "compact"


def build_official_candidate(pair: Pair) -> dict[str, Any]:
    if pair.brand == "Sony":
        display_name = f"Sony Cyber-shot {pair.raw_model}"
    elif pair.brand == "Panasonic":
        display_name = f"Panasonic Lumix {pair.raw_model}"
    elif pair.brand == "Olympus":
        display_name = f"Olympus {pair.raw_model}"
    elif pair.brand == "Fujifilm":
        display_name = f"Fujifilm {pair.raw_model}"
    elif pair.brand == "Casio":
        display_name = f"Casio Exilim {pair.raw_model}"
    else:
        display_name = f"{pair.brand} {pair.raw_model}"
    series = inferred_series(pair)
    aliases = model_variants(pair.brand, pair.raw_model)
    if pair.brand == "Sony":
        aliases = [alias for alias in aliases if not re.fullmatch(r"[A-Z]+\d+[A-Z]?", alias, flags=re.I)]
    return {
        "camera_id": make_camera_id(pair.brand, display_name),
        "brand": pair.brand,
        "series": series,
        "model": pair.raw_model,
        "display_name": display_name,
        "aliases": aliases,
        "regional_names": {},
        "release_year": None,
        "category": detect_category(pair.brand, series, pair.raw_model, display_name),
        "lens_type": "fixed_lens",
        "battery_system": "unknown",
        "notes": "Added from an official manufacturer battery compatibility table for a recognized fixed-lens compact family; release year remains unverified.",
        "candidate_source_name": pair.source_name,
        "candidate_source_url": pair.source_url,
        "candidate_source_type": pair.source_type,
        "candidate_batch": "phase9_official_bulk_compatibility",
        "candidate_status": "verified_battery",
    }


def clean_phase9_generated_short_aliases(ctx: ImportContext) -> None:
    unsafe_short = re.compile(r"^[A-Z]+\d+[A-Z]?$", flags=re.I)
    phase9_ids = {
        candidate["camera_id"]
        for candidate in ctx.candidates
        if candidate.get("candidate_batch") == "phase9_official_bulk_compatibility" and candidate["brand"] == "Sony"
    }
    for collection in (ctx.candidates, ctx.cameras):
        for row in collection:
            if row["camera_id"] in phase9_ids:
                row["aliases"] = [alias for alias in row["aliases"] if not unsafe_short.fullmatch(alias)]


def normalize_battery(value: str) -> str | None:
    value = value.strip().upper()
    value = re.sub(r"[（(]\s*\*\d+\s*[）)]", "", value).strip()
    if value in {"NH-AA", "AA", "単3"}:
        return "AA"
    match = re.search(
        r"\b(?:NP-[A-Z0-9/]+|DMW-[A-Z0-9]+|CGA-?[A-Z0-9]+|LI-\d+[A-Z]?|BLS-\d+|BLM-\d+|EN-EL\d+[A-Z]?|KLIC-\d+)\b",
        value,
    )
    return match.group(0) if match else None


def sony_pairs(page: str) -> list[Pair]:
    output: list[Pair] = []
    for table in parse_tables(page):
        rows = expand_rowspans(table)
        if not rows:
            continue
        header_index = next((index for index, row in enumerate(rows) if any("機種名" in cell for cell in row)), None)
        if header_index is None:
            continue
        headers = [normalize_battery(cell) for cell in rows[header_index]]
        for row in rows[header_index + 1 :]:
            if not row or not re.fullmatch(r"DSC-[A-Z0-9-]+", row[0].strip(), re.I):
                continue
            model = row[0].strip()
            for index, cell in enumerate(row[1:], start=1):
                if index >= len(headers) or not headers[index] or "○" not in cell:
                    continue
                battery = headers[index]
                status = "uses_aa" if battery == "AA" else "fully_compatible"
                output.append(
                    Pair(
                        source_key="sony_table",
                        source_name="Sony Cyber-shot official battery compatibility table",
                        source_url=SONY_URL,
                        brand="Sony",
                        raw_model=model,
                        battery_model=battery,
                        battery_brand="Generic" if battery == "AA" else "Sony",
                        status=status,
                        quantity_required=None if battery == "AA" else 1,
                        note=f"Sony official battery compatibility table lists {model} with compatible battery {battery}; AA quantity is not stated." if battery == "AA" else f"Sony official battery compatibility table lists {model} with compatible battery {battery}.",
                    )
                )
    return output


def olympus_pairs(page: str) -> list[Pair]:
    output: list[Pair] = []
    model_pattern = re.compile(r"^(?:TG-|STYLUS|XZ-|SH-|SZ-|VH-|VR-|VG-|SP-|μ|FE-|X-|C-|D-|AZ-|IR-)", re.I)
    battery_pattern = re.compile(r"\b(?:LI-\d+[A-Z]?|BLS-\d+|BLM-\d+)\b", re.I)
    for table in parse_tables(page):
        rows = expand_rowspans(table)
        table_text = " ".join(cell for row in rows for cell in row)
        has_aa_columns = "単3" in table_text
        for row in rows:
            if not row:
                continue
            model = row[0].strip()
            if not model_pattern.search(model):
                continue
            battery_models = list(dict.fromkeys(match.group(0).upper() for match in battery_pattern.finditer(" ".join(row[1:]))))
            for battery in battery_models:
                output.append(
                    Pair(
                        source_key="olympus_table",
                        source_name="OM SYSTEM compact camera official battery compatibility table",
                        source_url=OLYMPUS_URL,
                        brand="Olympus",
                        raw_model=model,
                        battery_model=battery,
                        battery_brand="Olympus",
                        note=f"OM SYSTEM official compact camera battery table lists {model} with compatible battery {battery}.",
                    )
                )
            if has_aa_columns and not battery_models and "○" in " ".join(row[1:]):
                output.append(
                    Pair(
                        source_key="olympus_table",
                        source_name="OM SYSTEM compact camera official battery compatibility table",
                        source_url=OLYMPUS_URL,
                        brand="Olympus",
                        raw_model=model,
                        battery_model="AA",
                        battery_brand="Generic",
                        status="uses_aa",
                        quantity_required=None,
                        note=f"OM SYSTEM official compact camera battery table lists AA battery support for {model}; quantity is not stated in the extracted row.",
                    )
                )
    return output


def panasonic_pairs(page: str) -> list[Pair]:
    sections = re.findall(r"<section\b([^>]*)>(.*?)</section>", page, flags=re.I | re.S)
    key_battery: dict[str, str] = {}
    parsed: list[tuple[str, str]] = []
    for attrs, body in sections:
        key_match = re.search(r'data-key="([^"]+)"', body, flags=re.I)
        heading_match = re.search(r"<h3\b[^>]*>(.*?)</h3>", body, flags=re.I | re.S)
        if not key_match or not heading_match:
            continue
        key = key_match.group(1).casefold()
        heading = clean_source_text(heading_match.group(1))
        text = clean_source_text(body)
        battery_match = re.search(r"part number\s+([A-Z0-9-]+)", text, flags=re.I)
        if battery_match:
            key_battery[key] = battery_match.group(1).upper()
        parsed.append((heading, key))
    output: list[Pair] = []
    for heading, key in parsed:
        battery = key_battery.get(key)
        if not battery:
            continue
        for model in [item.strip() for item in heading.split(",") if item.strip()]:
            if not re.fullmatch(r"(?:DMC|DC)-[A-Z0-9-]+", model, flags=re.I):
                continue
            output.append(
                Pair(
                    source_key="panasonic_table",
                    source_name="Panasonic official LUMIX battery compatibility page",
                    source_url=PANASONIC_URL,
                    brand="Panasonic",
                    raw_model=model,
                    battery_model=battery,
                    battery_brand="Panasonic",
                    note=f"Panasonic official LUMIX battery compatibility page identifies {battery} as the battery part number for {model}.",
                )
            )
    return output


def fujifilm_pairs(page: str, source_name: str, source_url: str, battery: str) -> list[Pair]:
    compatibility = re.search(
        r"<(?:h[1-6]|p)\b[^>]*>\s*(?:<[^>]+>\s*)*Compatibility\s*(?:</[^>]+>\s*)*</(?:h[1-6]|p)>(.*?)(?:Related Products|</main>)",
        page,
        flags=re.I | re.S,
    )
    if not compatibility:
        return []
    model_texts = re.findall(r"<a\b[^>]*>(.*?)</a>", compatibility.group(1), flags=re.I | re.S)
    output: list[Pair] = []
    for text in model_texts:
        cleaned = clean_source_text(text)
        if not cleaned or "battery" in cleaned.casefold():
            continue
        for model in [item.strip() for item in cleaned.split("/") if item.strip()]:
            if not re.search(r"(?:FinePix|FUJIFILM|X100|XF10|X70|XP\d|F\d|Z\d|J[A-Z]?\d|S\d)", model, flags=re.I):
                continue
            output.append(
                Pair(
                    source_key=f"fujifilm_{compact(battery)}",
                    source_name=source_name,
                    source_url=source_url,
                    brand="Fujifilm",
                    raw_model=model,
                    battery_model=battery,
                    battery_brand="Fujifilm",
                    note=f"FUJIFILM official {battery} compatibility page lists {model} as compatible.",
                )
            )
    return output


def casio_pairs(page: str, source_name: str, source_url: str, battery: str) -> list[Pair]:
    text = clean_source_text(page)
    match = re.search(r"対応機種\s+(.+?)(?:基本情報|レビュー|価格|$)", text, flags=re.S)
    if not match:
        return []
    output: list[Pair] = []
    for model in re.findall(r"\bEX-[A-Z0-9-]+\b", match.group(1), flags=re.I):
        output.append(
            Pair(
                source_key=f"casio_{compact(battery)}",
                source_name=source_name,
                source_url=source_url,
                brand="Casio",
                raw_model=model.upper(),
                battery_model=battery,
                battery_brand="Casio",
                note=f"CASIO official battery option page lists {model.upper()} as compatible with lithium-ion battery {battery}.",
            )
        )
    return output


def dedupe_pairs(pairs: list[Pair]) -> list[Pair]:
    output: list[Pair] = []
    seen: set[tuple[str, str, str, str]] = set()
    for pair in pairs:
        key = (pair.source_url, normalize_for_match(pair.raw_model), compact(pair.battery_model), pair.status)
        if key not in seen:
            output.append(pair)
            seen.add(key)
    return output


def retrieve_pairs() -> tuple[list[Pair], dict[str, SourceResult]]:
    source_results: dict[str, SourceResult] = {}
    all_pairs: list[Pair] = []

    def retrieve(
        key: str,
        name: str,
        url: str,
        brand: str,
        extractor: Callable[[str], list[Pair]],
    ) -> None:
        result = SourceResult(key, name, url, brand)
        source_results[key] = result
        try:
            pairs = dedupe_pairs(extractor(fetch_text(url, timeout=45)))
            result.extracted_pairs = len(pairs)
            all_pairs.extend(pairs)
            if not pairs:
                result.reason = "Page fetched, but no explicit camera-battery pairs were parsed."
        except Exception as exc:
            result.reason = f"Source fetch/parse failed: {type(exc).__name__}: {exc}"

    retrieve("sony_table", "Sony Cyber-shot official battery compatibility table", SONY_URL, "Sony", sony_pairs)
    retrieve("olympus_table", "OM SYSTEM compact camera official battery compatibility table", OLYMPUS_URL, "Olympus", olympus_pairs)
    retrieve("panasonic_table", "Panasonic official LUMIX battery compatibility page", PANASONIC_URL, "Panasonic", panasonic_pairs)
    for source_name, source_url, battery in FUJIFILM_PAGES:
        key = f"fujifilm_{compact(battery)}"
        retrieve(key, source_name, source_url, "Fujifilm", lambda page, n=source_name, u=source_url, b=battery: fujifilm_pairs(page, n, u, b))
    for source_name, source_url, battery in CASIO_PAGES:
        key = f"casio_{compact(battery)}"
        retrieve(key, source_name, source_url, "Casio", lambda page, n=source_name, u=source_url, b=battery: casio_pairs(page, n, u, b))
    source_results["nikon_manual"] = SourceResult(
        "nikon_manual",
        "Nikon official manuals/accessory pages",
        "",
        "Nikon",
        reason="No official bulk compatibility table was confirmed in this pass; remaining exact-model checks are routed to the bounded LLM-assisted step.",
    )
    source_results["samsung_manual"] = SourceResult(
        "samsung_manual",
        "Samsung official/manual sources",
        "",
        "Samsung",
        reason="No official bulk compatibility table was confirmed in this pass; remaining exact-model checks are routed to the bounded LLM-assisted step.",
    )
    source_results["kodak_manual"] = SourceResult(
        "kodak_manual",
        "Kodak official/manual sources",
        "",
        "Kodak",
        reason="No official bulk compatibility table was confirmed in this pass; remaining exact-model checks are routed to the bounded LLM-assisted step.",
    )
    return dedupe_pairs(all_pairs), source_results


def existing_row_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (row["camera_id"], row["battery_id"], row["status"], row["source_url"])


def process_pairs(ctx: ImportContext, pairs: list[Pair], results: dict[str, SourceResult], apply: bool) -> list[dict[str, str]]:
    initially_verified = {row["camera_id"] for row in ctx.cameras}
    planned_verified = set(initially_verified)
    existing_keys = {existing_row_key(row) for row in ctx.compatibility}
    actions: list[dict[str, str]] = []
    for pair in pairs:
        result = results[pair.source_key]
        candidate, reason = find_candidate(ctx, pair)
        if not candidate:
            if reason == "no candidate exact/boundary match" and source_backed_fixed_lens_family(pair):
                candidate = build_official_candidate(pair)
                result.new_candidates.add(candidate["camera_id"])
                if apply:
                    candidate = add_or_update_camera_candidate(ctx, candidate)
            else:
                if reason == "no candidate exact/boundary match":
                    reason = "no candidate match; model is outside the recognized fixed-lens bulk allowlist or requires manual scope review"
                rejection = {"model": pair.raw_model, "battery": pair.battery_model, "reason": reason}
                result.rejected.append(rejection)
                actions.append({"source": pair.source_name, **rejection, "action": "rejected"})
                continue
        if not candidate:
            rejection = {"model": pair.raw_model, "battery": pair.battery_model, "reason": reason}
            result.rejected.append(rejection)
            actions.append({"source": pair.source_name, **rejection, "action": "rejected"})
            continue
        result.matched_candidates.add(candidate["camera_id"])
        battery = battery_record(pair.battery_brand, pair.battery_model, "Added from an official bulk compatibility extraction.")
        key = (candidate["camera_id"], battery["battery_id"], pair.status, pair.source_url)
        if key in existing_keys:
            result.already_verified.add(candidate["camera_id"])
            actions.append({"source": pair.source_name, "model": pair.raw_model, "battery": pair.battery_model, "reason": "Exact source-backed mapping already exists.", "action": "already_verified"})
            continue
        if candidate["camera_id"] not in initially_verified:
            result.promoted.add(candidate["camera_id"])
            action = "promote_verified"
        else:
            result.already_verified.add(candidate["camera_id"])
            action = "add_official_confirmation"
        result.added_compatibility += 1
        actions.append({"source": pair.source_name, "model": pair.raw_model, "battery": pair.battery_model, "reason": pair.note, "action": action})
        existing_keys.add(key)
        planned_verified.add(candidate["camera_id"])
        if apply:
            add_compatibility_source_backed(
                ctx,
                candidate,
                battery,
                pair.status,
                pair.quantity_required,
                pair.note,
                pair.source_name,
                pair.source_url,
                pair.source_type,
                pair.confidence,
                pair.brand,
            )
    return actions


def markdown(value: Any) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")


def write_review_report(results: dict[str, SourceResult], mode: str) -> None:
    lines = [
        "# Bulk Official Extraction Review",
        "",
        f"Mode: {mode}",
        "",
        "| Source | Extracted pairs | Matched candidates | Promoted | Already verified | New candidates | Rejected | Reason |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for result in results.values():
        lines.append(
            f"| {markdown(result.source_name)} | {result.extracted_pairs} | {len(result.matched_candidates)} | "
            f"{len(result.promoted)} | {len(result.already_verified)} | {len(result.new_candidates)} | "
            f"{len(result.rejected)} | {markdown(result.reason)} |"
        )
    (REPORT_DIR / "bulk_official_extraction_review.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_rejected_report(results: dict[str, SourceResult]) -> None:
    lines = [
        "# Bulk Official Extraction Rejected",
        "",
        "| Source | Raw model | Proposed battery | Reason |",
        "| --- | --- | --- | --- |",
    ]
    for result in results.values():
        if result.reason and not result.extracted_pairs:
            lines.append(f"| {markdown(result.source_name)} |  |  | {markdown(result.reason)} |")
        for row in result.rejected:
            lines.append(f"| {markdown(result.source_name)} | {markdown(row['model'])} | {markdown(row['battery'])} | {markdown(row['reason'])} |")
    (REPORT_DIR / "bulk_official_extraction_rejected.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


POPULAR_TERMS = re.compile(
    r"(?:DSC-(?:HX|WX|W|T|TX)|COOLPIX (?:P|S|L|AW|W)|FinePix (?:F|Z|XP|S|HS)|"
    r"(?:DMC|DC)-(?:TZ|ZS|LX|FZ|FX|FS|FT|TS)|(?:TG-|XZ-|FE-|SP-|STYLUS|μ)|"
    r"(?:WB|ST|PL|DV)|EX-(?:ZR|H|FC|TR)|EasyShare (?:C|M|Z))",
    re.I,
)


def top_remaining(ctx: ImportContext, count: int = 50) -> list[dict[str, Any]]:
    brand_score = {"Sony": 95, "Nikon": 90, "Fujifilm": 88, "Panasonic": 86, "Olympus": 84, "Samsung": 82, "Casio": 80, "Kodak": 72}

    def score(row: dict[str, Any]) -> tuple[int, str, str]:
        popularity = 60 if POPULAR_TERMS.search(row["display_name"]) else 0
        return (-(brand_score.get(row["brand"], 0) + popularity), row["brand"], row["display_name"])

    return sorted(ctx.unresolved, key=score)[:count]


def write_final_reports(
    before: dict[str, int],
    after: dict[str, int],
    results: dict[str, SourceResult],
    ctx: ImportContext,
    mode: str,
) -> None:
    by_brand = Counter()
    by_source = Counter()
    rejected = 0
    for result in results.values():
        by_brand[result.brand] += len(result.promoted)
        by_source[result.source_name] += len(result.promoted)
        rejected += len(result.rejected)
    lines = [
        "# Phase 9 Bulk Official Extraction Summary",
        "",
        f"Mode: {mode}",
        "",
        "## Coverage Delta",
        "",
        "| Metric | Before | After | Delta |",
        "| --- | ---: | ---: | ---: |",
    ]
    for field in ["verified_cameras", "unresolved_models", "compatibility_rows", "batteries", "candidates", "suggestions"]:
        lines.append(f"| {field} | {before[field]} | {after[field]} | {after[field] - before[field]} |")
    lines.extend(["", "## Promoted By Source", "", "| Source | Brand | Verified cameras promoted |", "| --- | --- | ---: |"])
    for result in results.values():
        lines.append(f"| {markdown(result.source_name)} | {result.brand} | {len(result.promoted)} |")
    lines.extend(["", "## Promoted By Brand", "", "| Brand | Verified cameras promoted |", "| --- | ---: |"])
    for brand, total in sorted(by_brand.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"| {brand} | {total} |")
    lines.extend(["", f"- Extracted pairs: {sum(result.extracted_pairs for result in results.values())}", f"- Rejected or unmatched pairs: {rejected}", "", "## Fifty Popular Models Still Unresolved", "", "| Camera | Brand | Reason |", "| --- | --- | --- |"])
    for row in top_remaining(ctx):
        lines.append(f"| {markdown(row['display_name'])} | {row['brand']} | {markdown(row['reason'])} |")
    (REPORT_DIR / "phase9_bulk_extraction_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    remaining_lines = ["# Top Remaining Unresolved Popular Models", "", "| Camera | Brand | Series | Reason |", "| --- | --- | --- | --- |"]
    for row in top_remaining(ctx):
        remaining_lines.append(f"| {markdown(row['display_name'])} | {row['brand']} | {markdown(row['series'])} | {markdown(row['reason'])} |")
    (REPORT_DIR / "top_remaining_unresolved_popular.md").write_text("\n".join(remaining_lines) + "\n", encoding="utf-8")
    quality_lines = ["# Source Quality By Brand", "", "All compatibility rows generated by Phase 9 bulk extraction are official manufacturer compatibility rows with `high` confidence.", "", "| Brand | Official extracted pairs | Promoted cameras | Added compatibility rows | Rejected pairs |", "| --- | ---: | ---: | ---: | ---: |"]
    grouped = defaultdict(lambda: {"extracted": 0, "promoted": 0, "added": 0, "rejected": 0})
    for result in results.values():
        values = grouped[result.brand]
        values["extracted"] += result.extracted_pairs
        values["promoted"] += len(result.promoted)
        values["added"] += result.added_compatibility
        values["rejected"] += len(result.rejected)
    for brand, values in sorted(grouped.items(), key=lambda item: (-item[1]["promoted"], item[0])):
        quality_lines.append(f"| {brand} | {values['extracted']} | {values['promoted']} | {values['added']} | {values['rejected']} |")
    (REPORT_DIR / "source_quality_by_brand.md").write_text("\n".join(quality_lines) + "\n", encoding="utf-8")


def execute(apply: bool) -> tuple[dict[str, int], dict[str, int], dict[str, SourceResult]]:
    ctx = ImportContext.load(ROOT)
    suggestions = load_array(SUGGESTIONS_PATH)
    before = state_counts(ctx, suggestions)
    pairs, results = retrieve_pairs()
    process_pairs(ctx, pairs, results, apply)
    if apply:
        clean_phase9_generated_short_aliases(ctx)
        dedupe_compatibility_for_app_output(ctx)
        validate(ctx.cameras, ctx.batteries, ctx.compatibility, ctx.candidates, ctx.sources, ctx.unresolved, suggestions)
        ctx.write_all()
    after = state_counts(ctx, suggestions)
    REPORT_DIR.mkdir(exist_ok=True)
    mode = "apply" if apply else "dry-run"
    write_review_report(results, mode)
    write_rejected_report(results)
    write_final_reports(before, after, results, ctx, mode)
    return before, after, results


def main() -> None:
    parser = argparse.ArgumentParser(description="Bulk extract exact compact-camera battery compatibility from official manufacturer tables.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Extract and review pairs without writing JSON.")
    mode.add_argument("--apply", action="store_true", help="Apply source-backed exact matches to database JSON.")
    args = parser.parse_args()
    before, after, results = execute(bool(args.apply))
    print(f"Mode: {'apply' if args.apply else 'dry-run'}")
    for key in before:
        print(f"{key}: {before[key]} -> {after[key]}")
    print(f"Extracted pairs: {sum(result.extracted_pairs for result in results.values())}")
    print(f"Promoted verified cameras: {sum(len(result.promoted) for result in results.values())}")
    print(f"Rejected/unmatched pairs: {sum(len(result.rejected) for result in results.values())}")
    print("Reports: reports/bulk_official_extraction_review.md, reports/bulk_official_extraction_rejected.md, reports/phase9_bulk_extraction_summary.md")


if __name__ == "__main__":
    main()
