from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"


def load_json(name: str) -> list[dict]:
    path = DATA_DIR / name
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(name: str, rows: list[dict]) -> None:
    path = DATA_DIR / name
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def slug(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return re.sub(r"_+", "_", value).strip("_")


def valid_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def source_id(entry: dict) -> str:
    return slug(f"manual_missing_{entry['expected_brand']}_{entry['expected_model']}_{entry['source_url']}")[:180]


def camera_id(entry: dict) -> str:
    return slug(f"{entry['expected_brand']}_{entry['expected_model']}")


def battery_id(entry: dict) -> str:
    return entry.get("battery_id") or slug(f"{entry.get('battery_brand', entry['expected_brand'])}_{entry['battery_model']}")


def add_source(sources: list[dict], entry: dict) -> None:
    sid = source_id(entry)
    if any(row["source_id"] == sid or row["source_url"] == entry["source_url"] for row in sources):
        return
    sources.append(
        {
            "source_id": sid,
            "source_name": entry.get("source_name") or f"Manual missing query source {entry['expected_model']}",
            "source_url": entry["source_url"],
            "source_type": entry["source_type"],
            "publisher": entry.get("publisher") or entry["expected_brand"],
            "last_verified": entry.get("last_verified") or date.today().isoformat(),
            "notes": entry.get("notes") or "Added by scripts/import_missing_user_queries.py from data/manual_missing_queries.json.",
        }
    )


def make_camera(entry: dict, candidate_status: str, battery_system: str) -> dict:
    cid = camera_id(entry)
    display_name = entry.get("display_name") or f"{entry['expected_brand']} {entry['expected_model']}"
    aliases = sorted({entry["query"], entry["expected_model"], *(entry.get("aliases") or [])})
    return {
        "camera_id": cid,
        "brand": entry["expected_brand"],
        "series": entry.get("series") or entry["expected_brand"],
        "model": entry["expected_model"],
        "display_name": display_name,
        "aliases": aliases,
        "regional_names": entry.get("regional_names") or {},
        "release_year": entry.get("release_year"),
        "category": entry.get("category") or "unknown",
        "lens_type": "fixed_lens",
        "battery_system": battery_system,
        "notes": entry.get("notes") or "",
        "candidate_source_name": entry.get("source_name") or f"Manual missing query source {entry['expected_model']}",
        "candidate_source_url": entry["source_url"],
        "candidate_source_type": entry["source_type"],
        "candidate_batch": "manual_missing_user_queries",
        "candidate_status": candidate_status,
    }


def update_candidate(candidate: dict, entry: dict, candidate_status: str, battery_system: str) -> None:
    candidate["candidate_status"] = candidate_status
    candidate["battery_system"] = battery_system
    candidate["candidate_source_name"] = entry.get("source_name") or candidate["candidate_source_name"]
    candidate["candidate_source_url"] = entry["source_url"]
    candidate["candidate_source_type"] = entry["source_type"]
    candidate["candidate_batch"] = candidate.get("candidate_batch") or "manual_missing_user_queries"
    aliases = sorted({*candidate.get("aliases", []), entry["query"], entry["expected_model"], *(entry.get("aliases") or [])})
    candidate["aliases"] = aliases


def main() -> None:
    input_path = DATA_DIR / "manual_missing_queries.json"
    entries = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(entries, list):
        raise ValueError("data/manual_missing_queries.json must be a JSON array")
    if not entries:
        print("Processed 0 manual missing queries.")
        print("Added candidates: 0")
        print("Added verified compatibility rows: 0")
        return

    cameras = load_json("cameras.json")
    batteries = load_json("batteries.json")
    compatibility = load_json("compatibility.json")
    candidates = load_json("camera_candidates.json")
    sources = load_json("sources.json")
    unresolved = load_json("unresolved_models.json")

    camera_ids = {row["camera_id"] for row in cameras}
    candidates_by_id = {row["camera_id"]: row for row in candidates}
    candidate_ids = set(candidates_by_id)
    battery_ids = {row["battery_id"] for row in batteries}
    unresolved_by_id = {row["camera_id"]: row for row in unresolved}

    added_candidates = 0
    added_verified = 0
    for entry in entries:
        required = ["query", "expected_brand", "expected_model", "source_url", "source_type"]
        missing = [field for field in required if not entry.get(field)]
        if missing:
            raise ValueError(f"Entry missing required fields {missing}: {entry}")
        if not valid_url(entry["source_url"]):
            raise ValueError(f"Invalid source_url for {entry['query']}: {entry['source_url']}")

        cid = camera_id(entry)
        add_source(sources, entry)
        has_battery_mapping = bool(entry.get("battery_model") and entry.get("power_source_text"))
        battery_system = entry.get("battery_system") or ("proprietary_li_ion" if has_battery_mapping else "unknown")
        candidate_status = "verified_battery" if has_battery_mapping else "unresolved"

        if cid not in candidate_ids:
            candidates.append(make_camera(entry, candidate_status, battery_system))
            candidate_ids.add(cid)
            candidates_by_id[cid] = candidates[-1]
            added_candidates += 1
        else:
            update_candidate(candidates_by_id[cid], entry, candidate_status, battery_system)

        if has_battery_mapping:
            bid = battery_id(entry)
            if bid not in battery_ids:
                batteries.append(
                    {
                        "battery_id": bid,
                        "brand": entry.get("battery_brand") or entry["expected_brand"],
                        "model": entry["battery_model"],
                        "aliases": entry.get("battery_aliases") or [],
                        "chemistry": entry.get("battery_chemistry"),
                        "voltage": entry.get("battery_voltage"),
                        "capacity_mah": entry.get("battery_capacity_mah"),
                        "notes": entry.get("battery_notes") or "",
                    }
                )
                battery_ids.add(bid)
            if cid not in camera_ids:
                camera = make_camera(entry, "verified_battery", battery_system)
                cameras.append({key: camera[key] for key in [
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
                ]})
                camera_ids.add(cid)
            compat_key = (cid, bid, entry.get("compatibility_status") or "fully_compatible", entry["source_url"])
            existing_keys = {(row["camera_id"], row["battery_id"], row["status"], row["source_url"]) for row in compatibility}
            if compat_key not in existing_keys:
                compatibility.append(
                    {
                        "camera_id": cid,
                        "battery_id": bid,
                        "status": entry.get("compatibility_status") or "fully_compatible",
                        "quantity_required": entry.get("quantity_required") or 1,
                        "note": entry["power_source_text"],
                        "source_name": entry.get("source_name") or f"Manual missing query source {entry['expected_model']}",
                        "source_url": entry["source_url"],
                        "source_type": entry["source_type"],
                        "confidence": entry.get("confidence") or ("high" if entry["source_type"].startswith("official") else "medium"),
                        "last_verified": entry.get("last_verified") or date.today().isoformat(),
                    }
                )
                added_verified += 1
            unresolved_by_id.pop(cid, None)
        else:
            unresolved_by_id.setdefault(
                cid,
                {
                    "camera_id": cid,
                    "display_name": entry.get("display_name") or f"{entry['expected_brand']} {entry['expected_model']}",
                    "brand": entry["expected_brand"],
                    "series": entry.get("series") or entry["expected_brand"],
                    "release_year": entry.get("release_year"),
                    "reason": "Camera existence confirmed, battery not yet source-verified",
                    "candidate_source_name": entry.get("source_name") or f"Manual missing query source {entry['expected_model']}",
                    "candidate_source_url": entry["source_url"],
                    "checked_source_urls": [entry["source_url"]],
                    "last_checked": entry.get("last_verified") or date.today().isoformat(),
                },
            )

    write_json("cameras.json", cameras)
    write_json("batteries.json", batteries)
    write_json("compatibility.json", compatibility)
    write_json("camera_candidates.json", candidates)
    write_json("sources.json", sources)
    write_json("unresolved_models.json", sorted(unresolved_by_id.values(), key=lambda row: row["camera_id"]))

    print(f"Processed {len(entries)} manual missing queries.")
    print(f"Added candidates: {added_candidates}")
    print(f"Added verified compatibility rows: {added_verified}")


if __name__ == "__main__":
    main()
