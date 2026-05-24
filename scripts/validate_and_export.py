from __future__ import annotations

import csv
import json
import random
import re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
EXPORT_DIR = ROOT / "exports"
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

CAMERA_CATEGORIES = {
    "point_and_shoot",
    "premium_compact",
    "travel_zoom",
    "waterproof_compact",
    "bridge_superzoom",
    "large_sensor_compact",
    "3d_compact",
    "unknown",
}

BATTERY_SYSTEMS = {
    "proprietary_li_ion",
    "aa",
    "aaa",
    "built_in",
    "special",
    "unknown",
}

STATUSES = {
    "fully_compatible",
    "partially_compatible",
    "uses_aa",
    "uses_aaa",
    "built_in_battery",
    "unknown",
}

SOURCE_TYPES = {
    "official_manual",
    "official_accessory_page",
    "trusted_database",
    "manual_mirror",
    "retailer",
    "third_party_chart",
    "unknown",
}

CONFIDENCE = {"high", "medium", "low"}
CANDIDATE_STATUSES = {"verified_battery", "unresolved"}


def load_json(name: str) -> list[dict]:
    path = DATA_DIR / name
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"{path} must contain a JSON array")
    return data


def load_optional_json(name: str) -> list[dict]:
    path = DATA_DIR / name
    if not path.exists():
        return []
    return load_json(name)


def require_fields(rows: list[dict], fields: list[str], label: str) -> None:
    for index, row in enumerate(rows, start=1):
        missing = [field for field in fields if field not in row]
        extra = [field for field in row if field not in fields]
        if missing:
            raise ValueError(f"{label} row {index} missing fields: {missing}")
        if extra:
            raise ValueError(f"{label} row {index} has unexpected fields: {extra}")


def check_unique(rows: list[dict], key: str, label: str) -> None:
    counts = Counter(row[key] for row in rows)
    duplicates = sorted(item for item, count in counts.items() if count > 1)
    if duplicates:
        raise ValueError(f"Duplicate {label} IDs: {duplicates}")


def valid_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def validate_camera_row(camera: dict) -> None:
    if camera["lens_type"] != "fixed_lens":
        raise ValueError(f"{camera['camera_id']} is not fixed_lens")
    if camera["category"] not in CAMERA_CATEGORIES:
        raise ValueError(f"{camera['camera_id']} has invalid category")
    if camera["battery_system"] not in BATTERY_SYSTEMS:
        raise ValueError(f"{camera['camera_id']} has invalid battery_system")
    year = camera["release_year"]
    if year is not None and not (1998 <= year <= 2026):
        raise ValueError(f"{camera['camera_id']} release_year outside 1998-2026")
    if not isinstance(camera["aliases"], list):
        raise ValueError(f"{camera['camera_id']} aliases must be a list")
    if not isinstance(camera["regional_names"], dict):
        raise ValueError(f"{camera['camera_id']} regional_names must be an object")


