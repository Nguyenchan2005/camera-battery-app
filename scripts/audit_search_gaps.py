from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
REPORT_DIR = ROOT / "reports"

DEFAULT_QUERIES = [
    "canon ixy500",
    "canon ixy 500",
    "ixy500",
    "ixy digital 500",
    "ixus500",
    "digital ixus500",
    "powershot s500",
    "sony t700",
    "sony dsc t700",
    "dsc t700",
    "dsct700",
    "cyber shot t700",
    "sony t900",
    "sony wx500",
    "sony t300",
    "sony t90",
    "canon ixy 30",
    "canon ixy 450",
    "nikon p1000",
    "coolpix p1000",
    "panasonic tz90",
    "panasonic zs70",
    "fuji f30",
    "finepix f30",
    "olympus tg6",
    "casio zr1000",
]


@dataclass
class Match:
    camera_id: str
    source_file: str
    reason: str


def load_json(name: str) -> list[dict]:
    with (DATA_DIR / name).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def compact(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "", value).upper()


def normalize(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[?!.:,;()[\]{}\"'`]+", " ", value)).strip()


def split_variants(value: str) -> list[str]:
    variants = {normalize(value)}
    variants.update(normalize(part) for part in re.split(r"[/,;|]+", value))
    variants.update(normalize(match) for match in re.findall(r"\(([^)]+)\)", value))
    variants.add(normalize(re.sub(r"\([^)]*\)", " ", value)))
    return [item for item in variants if item]


def flatten_regional(row: dict) -> list[str]:
    return [name for names in row.get("regional_names", {}).values() for name in names]


def add(values: set[str], value: str | None) -> None:
    if value and normalize(value):
        values.add(normalize(value))


def roman_for_mark(mark: str) -> str | None:
    return {"2": "II", "3": "III", "4": "IV", "5": "V", "6": "VI", "7": "VII"}.get(mark.upper())


def canon_blocked_suffix(term: str, match: re.Match) -> bool:
    suffix = term[match.end() :].strip()
    return bool(re.match(r"^(HS|IS|Ti|Mark|MK|II|III|IV|V|VI|VII)\b", suffix, re.I))


