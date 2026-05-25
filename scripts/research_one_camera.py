from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from importers.common import ImportContext
from llm_assisted_research_batch import DATA_DIR, execute, load_evidence


ROOT = Path(__file__).resolve().parents[1]


def compact(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").casefold())


def find_evidence(query: str) -> dict | None:
    wanted = compact(query)
    evidence, _errors = load_evidence()
    for row in evidence:
        terms = [row.get("display_name", ""), row.get("camera_id", ""), *row.get("aliases_found", [])]
        if any(wanted == compact(term) or wanted in compact(term) or compact(term) in wanted for term in terms if compact(term)):
            return row
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Show reviewed research evidence for one camera and optionally apply it.")
    parser.add_argument("query")
    parser.add_argument("--apply", action="store_true", help="Apply accepted source-backed evidence for this camera only.")
    args = parser.parse_args()
    row = find_evidence(args.query)
    if row is None:
        print(f"No reviewed battery evidence recorded for: {args.query}")
        print("Apply: no")
        return
    ctx = ImportContext.load(ROOT)
    currently_verified = any(camera["camera_id"] == row["camera_id"] for camera in ctx.cameras)
    print(f"Camera: {row['display_name']}")
    print(f"Aliases found: {', '.join(row.get('aliases_found', [])) or 'none recorded'}")
    print(f"Battery: {row['battery_model']}")
    if row.get("chemistry"):
        print(f"Chemistry: {row['chemistry']}")
    if row.get("voltage") is not None:
        print(f"Voltage: {row['voltage']} V")
    if row.get("capacity_mah") is not None:
        print(f"Capacity: {row['capacity_mah']} mAh")
    print(f"Evidence level: {row['evidence_level']}")
    print(f"Source: {row['source_name']} - {row['source_url']}")
    print(f"Evidence text: {row['source_text']}")
    print(f"Current database status: {'verified' if currently_verified else 'not verified'}")
    print("Evidence JSON:")
    print(json.dumps(row, ensure_ascii=False, indent=2))
    if args.apply:
        result = execute(1, True, {row["camera_id"]})
        applied = next((item for item in result["results"] if item.get("camera_id") == row["camera_id"]), None)
        print(f"Apply: {applied['decision'] if applied else 'no eligible change'}")
    else:
        print(f"Proposed database change: {row['decision']}")
        print("Apply: no (run again with --apply after review)")


if __name__ == "__main__":
    main()
