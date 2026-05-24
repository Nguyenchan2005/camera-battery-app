from __future__ import annotations

import re

from .common import (
    camera_wiki_find_matches,
    camera_wiki_list_item_texts,
    detect_category,
    dedupe_aliases,
    extract_release_year,
    normalize_model_name,
    remove_release_year_text,
)


BAD_CONTEXT = re.compile(
    r"\b(?:DSLR|Digital SLR|SLR|mirrorless|interchangeable|camcorder|webcam|phone|smartphone|lens mount|lenses)\b",
    re.I,
)


def years_from_text(value: str) -> list[int]:
    return [int(year) for year in re.findall(r"\b(19\d{2}|20\d{2})\b", value or "")]


def in_scope(context: str) -> bool:
    years = years_from_text(context)
    if years and all(year < 1998 or year > 2026 for year in years):
        return False
    return True


def clean_name(value: str) -> str:
    value = remove_release_year_text(value)
    value = re.sub(r"\bimage by\b.*", "", value, flags=re.I)
    value = re.sub(r"\bRetrieved from\b.*", "", value, flags=re.I)
    value = re.sub(r"\bCategories\b.*", "", value, flags=re.I)
    value = re.sub(r"\s+", " ", value)
    return normalize_model_name(value).strip(" .,:;-/")


def add_record(
    records: list[dict],
    brand: str,
    series: str,
    model: str,
    display_name: str,
    source_url: str,
    context: str,
    aliases: list[str] | None = None,
    regional_names: dict[str, list[str]] | None = None,
    category: str | None = None,
) -> None:
    if not display_name or not model:
        return
    if not in_scope(context):
        return
    if BAD_CONTEXT.search(context) and brand not in {"Sigma"}:
        return
    release_year = extract_release_year(context)
    records.append(
        {
            "brand": brand,
            "series": series,
            "model": model,
            "display_name": display_name,
            "aliases": dedupe_aliases(aliases or []),
            "regional_names": regional_names or {"global": [display_name]},
            "release_year": release_year,
            "category": category or detect_category(brand, series, model, display_name),
            "source_url": source_url,
        }
    )


def sony_records(page_text: str, page_url: str) -> list[dict]:
    pattern = (
        r"\b(?:Sony\s+)?(?:Cyber-shot\s+)?DSC-"
        r"(?:RX100(?:M[2-7]A?|\s*(?:II|III|IV|V|VA|VI|VII))?|"
        r"RX10(?:M[2-4]|\s*(?:II|III|IV))?|RX1(?:R?M2|R)?|"
        r"HX\d{1,4}V?|H\d{1,4}|WX\d{1,4}|W\d{1,4}|TX\d{1,4}V?|T\d{1,4}|TF\d+)\b"
        r"|(?:Sony\s+)?ZV-1(?:F|\s+Mark\s+II|\s+II)?\b"
    )
    records: list[dict] = []
    for item in camera_wiki_find_matches(page_text, page_url, pattern):
        name = clean_name(item["raw_name"])
        if name.upper().startswith("DSC-"):
            code = name.upper().replace(" ", "")
            display = f"Sony Cyber-shot {name}"
        elif name.casefold().startswith("sony dsc-"):
            code = re.sub(r"^Sony\s+", "", name, flags=re.I)
            display = f"Sony Cyber-shot {code}"
        elif name.casefold().startswith("sony zv-"):
            code = re.sub(r"^Sony\s+", "", name, flags=re.I)
            display = f"Sony {code}"
        else:
            code = name
            display = name if name.startswith("Sony") else f"Sony {name}"
        core = code.upper()
        if core.startswith("DSC-RX100"):
            series = "Cyber-shot DSC-RX100"
            category = "premium_compact"
        elif core.startswith("DSC-RX10"):
            series = "Cyber-shot DSC-RX10"
            category = "bridge_superzoom"
        elif core.startswith("DSC-RX1"):
            series = "Cyber-shot DSC-RX1"
            category = "large_sensor_compact"
        elif core.startswith("DSC-HX"):
            series = "Cyber-shot DSC-HX"
            category = "travel_zoom"
        elif core.startswith("DSC-H"):
            series = "Cyber-shot DSC-H"
            category = "bridge_superzoom"
        elif core.startswith("DSC-WX"):
            series = "Cyber-shot DSC-WX"
            category = "travel_zoom"
        elif core.startswith("DSC-W"):
            series = "Cyber-shot DSC-W"
            category = "point_and_shoot"
        elif core.startswith("DSC-TX"):
            series = "Cyber-shot DSC-TX"
            category = "waterproof_compact" if "TX" in core and any(token in core for token in ["TX5", "TX10", "TX20", "TX30"]) else "point_and_shoot"
        elif core.startswith("DSC-T"):
            series = "Cyber-shot DSC-T"
            category = "point_and_shoot"
        else:
            series = "VLOGCAM ZV"
            category = "premium_compact"
        aliases = [code, display.replace("Sony Cyber-shot ", "Cyber-shot ")]
        add_record(records, "Sony", series, code, display, item["source_url"], item["context"], aliases, {"global": [display], "sony_code": [code]}, category)
    return records