def validate(
    cameras: list[dict],
    batteries: list[dict],
    compat: list[dict],
    candidates: list[dict] | None = None,
    sources: list[dict] | None = None,
    unresolved: list[dict] | None = None,
) -> None:
    candidates = candidates or []
    sources = sources or []
    unresolved = unresolved or []

    require_fields(cameras, CAMERA_FIELDS, "camera")
    require_fields(batteries, BATTERY_FIELDS, "battery")
    require_fields(compat, COMPAT_FIELDS, "compatibility")
    if candidates:
        require_fields(candidates, CANDIDATE_FIELDS, "camera candidate")
    if sources:
        require_fields(sources, SOURCE_FIELDS, "source")
    if unresolved:
        require_fields(unresolved, UNRESOLVED_FIELDS, "unresolved model")

    check_unique(cameras, "camera_id", "camera")
    check_unique(batteries, "battery_id", "battery")
    if candidates:
        check_unique(candidates, "camera_id", "camera candidate")
    if sources:
        check_unique(sources, "source_id", "source")

    camera_ids = {row["camera_id"] for row in cameras}
    battery_ids = {row["battery_id"] for row in batteries}

    for camera in cameras:
        validate_camera_row(camera)

    for battery in batteries:
        if not isinstance(battery["aliases"], list):
            raise ValueError(f"{battery['battery_id']} aliases must be a list")
        if battery["voltage"] is not None and battery["voltage"] <= 0:
            raise ValueError(f"{battery['battery_id']} voltage must be positive")
        if battery["capacity_mah"] is not None and battery["capacity_mah"] <= 0:
            raise ValueError(f"{battery['battery_id']} capacity_mah must be positive")

    for index, row in enumerate(compat, start=1):
        camera_id = row["camera_id"]
        battery_id = row["battery_id"]
        status = row["status"]

        if camera_id not in camera_ids:
            raise ValueError(f"compat row {index} references unknown camera {camera_id}")
        if battery_id is not None and battery_id not in battery_ids:
            raise ValueError(f"compat row {index} references unknown battery {battery_id}")
        if status not in STATUSES:
            raise ValueError(f"compat row {index} has invalid status {status}")
        if row["source_type"] not in SOURCE_TYPES:
            raise ValueError(f"compat row {index} has invalid source_type")
        if row["confidence"] not in CONFIDENCE:
            raise ValueError(f"compat row {index} has invalid confidence")
        if not row["source_name"].strip():
            raise ValueError(f"compat row {index} missing source_name")
        if not valid_url(row["source_url"]):
            raise ValueError(f"compat row {index} has invalid source_url")
        date.fromisoformat(row["last_verified"])
        if row["quantity_required"] is not None:
            if not isinstance(row["quantity_required"], int) or row["quantity_required"] <= 0:
                raise ValueError(f"compat row {index} has invalid quantity_required")

        if status == "unknown":
            if battery_id is not None or row["quantity_required"] is not None:
                raise ValueError(f"unknown row {index} must not set battery or quantity")
            if row["confidence"] != "low":
                raise ValueError(f"unknown row {index} must use low confidence")
        else:
            if battery_id is None:
                raise ValueError(f"compat row {index} must set battery_id")

        if status == "uses_aa" and battery_id != "generic_aa":
            raise ValueError(f"uses_aa row {index} must use generic_aa")
        if status == "uses_aaa" and battery_id != "generic_aaa":
            raise ValueError(f"uses_aaa row {index} must use generic_aaa")

    verified_compat_camera_ids = {
        row["camera_id"]
        for row in compat
        if row["status"] != "unknown"
    }
    candidate_ids = {row["camera_id"] for row in candidates}
    unresolved_ids = {row["camera_id"] for row in unresolved}

    for index, source in enumerate(sources, start=1):
        if source["source_type"] not in SOURCE_TYPES:
            raise ValueError(f"source row {index} has invalid source_type")
        if not source["source_name"].strip():
            raise ValueError(f"source row {index} missing source_name")
        if not valid_url(source["source_url"]):
            raise ValueError(f"source row {index} has invalid source_url")
        date.fromisoformat(source["last_verified"])

    for index, candidate in enumerate(candidates, start=1):
        validate_camera_row(candidate)
        if candidate["candidate_status"] not in CANDIDATE_STATUSES:
            raise ValueError(f"candidate row {index} has invalid candidate_status")
        if candidate["candidate_source_type"] not in SOURCE_TYPES:
            raise ValueError(f"candidate row {index} has invalid candidate_source_type")
        if not candidate["candidate_source_name"].strip():
            raise ValueError(f"candidate row {index} missing candidate_source_name")
        if not valid_url(candidate["candidate_source_url"]):
            raise ValueError(f"candidate row {index} has invalid candidate_source_url")
        if candidate["candidate_status"] == "verified_battery" and candidate["camera_id"] not in verified_compat_camera_ids:
            raise ValueError(f"{candidate['camera_id']} is marked verified_battery without verified compatibility")
        if candidate["candidate_status"] == "unresolved" and candidate["camera_id"] not in unresolved_ids:
            raise ValueError(f"{candidate['camera_id']} is marked unresolved but missing unresolved record")

    if candidate_ids and unresolved_ids - candidate_ids:
        raise ValueError(f"Unresolved rows not present in candidates: {sorted(unresolved_ids - candidate_ids)}")

    for index, row in enumerate(unresolved, start=1):
        if not row["reason"].strip():
            raise ValueError(f"unresolved row {index} missing reason")
        if not valid_url(row["candidate_source_url"]):
            raise ValueError(f"unresolved row {index} has invalid candidate_source_url")
        if not isinstance(row["checked_source_urls"], list):
            raise ValueError(f"unresolved row {index} checked_source_urls must be a list")
        invalid_urls = [url for url in row["checked_source_urls"] if not valid_url(url)]
        if invalid_urls:
            raise ValueError(f"unresolved row {index} has invalid checked_source_urls: {invalid_urls}")
        date.fromisoformat(row["last_checked"])
        if row["camera_id"] in verified_compat_camera_ids:
            raise ValueError(f"{row['camera_id']} is unresolved but has verified compatibility")

    mapped_camera_ids = {row["camera_id"] for row in compat}
    missing_compat = sorted(camera_ids - mapped_camera_ids)
    if missing_compat:
        raise ValueError(f"Cameras without any compatibility row: {missing_compat}")


