from __future__ import annotations

import json
import re
from collections import Counter
from datetime import date
from pathlib import Path

from audit_search_gaps import compact, generated_terms


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
REPORT_DIR = ROOT / "reports"
INPUT_PATH = DATA_DIR / "manual_missing_queries.json"


def load_json(name: str) -> list[dict]:
    with (DATA_DIR / name).open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError(f"data/{name} must contain a JSON array")
    return data


def row_terms(row: dict) -> set[str]:
    return {compact(value) for value in generated_terms(row) if compact(value)}


def build_index(rows: list[dict]) -> dict[str, dict]:
    index: dict[str, dict] = {}
    for row in rows:
        for term in row_terms(row):
            index.setdefault(term, row)
    return index


def find_row(query: str, expected_model: str, index: dict[str, dict]) -> dict | None:
    query_keys = [compact(query), compact(expected_model)]
    query_keys.extend(compact(part) for part in re.split(r"[/,;|]+", expected_model or ""))
    for key in query_keys:
        if key and key in index:
            return index[key]
    return None


def markdown_cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def main() -> None:
    entries = load_json("manual_missing_queries.json")
    cameras = load_json("cameras.json")
    candidates = load_json("camera_candidates.json")
    unresolved = load_json("unresolved_models.json")

    camera_index = build_index(cameras)
    candidate_index = build_index(candidates)
    unresolved_ids = {row["camera_id"] for row in unresolved}
    status_counts = Counter(entry.get("status", "unspecified") for entry in entries)

    lines = [
        "# Manual Missing Query Audit",
        "",
        f"Generated: {date.today().isoformat()}",
        "",
        "## Summary",
        "",
        f"- total manual query notes: {len(entries)}",
    ]
    for status, count in sorted(status_counts.items()):
        lines.append(f"- {status}: {count}")

    lines.extend(
        [
            "",
            "## Rows",
            "",
            "| Query | Status | Expected brand | Expected model | Catalog state | Matched camera_id | Recommended action | Notes |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for entry in entries:
        query = entry.get("query", "")
        expected_model = entry.get("expected_model", "")
        matched = find_row(query, expected_model, camera_index)
        catalog_state = "verified_camera" if matched else ""
        if not matched:
            matched = find_row(query, expected_model, candidate_index)
            if matched:
                catalog_state = "unresolved_candidate" if matched["camera_id"] in unresolved_ids else "candidate"
        if not matched:
            catalog_state = "not_in_catalog"

        status = entry.get("status", "unspecified")
        if status == "search_alias_fixed":
            action = "No data action; keep search regression test."
        elif status == "unresolved_battery":
            action = "Find explicit battery source before promoting."
        elif status == "missing_candidate":
            action = "Add candidate only with source_url confirming existence."
        elif status == "verified_battery_source_added":
            action = "No data action; keep source-backed battery regression covered."
        else:
            action = "Review manually."

        lines.append(
            "| "
            + " | ".join(
                markdown_cell(value)
                for value in [
                    query,
                    status,
                    entry.get("expected_brand", ""),
                    entry.get("expected_model", ""),
                    catalog_state,
                    matched["camera_id"] if matched else "",
                    action,
                    entry.get("notes", ""),
                ]
            )
            + " |"
        )

    REPORT_DIR.mkdir(exist_ok=True)
    (REPORT_DIR / "manual_missing_query_audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote reports/manual_missing_query_audit.md for {len(entries)} manual query notes.")


if __name__ == "__main__":
    main()