def nikon_records(page_text: str, page_url: str) -> list[dict]:
    pattern = r"\b(?:Nikon\s+)?Coolpix\s+(?:A\d*|AW\d+|B\d+|L\d+|P\d+|S\d+|W\d+|[2-9]\d{2,3})\b"
    records: list[dict] = []
    for item in camera_wiki_find_matches(page_text, page_url, pattern):
        name = clean_name(item["raw_name"])
        model = re.sub(r"^Nikon\s+", "", name, flags=re.I)
        model = re.sub(r"^Coolpix", "COOLPIX", model, flags=re.I)
        number = re.sub(r"^COOLPIX\s+", "", model, flags=re.I).upper()
        if number in {"100", "300"}:
            continue
        series_key = number[:2] if number.startswith("AW") else number[:1]
        series = f"COOLPIX {series_key}"
        display = f"Nikon {model}"
        add_record(records, "Nikon", series, model, display, item["source_url"], item["context"], [model.title(), number], {"global": [model]}, None)
    return records


def fujifilm_records(page_text: str, page_url: str) -> list[dict]:
    pattern = (
        r"\b(?:Fujifilm|Fuji)\s+Fine[Pp]ix\s+(?:Real\s+3D\s+W[13]|"
        r"(?:A|AV|AX|F|J|JV|JX|JZ|S|HS|SL|XP|Z|T)\d{1,4}[A-Z]*(?:\s?(?:EXR|fd|HD|Zoom|W))?)\b"
        r"|\b(?:FUJIFILM|Fujifilm)\s+(?:X100(?:VI|V|F|T|S)?|X70|XF10)\b"
    )
    records: list[dict] = []
    for item in camera_wiki_find_matches(page_text, page_url, pattern):
        name = clean_name(item["raw_name"])
        if re.search(r"\bFinePix\s+S[1235]\s+Pro\b|\bIS\s+Pro\b", " ".join([name, item["context"]]), re.I):
            continue
        display = re.sub(r"^Fuji\s+", "Fujifilm ", name, flags=re.I)
        display = re.sub(r"Finepix", "FinePix", display, flags=re.I)
        model = re.sub(r"^(?:Fujifilm|FUJIFILM)\s+", "", display, flags=re.I)
        if model.upper().startswith("X"):
            series = "X100" if model.upper().startswith("X100") else "XF compact"
            category = "large_sensor_compact"
        elif "REAL 3D" in model.upper():
            series = "FinePix REAL 3D"
            category = "3d_compact"
        else:
            token = re.sub(r"^FinePix\s+", "", model, flags=re.I)
            prefix = re.match(r"[A-Z]+", token.upper()).group(0)
            series = f"FinePix {prefix}"
            category = None
        add_record(records, "Fujifilm", series, model, display, item["source_url"], item["context"], [display.replace("Fujifilm", "FUJIFILM")], {"global": [display]}, category)
    return records