def generated_terms(row: dict) -> set[str]:
    brand = row["brand"]
    raw_terms = [
        row["display_name"],
        row["model"],
        row["brand"],
        row["series"],
        f"{row['brand']} {row['model']}",
        f"{row['brand']} {row['display_name']}",
        *row.get("aliases", []),
        *flatten_regional(row),
    ]
    terms = {variant for term in raw_terms for variant in split_variants(str(term))}
    generated = set(terms)

    for term in list(terms):
        no_powershot = re.sub(r"\bPowerShot\b", "", term, flags=re.I).strip()
        add(generated, no_powershot)
        add(generated, re.sub(r"\b(G\d+)\s+X\b", r"\1X", term, flags=re.I))

        mark = re.search(r"\b(.+?)\s+Mark\s+(II|III|IV|V|VI|VII)\b", term, re.I)
        if mark:
            add(generated, f"{mark.group(1)} {mark.group(2)}")
            add(generated, f"{mark.group(1).replace(' ', '')} {mark.group(2)}")

        ixy = re.search(r"\bIXY\s+(?:DIGITAL\s+)?([A-Z]?\d+[A-Z]?)\b", term, re.I)
        if ixy and not canon_blocked_suffix(term, ixy):
            code = ixy.group(1).upper()
            for value in [f"IXY {code}", f"IXY{code}", f"{brand} IXY {code}", f"{brand} IXY{code}"]:
                add(generated, value)

        ixus = re.search(r"\b(?:DIGITAL\s+)?IXUS\s+([A-Z]?\d+[A-Z]?)\b", term, re.I)
        if ixus and not canon_blocked_suffix(term, ixus):
            code = ixus.group(1).upper()
            for value in [f"IXUS {code}", f"IXUS{code}", f"{brand} IXUS {code}", f"{brand} IXUS{code}", f"Digital IXUS {code}", f"Digital IXUS{code}"]:
                add(generated, value)

        powershot = re.search(r"\bPowerShot\s+([A-Z]\d+[A-Z]?)\b", term, re.I)
        elph = re.search(r"\b([A-Z]\d+[A-Z]?)\s+(?:DIGITAL\s+)?ELPH\b", term, re.I)
        code = (powershot or elph).group(1).upper() if (powershot or elph) else None
        if code:
            for value in [f"PowerShot {code}", code, f"{code} ELPH", f"{code} DIGITAL ELPH", f"{brand} PowerShot {code}"]:
                add(generated, value)

        for dsc in re.finditer(r"\bDSC[-\s]?([A-Z]+\d+[A-Z0-9]*)\b", term, re.I):
            code = dsc.group(1).upper()
            for value in [code, f"Sony {code}", f"DSC {code}", f"DSC{code}", f"Sony DSC {code}", f"Sony DSC{code}", f"Cyber-shot {code}", f"Cyber shot {code}", f"Sony Cyber-shot {code}"]:
                add(generated, value)
            rx = re.match(r"^RX100M([2-7])A?$", code, re.I)
            if rx:
                roman = roman_for_mark(rx.group(1))
                if roman:
                    for value in [f"RX100 {roman}", f"Sony RX100 {roman}", f"Sony Cyber-shot RX100 {roman}", f"DSC RX100 {roman}"]:
                        add(generated, value)
                add(generated, f"RX100 {rx.group(1)}")

        nikon = re.search(r"\b(?:Nikon\s+)?(?:COOLPIX|Coolpix)?\s*([A-Z]\d{2,4}[A-Z]?)\b", term, re.I)
        if nikon:
            code = nikon.group(1).upper()
            for value in [code, f"Nikon {code}", f"Coolpix {code}", f"COOLPIX {code}", f"Nikon COOLPIX {code}"]:
                add(generated, value)

        pairs = {
            "TZ90": "ZS70",
            "ZS70": "TZ90",
            "TZ100": "ZS100",
            "ZS100": "TZ100",
            "TZ200": "ZS200",
            "ZS200": "TZ200",
            "TZ95": "ZS80",
            "ZS80": "TZ95",
            "TZ80": "ZS60",
            "ZS60": "TZ80",
        }
        for panasonic in re.finditer(r"\b(?:DMC|DC)?[-\s]?((?:TZ|ZS)\d+[A-Z]?)\b", term, re.I):
            code = panasonic.group(1).upper()
            for value in [code, f"Panasonic {code}", f"Lumix {code}", pairs.get(code), f"Panasonic {pairs.get(code)}" if pairs.get(code) else None]:
                add(generated, value)

        finepix = re.search(r"\bFinePix\s+([A-Z]+\d+[A-Z0-9]*)\b", term, re.I)
        xseries = re.search(r"\b(X(?:100|70|F10)\w*)\b", term, re.I)
        code = (finepix or xseries).group(1).upper() if (finepix or xseries) else None
        if code:
            for value in [code, f"Fuji {code}", f"Fujifilm {code}", f"FinePix {code}" if finepix else None, f"Fuji FinePix {code}" if finepix else None]:
                add(generated, value)

        for casio in re.finditer(r"\bEX[-\s]?((?:ZR|FH|FC|TR|Z|S|H)\d{2,4}[A-Z]?)\b", term, re.I):
            code = casio.group(1).upper()
            for value in [code, f"Casio {code}", f"Exilim {code}", f"EX{code}"]:
                add(generated, value)

        olympus = re.search(r"\bTG[-\s]?(\d{1,2})\b", term, re.I)
        if olympus:
            code = f"TG{olympus.group(1)}"
            for value in [code, f"Olympus {code}", f"Tough {code}"]:
                add(generated, value)

    return generated