def csv_value(value) -> str:
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    if value is None:
        return ""
    return str(value)


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row[field]) for field in fields})


def write_report(cameras: list[dict], compat: list[dict]) -> None:
    camera_by_id = {camera["camera_id"]: camera for camera in cameras}
    brands = Counter(camera["brand"] for camera in cameras)
    high_camera_ids = {
        row["camera_id"]
        for row in compat
        if row["confidence"] == "high" and row["status"] != "unknown"
    }
    unknown_rows = [row for row in compat if row["status"] == "unknown"]
    alias_camera_ids = {
        camera["camera_id"]
        for camera in cameras
        if camera["aliases"] or any(camera["regional_names"].values())
    }

    confidence_by_brand = defaultdict(lambda: Counter())
    for row in compat:
        brand = camera_by_id[row["camera_id"]]["brand"]
        confidence_by_brand[brand][row["confidence"]] += 1

    manual_check = []
    for row in compat:
        if row["status"] == "unknown" or row["confidence"] in {"low", "medium"}:
            camera = camera_by_id[row["camera_id"]]
            manual_check.append(
                (
                    camera["brand"],
                    camera["display_name"],
                    row["status"],
                    row["confidence"],
                    row["source_url"],
                )
            )

    lines = [
        "# Coverage Report",
        "",
        f"Generated: {date.today().isoformat()}",
        "",
        "## Summary",
        "",
        f"- Cameras: {len(cameras)}",
        f"- Compatibility rows: {len(compat)}",
        f"- Cameras with at least one high-confidence verified battery row: {len(high_camera_ids)}",
        f"- Cameras with unknown battery mapping rows: {len({row['camera_id'] for row in unknown_rows})}",
        f"- Cameras with aliases or regional names: {len(alias_camera_ids)}",
        "",
        "## Cameras By Brand",
        "",
        "| Brand | Cameras | High rows | Medium rows | Low rows |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]

    for brand, count in sorted(brands.items()):
        confidence = confidence_by_brand[brand]
        lines.append(
            f"| {brand} | {count} | {confidence['high']} | {confidence['medium']} | {confidence['low']} |"
        )

    lines.extend(
        [
            "",
            "## Manual Check List",
            "",
            "| Brand | Camera | Status | Confidence | Source |",
            "| --- | --- | --- | --- | --- |",
        ]
    )

    for brand, display_name, status, confidence, source_url in sorted(manual_check):
        lines.append(f"| {brand} | {display_name} | {status} | {confidence} | {source_url} |")

    (REPORT_DIR / "coverage.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def has_regional_alias(camera: dict) -> bool:
    regional_names = {
        name
        for names in camera["regional_names"].values()
        for name in names
    }
    return bool(camera["aliases"]) or any(name != camera["display_name"] for name in regional_names)


def markdown_cell(value) -> str:
    return str(value).replace("|", "\\|")


def normalize_name(value: str) -> str:
    value = value.casefold()
    value = re.sub(r"^canon\s+", "", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def iter_names(camera: dict):
    yield "display_name", camera["display_name"]
    for alias in camera["aliases"]:
        yield "aliases", alias
    for region, names in camera["regional_names"].items():
        for name in names:
            yield f"regional_names.{region}", name


def write_duplicate_alias_report(cameras: list[dict], candidates: list[dict]) -> None:
    records = candidates or cameras
    by_name: dict[str, list[dict]] = defaultdict(list)
    for camera in records:
        seen_for_camera = set()
        for field, name in iter_names(camera):
            normalized = normalize_name(name)
            if not normalized:
                continue
            key = (camera["camera_id"], normalized)
            if key in seen_for_camera:
                continue
            seen_for_camera.add(key)
            by_name[normalized].append(
                {
                    "camera_id": camera["camera_id"],
                    "display_name": camera["display_name"],
                    "series": camera["series"],
                    "field": field,
                    "name": name,
                }
            )

    duplicates = []
    for normalized, rows in sorted(by_name.items()):
        camera_ids = sorted({row["camera_id"] for row in rows})
        if len(camera_ids) <= 1:
            continue
        duplicates.append(
            {
                "normalized_name": normalized,
                "camera_ids": camera_ids,
                "name_variants": sorted({row["name"] for row in rows}),
                "records": rows,
            }
        )

    path = REPORT_DIR / "duplicate_alias_report.json"
    path.write_text(json.dumps(duplicates, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_duplicate_compatibility_report(compat: list[dict]) -> None:
    groups = defaultdict(list)
    for index, row in enumerate(compat, start=1):
        key = (row["camera_id"], row["battery_id"], row["status"], row["source_url"])
        groups[key].append({"row_number": index, **row})

    duplicates = []
    for key, rows in sorted(groups.items()):
        if len(rows) <= 1:
            continue
        duplicates.append(
            {
                "key": {
                    "camera_id": key[0],
                    "battery_id": key[1],
                    "status": key[2],
                    "source_url": key[3],
                },
                "count": len(rows),
                "explanation": "Exact same camera/battery/status/source_url appears more than once.",
                "rows": rows,
            }
        )

    (REPORT_DIR / "duplicate_compatibility_report.json").write_text(
        json.dumps(duplicates, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_coverage_by_series(candidates: list[dict], compat: list[dict], unresolved: list[dict]) -> None:
    verified_ids = {
        row["camera_id"]
        for row in compat
        if row["status"] != "unknown"
    }
    high_ids = {
        row["camera_id"]
        for row in compat
        if row["status"] != "unknown" and row["confidence"] == "high"
    }
    unresolved_ids = {row["camera_id"] for row in unresolved}
    regional_alias_ids = {
        row["camera_id"]
        for row in candidates
        if has_regional_alias(row)
    }

    canon_candidates = [row for row in candidates if row["brand"] == "Canon"]
    canon_ids = {row["camera_id"] for row in canon_candidates}

    by_series: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for candidate in candidates:
        by_series[(candidate["brand"], candidate["series"])].append(candidate)

    lines = [
        "# Coverage By Series",
        "",
        f"Generated: {date.today().isoformat()}",
        "",
        "## Canon Batch 1 Summary",
        "",
        f"- Canon candidates: {len(canon_candidates)}",
        f"- Canon candidates with verified battery mapping: {len(canon_ids & verified_ids)}",
        f"- Canon unresolved candidates: {len(canon_ids & unresolved_ids)}",
        f"- Canon candidates with regional aliases: {len(canon_ids & regional_alias_ids)}",
        f"- Canon candidates with high-confidence verified mapping: {len(canon_ids & high_ids)}",
        "",
        "## Series Coverage",
        "",
        "| Brand | Series | Candidates | Verified | High-confidence verified | Unresolved | Regional aliases |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]

    for (brand, series), rows in sorted(by_series.items()):
        ids = {row["camera_id"] for row in rows}
        lines.append(
            "| "
            + " | ".join(
                [
                    markdown_cell(brand),
                    markdown_cell(series),
                    str(len(rows)),
                    str(len(ids & verified_ids)),
                    str(len(ids & high_ids)),
                    str(len(ids & unresolved_ids)),
                    str(len(ids & regional_alias_ids)),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Manual Check List",
            "",
            "| Brand | Series | Year | Camera | Reason | Candidate source |",
            "| --- | --- | ---: | --- | --- | --- |",
        ]
    )
    for row in sorted(unresolved, key=lambda item: (item["brand"], item["series"], item["display_name"])):
        lines.append(
            "| "
            + " | ".join(
                [
                    markdown_cell(row["brand"]),
                    markdown_cell(row["series"]),
                    markdown_cell(row["release_year"] if row["release_year"] is not None else ""),
                    markdown_cell(row["display_name"]),
                    markdown_cell(row["reason"]),
                    markdown_cell(row["candidate_source_url"]),
                ]
            )
            + " |"
        )

    (REPORT_DIR / "coverage_by_series.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_coverage_by_brand(
    cameras: list[dict],
    candidates: list[dict],
    compat: list[dict],
    unresolved: list[dict],
    sources: list[dict],
) -> None:
    importer_status_by_brand = load_importer_status_by_brand()
    camera_by_id = {camera["camera_id"]: camera for camera in cameras}
    candidate_by_id = {candidate["camera_id"]: candidate for candidate in candidates}
    brands = sorted({row["brand"] for row in candidates} | {row["brand"] for row in cameras})
    unresolved_ids_by_brand = defaultdict(set)
    for row in unresolved:
        unresolved_ids_by_brand[row["brand"]].add(row["camera_id"])

    compat_by_brand = defaultdict(list)
    for row in compat:
        camera = camera_by_id[row["camera_id"]]
        compat_by_brand[camera["brand"]].append(row)

    source_urls_by_brand = defaultdict(set)
    for candidate in candidates:
        source_urls_by_brand[candidate["brand"]].add(candidate["candidate_source_url"])
    for row in compat:
        brand = camera_by_id[row["camera_id"]]["brand"]
        source_urls_by_brand[brand].add(row["source_url"])

    source_url_registry = {source["source_url"] for source in sources}
    missing_registry_by_brand = {
        brand: sorted(urls - source_url_registry)
        for brand, urls in source_urls_by_brand.items()
        if urls - source_url_registry
    }

    lines = [
        "# Coverage By Brand",
        "",
        f"Generated: {date.today().isoformat()}",
        "",
        "| Brand | Total candidates | Verified cameras | Unresolved cameras | Compatibility rows | High confidence rows | Medium confidence rows | Low confidence rows | Alias/regional-name count | Source count |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    lines[-2] = "| Brand | Importer status | Total candidates | Verified cameras | Unresolved cameras | Compatibility rows | High confidence rows | Medium confidence rows | Low confidence rows | Alias/regional-name count | Source count |"
    lines[-1] = "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"
    for brand in brands:
        brand_candidates = [row for row in candidates if row["brand"] == brand]
        brand_candidate_ids = {row["camera_id"] for row in brand_candidates}
        verified = {
            row["camera_id"]
            for row in compat_by_brand[brand]
            if row["status"] != "unknown"
        }
        confidence = Counter(row["confidence"] for row in compat_by_brand[brand])
        alias_count = sum(1 for row in brand_candidates if has_regional_alias(row))
        lines.append(
            "| "
            + " | ".join(
                [
                    markdown_cell(brand),
                    markdown_cell(importer_status_by_brand.get(brand, "unknown")),
                    str(len(brand_candidates)),
                    str(len(brand_candidate_ids & verified)),
                    str(len(unresolved_ids_by_brand[brand])),
                    str(len(compat_by_brand[brand])),
                    str(confidence["high"]),
                    str(confidence["medium"]),
                    str(confidence["low"]),
                    str(alias_count),
                    str(len(source_urls_by_brand[brand])),
                ]
            )
            + " |"
        )

    if missing_registry_by_brand:
        lines.extend(["", "## Source URLs Missing From Registry", ""])
        for brand, urls in sorted(missing_registry_by_brand.items()):
            lines.append(f"- {brand}: {len(urls)}")

    (REPORT_DIR / "coverage_by_brand.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_importer_status_by_brand() -> dict[str, str]:
    path = REPORT_DIR / "import_all_remaining_report.json"
    status_by_brand = {"Canon": "preexisting_canon_batch"}
    if not path.exists():
        return status_by_brand
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return status_by_brand
    module_brands = {
        "importers.import_sony": ["Sony"],
        "importers.import_nikon": ["Nikon"],
        "importers.import_fujifilm": ["Fujifilm"],
        "importers.import_panasonic": ["Panasonic"],
        "importers.import_olympus_om": ["Olympus", "OM System"],
        "importers.import_ricoh_pentax": ["Ricoh", "Pentax"],
        "importers.import_casio": ["Casio"],
        "importers.import_kodak": ["Kodak", "Kodak PIXPRO"],
        "importers.import_samsung": ["Samsung"],
        "importers.import_leica_sigma": ["Leica", "Sigma"],
        "importers.import_minolta_konica": ["Minolta", "Konica Minolta"],
        "importers.import_minor_brands": [
            "AgfaPhoto",
            "GE",
            "Vivitar",
            "BenQ",
            "HP",
            "Polaroid",
            "Praktica",
            "Sanyo",
            "Toshiba",
            "Rollei",
            "SeaLife",
            "Yashica",
            "Minox",
        ],
    }
    for result in report.get("importer_results", []):
        for brand in module_brands.get(result.get("importer"), []):
            status_by_brand[brand] = result.get("adapter_status", "unknown")
    return status_by_brand


def write_unresolved_by_brand(unresolved: list[dict]) -> None:
    by_brand = defaultdict(list)
    for row in unresolved:
        by_brand[row["brand"]].append(row)

    lines = [
        "# Unresolved By Brand",
        "",
        f"Generated: {date.today().isoformat()}",
        "",
        "| Brand | Unresolved models |",
        "| --- | ---: |",
    ]
    for brand, rows in sorted(by_brand.items(), key=lambda item: (-len(item[1]), item[0])):
        lines.append(f"| {markdown_cell(brand)} | {len(rows)} |")

    lines.extend(["", "## Detail", ""])
    for brand, rows in sorted(by_brand.items()):
        lines.extend([f"### {brand}", ""])
        for row in sorted(rows, key=lambda item: (item["series"], item["display_name"])):
            lines.append(f"- {row['display_name']} ({row['series']}): {row['reason']} Source: {row['candidate_source_url']}")
        lines.append("")

    (REPORT_DIR / "unresolved_by_brand.md").write_text("\n".join(lines), encoding="utf-8")


def write_unresolved_sample_by_brand(unresolved: list[dict]) -> None:
    major_brands = {
        "Sony",
        "Nikon",
        "Fujifilm",
        "Panasonic",
        "Olympus",
        "Ricoh",
        "Pentax",
        "Casio",
        "Kodak",
        "Samsung",
        "Leica",
        "Sigma",
        "Minolta",
        "Konica Minolta",
        "HP",
    }
    by_brand = defaultdict(list)
    for row in unresolved:
        by_brand[row["brand"]].append(row)

    lines = [
        "# Unresolved Sample By Brand",
        "",
        f"Generated: {date.today().isoformat()}",
        "",
        "Major brands list up to 20 unresolved models; smaller brands list up to 5.",
        "",
    ]
    for brand, rows in sorted(by_brand.items(), key=lambda item: (-len(item[1]), item[0])):
        limit = 20 if brand in major_brands else 5
        lines.extend([f"## {brand}", ""])
        lines.append("| Camera | Series | Source | Reason |")
        lines.append("| --- | --- | --- | --- |")
        for row in sorted(rows, key=lambda item: (item["series"], item["display_name"]))[:limit]:
            lines.append(
                "| "
                + " | ".join(
                    [
                        markdown_cell(row["display_name"]),
                        markdown_cell(row["series"]),
                        markdown_cell(row["candidate_source_url"]),
                        markdown_cell(row["reason"]),
                    ]
                )
                + " |"
            )
        lines.append("")
    (REPORT_DIR / "unresolved_sample_by_brand.md").write_text("\n".join(lines), encoding="utf-8")


def write_source_coverage_report(
    cameras: list[dict],
    candidates: list[dict],
    compat: list[dict],
    sources: list[dict],
) -> None:
    camera_by_id = {camera["camera_id"]: camera for camera in cameras}
    source_by_url = {source["source_url"]: source for source in sources}
    used_urls = set()
    rows = []

    for candidate in candidates:
        used_urls.add(candidate["candidate_source_url"])
        rows.append((candidate["brand"], candidate["candidate_source_type"], candidate["candidate_source_url"], "candidate"))
    for row in compat:
        brand = camera_by_id[row["camera_id"]]["brand"]
        used_urls.add(row["source_url"])
        rows.append((brand, row["source_type"], row["source_url"], "compatibility"))

    by_brand_type = defaultdict(Counter)
    for brand, source_type, _url, usage in rows:
        by_brand_type[brand][source_type] += 1
        by_brand_type[brand][f"usage:{usage}"] += 1

    lines = [
        "# Source Coverage Report",
        "",
        f"Generated: {date.today().isoformat()}",
        "",
        f"- Registered sources: {len(sources)}",
        f"- Source URLs used by candidates/compatibility: {len(used_urls)}",
        f"- Used URLs missing from sources.json: {len(used_urls - set(source_by_url))}",
        "",
        "| Brand | Official manual | Official accessory | Trusted DB | Manual mirror | Retailer | Third-party | Unknown | Candidate uses | Compatibility uses |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for brand, counts in sorted(by_brand_type.items()):
        lines.append(
            "| "
            + " | ".join(
                [
                    markdown_cell(brand),
                    str(counts["official_manual"]),
                    str(counts["official_accessory_page"]),
                    str(counts["trusted_database"]),
                    str(counts["manual_mirror"]),
                    str(counts["retailer"]),
                    str(counts["third_party_chart"]),
                    str(counts["unknown"]),
                    str(counts["usage:candidate"]),
                    str(counts["usage:compatibility"]),
                ]
            )
            + " |"
        )

    missing = sorted(used_urls - set(source_by_url))
    if missing:
        lines.extend(["", "## Missing Registry URLs", ""])
        for url in missing:
            lines.append(f"- {url}")

    (REPORT_DIR / "source_coverage_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def short_model_risk(model: str) -> bool:
    core = re.sub(
        r"^(Canon\s+|Sony\s+|Nikon\s+|FUJIFILM\s+|Fujifilm\s+|RICOH\s+|Ricoh\s+|Leica\s+|Sigma\s+|PowerShot\s+|Cyber-shot\s+|COOLPIX\s+|DSC-|DMC-|DC-|EX-|FinePix\s+)",
        "",
        model,
        flags=re.I,
    )
    core = re.sub(r"[^A-Za-z0-9]+", " ", core).strip()
    return bool(re.fullmatch(r"[A-Z]?\d{1,2}[A-Z]?(?:\s.*)?", core, re.I))


def write_risky_short_model_matches(cameras: list[dict], compat: list[dict]) -> None:
    camera_by_id = {camera["camera_id"]: camera for camera in cameras}
    lines = [
        "# Risky Short Model Matches",
        "",
        f"Generated: {date.today().isoformat()}",
        "",
        "Short model names can match longer models if substring matching is used. This report lists verified rows whose model token needs exact-boundary review.",
        "",
        "| Brand | Camera | Model | Battery/source | Source type | Confidence | Reason |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    rows_written = 0
    for row in sorted(compat, key=lambda item: (item["camera_id"], item["battery_id"] or "", item["source_url"])):
        camera = camera_by_id[row["camera_id"]]
        if not short_model_risk(camera["model"]):
            continue
        rows_written += 1
        lines.append(
            "| "
            + " | ".join(
                [
                    markdown_cell(camera["brand"]),
                    markdown_cell(camera["display_name"]),
                    markdown_cell(camera["model"]),
                    markdown_cell(f"{row['battery_id']} / {row['source_url']}"),
                    markdown_cell(row["source_type"]),
                    markdown_cell(row["confidence"]),
                    "Exact source-backed row; review if source was not a direct product/manual page.",
                ]
            )
            + " |"
        )
    if rows_written == 0:
        lines.append("|  |  |  |  |  |  | No risky short verified model names found. |")
    (REPORT_DIR / "risky_short_model_matches.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_manual_audit_sample(cameras: list[dict], batteries: list[dict], compat: list[dict]) -> None:
    camera_by_id = {camera["camera_id"]: camera for camera in cameras}
    battery_by_id = {battery["battery_id"]: battery for battery in batteries}
    rows_by_brand = defaultdict(list)
    for row in compat:
        if row["status"] == "unknown":
            continue
        camera = camera_by_id[row["camera_id"]]
        rows_by_brand[camera["brand"]].append(row)

    rng = random.Random(20260524)
    major_brands = {
        "Canon",
        "Sony",
        "Nikon",
        "Fujifilm",
        "Panasonic",
        "Olympus",
        "Ricoh",
        "Pentax",
        "Casio",
        "Kodak",
        "Samsung",
        "Leica",
        "Sigma",
    }
    lines = [
        "# Manual Audit Sample",
        "",
        f"Generated: {date.today().isoformat()}",
        "",
        "Deterministic random sample using seed 20260524. If a brand has fewer rows than its target sample size, all rows are listed.",
        "",
    ]
    for brand in sorted(rows_by_brand):
        rows = rows_by_brand[brand]
        target = 20 if brand in major_brands else 5
        sample = rows[:] if len(rows) <= target else rng.sample(rows, target)
        lines.extend(
            [
                f"## {brand}",
                "",
                "| Camera | Battery model | Source URL | Source type | Confidence | Extracted power/note | Acceptance reason |",
                "| --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for row in sorted(sample, key=lambda item: (camera_by_id[item["camera_id"]]["display_name"], item["battery_id"] or "")):
            camera = camera_by_id[row["camera_id"]]
            battery = battery_by_id.get(row["battery_id"], {"model": row["battery_id"]})
            acceptance = (
                "Official source directly names the model/battery."
                if row["source_type"] in {"official_manual", "official_accessory_page"}
                else "Non-official source used with recorded confidence; manual review recommended."
            )
            lines.append(
                "| "
                + " | ".join(
                    [
                        markdown_cell(camera["display_name"]),
                        markdown_cell(battery["model"]),
                        markdown_cell(row["source_url"]),
                        markdown_cell(row["source_type"]),
                        markdown_cell(row["confidence"]),
                        markdown_cell(row["note"][:360]),
                        markdown_cell(acceptance),
                    ]
                )
                + " |"
            )
        lines.append("")

    (REPORT_DIR / "manual_audit_sample.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    cameras = load_json("cameras.json")
    batteries = load_json("batteries.json")
    compat = load_json("compatibility.json")
    candidates = load_optional_json("camera_candidates.json")
    sources = load_optional_json("sources.json")
    unresolved = load_optional_json("unresolved_models.json")

    validate(cameras, batteries, compat, candidates, sources, unresolved)

    EXPORT_DIR.mkdir(exist_ok=True)
    REPORT_DIR.mkdir(exist_ok=True)

    write_csv(EXPORT_DIR / "cameras.csv", cameras, CAMERA_FIELDS)
    write_csv(EXPORT_DIR / "batteries.csv", batteries, BATTERY_FIELDS)
    write_csv(EXPORT_DIR / "compatibility.csv", compat, COMPAT_FIELDS)
    if candidates:
        write_csv(EXPORT_DIR / "camera_candidates.csv", candidates, CANDIDATE_FIELDS)
    if sources:
        write_csv(EXPORT_DIR / "sources.csv", sources, SOURCE_FIELDS)
    if unresolved:
        write_csv(EXPORT_DIR / "unresolved_models.csv", unresolved, UNRESOLVED_FIELDS)
    write_report(cameras, compat)
    write_duplicate_alias_report(cameras, candidates)
    write_duplicate_compatibility_report(compat)
    write_coverage_by_series(candidates, compat, unresolved)
    write_coverage_by_brand(cameras, candidates, compat, unresolved, sources)
    write_unresolved_by_brand(unresolved)
    write_unresolved_sample_by_brand(unresolved)
    write_source_coverage_report(cameras, candidates, compat, sources)
    write_risky_short_model_matches(cameras, compat)
    write_manual_audit_sample(cameras, batteries, compat)

    print(f"Validated {len(cameras)} cameras, {len(batteries)} batteries, {len(compat)} compatibility rows.")
    print("Wrote CSV files to exports/")
    print("Wrote coverage reports to reports/")


if __name__ == "__main__":
    main()