def panasonic_records(page_text: str, page_url: str) -> list[dict]:
    pattern = r"\b(?:Panasonic\s+)?Lumix\s+(?:DMC|DC)-(?:FX|FS|LX|TZ|ZS|FZ|FT|TS|SZ|ZX|FP|LS|LZ|LC|LF)\d+[A-Z]*(?:\s+II)?\b"
    records: list[dict] = []
    for item in camera_wiki_find_matches(page_text, page_url, pattern):
        name = clean_name(item["raw_name"])
        if name.lower().startswith("lumix "):
            display = f"Panasonic {name}"
        else:
            display = name
        model = re.sub(r"^Panasonic\s+Lumix\s+", "", display, flags=re.I)
        prefix = re.match(r"(?:DMC|DC)-([A-Z]+)", model.upper()).group(1)
        if prefix == "FT":
            series = "Lumix FT/TS"
        elif prefix == "TS":
            series = "Lumix TS/FT"
        elif prefix in {"TZ", "ZS"}:
            series = "Lumix TZ/ZS"
        else:
            series = f"Lumix {prefix}"
        aliases = [model]
        if "DMC-TZ" in model.upper():
            aliases.append(model.upper().replace("DMC-TZ", "DMC-ZS"))
        if "DMC-ZS" in model.upper():
            aliases.append(model.upper().replace("DMC-ZS", "DMC-TZ"))
        if "DMC-FT" in model.upper():
            aliases.append(model.upper().replace("DMC-FT", "DMC-TS"))
        if "DMC-TS" in model.upper():
            aliases.append(model.upper().replace("DMC-TS", "DMC-FT"))
        add_record(records, "Panasonic", series, model, display, item["source_url"], item["context"], aliases, {"global": [display], "regional_aliases": aliases}, None)
    return records


def olympus_records(page_text: str, page_url: str) -> list[dict]:
    pattern = (
        r"\bOlympus\s+(?:Camedia\s+)?(?:C|D|FE|SP|SZ|VG|VR|VH|TG|XZ)-?\d+[A-Z]*(?:\s*iHS)?\b"
        r"|\bOlympus\s+(?:Stylus|µ|mju)\s+[A-Z0-9][A-Z0-9 :/.-]*(?:Digital|Tough|Verve|SW|WP|\d)\b"
    )
    records: list[dict] = []
    for item in camera_wiki_find_matches(page_text, page_url, pattern):
        name = clean_name(item["raw_name"])
        if "pen " in name.casefold() or name.upper().startswith("OLYMPUS E-"):
            continue
        display = name
        model = re.sub(r"^Olympus\s+", "", display, flags=re.I)
        if model.upper() in {"C-1000L", "C-1400L", "D-500L", "D-600L"}:
            continue
        if re.match(r"(Stylus|µ|mju)", model, re.I):
            series = "Stylus/mju Digital"
        else:
            prefix = re.match(r"(?:Camedia\s+)?([A-Z]+)", model.upper()).group(1)
            series = f"{prefix} series" if prefix != "TG" else "Tough/TG"
        aliases = [display.replace("Olympus Stylus", "Olympus mju")]
        add_record(records, "Olympus", series, model, display, item["source_url"], item["context"], aliases, {"global": [display], "regional_aliases": aliases}, None)
    return records


def casio_records(page_text: str, page_url: str) -> list[dict]:
    pattern = r"\bCasio\s+(?:Exilim\s+)?(?:EX-(?!FR)[A-Z0-9-]+|QV-?[A-Z0-9-]+)\b"
    records: list[dict] = []
    for item in camera_wiki_find_matches(page_text, page_url, pattern):
        name = clean_name(item["raw_name"])
        display = name if name.startswith("Casio") else f"Casio {name}"
        if " EX-" in display and "Exilim" not in display:
            display = display.replace("Casio EX-", "Casio Exilim EX-")
        model = re.sub(r"^Casio\s+", "", display, flags=re.I)
        if model.upper().startswith("QV"):
            number_match = re.search(r"\d+", model)
            if number_match and int(number_match.group(0)) < 1000:
                continue
            series = "QV"
        else:
            token = re.sub(r"^Exilim\s+", "", model, flags=re.I)
            series = "Exilim " + token.split("-")[1][:1] if token.startswith("EX-") and len(token.split("-")) > 1 else "Exilim"
        add_record(records, "Casio", series, model, display, item["source_url"], item["context"], [model], {"global": [display]}, None)
    return records