def build_index(rows: list[dict], source_file: str) -> dict[str, list[Match]]:
    index: dict[str, list[Match]] = {}
    for row in rows:
        for term in generated_terms(row):
            index.setdefault(compact(term), []).append(Match(row["camera_id"], source_file, "generated/exact alias"))
    return index


def search(indexes: list[dict[str, list[Match]]], query: str) -> Match | None:
    q = compact(query)
    for index in indexes:
        matches = index.get(q)
        if matches:
            return matches[0]
    return None


def loose_find(indexes: list[dict[str, list[Match]]], query: str) -> Match | None:
    q = compact(query)
    if len(q) < 4:
        return None
    for index in indexes:
        for term, matches in index.items():
            if q == term or (len(q) >= 6 and len(term) >= 6 and (q in term or term in q)):
                return matches[0]
    return None


def markdown_cell(value: object) -> str:
    return str(value).replace("|", "\\|")


def main() -> None:
    cameras = load_json("cameras.json")
    candidates = load_json("camera_candidates.json")
    compatibility = load_json("compatibility.json")
    camera_ids = {row["camera_id"] for row in cameras}
    verified_ids = {row["camera_id"] for row in compatibility if row["status"] != "unknown"}
    camera_index = build_index(cameras, "data/cameras.json")
    candidate_only = [row for row in candidates if row["camera_id"] not in camera_ids]
    candidate_index = build_index(candidate_only, "data/camera_candidates.json")

    rows = []
    counts = {"A": 0, "B": 0, "C": 0, "D": 0, "E": 0}
    for query in DEFAULT_QUERIES:
        match = search([camera_index, candidate_index], query)
        loose = match or loose_find([camera_index, candidate_index], query)
        if match and match.camera_id in verified_ids:
            classification = "E. verified battery mapping"
            action = "No data action needed; search should return verified compatibility."
            key = "E"
        elif match:
            classification = "D. exists but missing battery mapping"
            action = "Keep unresolved; verify battery only from explicit source."
            key = "D"
        elif loose and loose.source_file == "data/cameras.json":
            classification = "A. in cameras.json but search missed"
            action = "Add/adjust search alias normalization."
            key = "A"
        elif loose:
            classification = "B. in camera_candidates.json but search missed"
            action = "Add/adjust search alias normalization."
            key = "B"
        else:
            classification = "C. not in candidate catalog"
            action = "Add to data/manual_missing_queries.json with source_url, then run scripts/import_missing_user_queries.py."
            key = "C"
        counts[key] += 1
        rows.append(
            {
                "query": query,
                "classification": classification,
                "matched_camera_id": match.camera_id if match else loose.camera_id if loose else "",
                "recommended_action": action,
                "source_file": match.source_file if match else loose.source_file if loose else "",
                "reason": match.reason if match else "Loose local-data check" if loose else "No local candidate/catalog match found",
            }
        )

    REPORT_DIR.mkdir(exist_ok=True)
    lines = [
        "# Search Gap Audit",
        "",
        f"Generated: {date.today().isoformat()}",
        "",
        "## Summary",
        "",
        f"- A in cameras.json but search missed: {counts['A']}",
        f"- B in camera_candidates.json but search missed: {counts['B']}",
        f"- C not in candidate catalog: {counts['C']}",
        f"- D exists but missing battery mapping: {counts['D']}",
        f"- E verified battery mapping: {counts['E']}",
        "",
        "| Query | Classification | Matched camera_id | Recommended action | Source file | Reason |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    markdown_cell(row["query"]),
                    markdown_cell(row["classification"]),
                    markdown_cell(row["matched_camera_id"]),
                    markdown_cell(row["recommended_action"]),
                    markdown_cell(row["source_file"]),
                    markdown_cell(row["reason"]),
                ]
            )
            + " |"
        )

    (REPORT_DIR / "search_gap_audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote reports/search_gap_audit.md for {len(DEFAULT_QUERIES)} queries.")


if __name__ == "__main__":
    main()