def kodak_records(page_text: str, page_url: str) -> list[dict]:
    records: list[dict] = []
    token_pattern = re.compile(r"\b(?:CD|CX|DX|LS|MD|MX|C|M|V|Z|ZD|P)\d{2,5}(?:\s+IS|\s+MAX|\s+Touch)?\b|\b(?:One\s+\dMP|SLICE)\b", re.I)
    for text in camera_wiki_list_item_texts(page_text):
        if "Kodak Easyshare" not in text and "Kodak EasyShare" not in text:
            continue
        start = re.search(r"Kodak\s+Easy[Ss]hare", text)
        if not start:
            continue
        fragment = text[start.end():]
        for token in token_pattern.finditer(fragment):
            model_token = normalize_model_name(token.group(0))
            display = f"Kodak EasyShare {model_token}"
            prefix = re.match(r"[A-Z]+", model_token.upper()).group(0)
            series = f"EasyShare {prefix}"
            add_record(records, "Kodak", series, f"EasyShare {model_token}", display, page_url, text, [f"Kodak Easyshare {model_token}"], {"global": [display]}, None)
    return records


def samsung_records(page_text: str, page_url: str) -> list[dict]:
    pattern = r"\bSamsung\s+(?:Digimax\s+[A-Z0-9-]+|NV\d+|PL\d+[A-Z]*|ST\d+[A-Z]*|WB\d+[A-Z]*|DV\d+[A-Z]*|ES\d+[A-Z]*|Galaxy\s+Camera(?:\s+\d)?)\b"
    records: list[dict] = []
    for item in camera_wiki_find_matches(page_text, page_url, pattern):
        display = clean_name(item["raw_name"])
        if "NX" in display:
            continue
        model = re.sub(r"^Samsung\s+", "", display, flags=re.I)
        series = "Galaxy Camera" if model.startswith("Galaxy") else model.split()[0] if model.startswith("Digimax") else re.match(r"[A-Z]+", model).group(0)
        add_record(records, "Samsung", series, model, display, item["source_url"], item["context"], [model], {"global": [display]}, None)
    return records


def ricoh_pentax_records(ricoh_text: str, ricoh_url: str, pentax_text: str, pentax_url: str) -> list[dict]:
    records: list[dict] = []
    ricoh_pattern = r"\bRicoh\s+(?:Caplio\s+(?:RR\d+|RR\d+[A-Z]*|G3(?:\s+model\s+[MS])?|Pro\s+G3|G4(?:\s+Wide)?|RZ1|RX|R\d+[A-Z]?|R\d{2}|GX\d*|GX100|R30|R40|[345]00G(?:\s+Wide)?|500SE)|CX\d|GR(?:\s+Digital(?:\s+(?:II|III|IV))?|\s+II|\s+IIIx?|\s+Rugged)?|WG-\d+|G600|G700(?:SE)?|PX)\b"
    for item in camera_wiki_find_matches(ricoh_text, ricoh_url, ricoh_pattern):
        display = clean_name(item["raw_name"])
        model = re.sub(r"^Ricoh\s+", "", display, flags=re.I)
        if model.startswith("Caplio"):
            series = "Caplio"
        elif model.startswith("CX"):
            series = "CX"
        elif model.startswith("GR"):
            series = "GR"
        elif model.startswith("WG"):
            series = "WG"
        else:
            series = "Rugged"
        add_record(records, "Ricoh", series, model, display, item["source_url"], item["context"], [model], {"global": [display]}, None)

    pentax_pattern = r"\bPentax\s+(?:Optio\s+[A-Z0-9-]+|WG-\d+)\b"
    for item in camera_wiki_find_matches(pentax_text, pentax_url, pentax_pattern):
        display = clean_name(item["raw_name"])
        model = re.sub(r"^Pentax\s+", "", display, flags=re.I)
        series = "WG" if model.startswith("WG") else "Optio"
        add_record(records, "Pentax", series, model, display, item["source_url"], item["context"], [model], {"global": [display]}, None)
    return records


def leica_sigma_records(leica_text: str, leica_url: str, sigma_text: str, sigma_url: str) -> list[dict]:
    records: list[dict] = []
    leica_pattern = r"\bLeica\s+(?:D-Lux\s*\d*|C-Lux\s*\d*|V-Lux\s*\d*|X(?:\s+Vario|-E|-U|1|2)?|Q(?:-P|2|3)?)\b"
    for item in camera_wiki_find_matches(leica_text, leica_url, leica_pattern):
        display = clean_name(item["raw_name"])
        if display == "Leica X":
            series = "X"
        else:
            series = display.replace("Leica ", "").split()[0]
        category = "large_sensor_compact" if series in {"Q", "X"} else None
        add_record(records, "Leica", series, display.replace("Leica ", ""), display, item["source_url"], item["context"], [display.upper()], {"global": [display]}, category)

    sigma_pattern = r"\b(?:Sigma\s+)?(?:DP[0-3](?:s|x|m)?|DP[0-3]\s+Quattro|dp[0-3]\s+Quattro)\b"
    for item in camera_wiki_find_matches(sigma_text, sigma_url, sigma_pattern):
        name = clean_name(item["raw_name"])
        display = name if name.startswith("Sigma") else f"Sigma {name}"
        model = display.replace("Sigma ", "")
        series = "dp Quattro" if "quattro" in model.casefold() else "DP"
        add_record(records, "Sigma", series, model, display, item["source_url"], item["context"], [model], {"global": [display]}, "large_sensor_compact")
    return records


def minolta_konica_records(minolta_text: str, minolta_url: str, konica_text: str, konica_url: str) -> list[dict]:
    records: list[dict] = []
    pattern = r"\b(?:Minolta|Konica\s+Minolta)\s+DiMAGE\s+(?:X\d*|Xi|Xt|Xg|F\d+|G\d+|Z\d+|A\d+|E\d+|S\d+)\b"
    for page_text, page_url in [(minolta_text, minolta_url), (konica_text, konica_url)]:
        for item in camera_wiki_find_matches(page_text, page_url, pattern):
            display = clean_name(item["raw_name"])
            brand = "Konica Minolta" if display.startswith("Konica") else "Minolta"
            model = re.sub(r"^(?:Konica\s+Minolta|Minolta)\s+", "", display, flags=re.I)
            token = model.replace("DiMAGE ", "")
            series = f"DiMAGE {re.match(r'[A-Z]+', token.upper()).group(0)}"
            add_record(records, brand, series, model, display, item["source_url"], item["context"], [model], {"global": [display]}, None)
    return records


def minor_brand_records(page_text_by_brand: dict[str, tuple[str, str]]) -> list[dict]:
    records: list[dict] = []
    patterns = {
        "GE": r"\bGE\s+(?:Power\s+Pro\s+)?[A-Z][A-Z0-9-]+\b",
        "Vivitar": r"\bVivitar\s+Vivi[Cc]am\s+[A-Z0-9-]+\b",
        "HP": r"\bHP\s+Photo[Ss]mart\s+[A-Z0-9-]+\b",
        "AgfaPhoto": r"\b(?:Agfa|AgfaPhoto)\s+(?:ePhoto|Sensor|Realishot)\s+[A-Z0-9-]+\b",
    }
    for brand, pattern in patterns.items():
        if brand not in page_text_by_brand:
            continue
        page_text, page_url = page_text_by_brand[brand]
        for item in camera_wiki_find_matches(page_text, page_url, pattern):
            display = clean_name(item["raw_name"])
            if display in {"GE logo", "GE of", "Agfa ePhoto name"}:
                continue
            display_brand = "AgfaPhoto" if display.startswith("Agfa ") else brand
            model = re.sub(rf"^{re.escape(display_brand)}\s+", "", display, flags=re.I)
            if display_brand == "GE":
                series = "GE compact"
            elif display_brand == "HP":
                series = "PhotoSmart"
            elif display_brand == "Vivitar":
                series = "ViviCam"
            else:
                series = "AgfaPhoto digital"
            add_record(records, display_brand, series, model, display, item["source_url"], item["context"], [model], {"global": [display]}, None)
    return records
