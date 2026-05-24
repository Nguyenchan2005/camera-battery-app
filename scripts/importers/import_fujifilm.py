from __future__ import annotations

from .camera_wiki_rules import fujifilm_records
from .common import fetch_text, import_camera_wiki_catalog, import_official_spec_records, mark_brand_processed, merge_import_results


BRAND = "Fujifilm"
BATCH_ID = "fujifilm_remaining_official_specs"
CATALOG_BATCH_ID = "fujifilm_camera_wiki_catalog_phase2"
CATALOG_URL = "https://camera-wiki.org/wiki/Fujifilm_digital_cameras"

RECORDS = [
    {
        "brand": "Fujifilm",
        "series": "X100",
        "model": "X100VI",
        "display_name": "FUJIFILM X100VI",
        "aliases": ["Fujifilm X100VI", "X100VI"],
        "regional_names": {"global": ["FUJIFILM X100VI"]},
        "category": "large_sensor_compact",
        "source_name": "Fujifilm X100VI online manual specifications",
        "source_url": "https://fujifilm-dsc.com/en/manual/x100vi/technical_notes/spec/index.html",
        "source_type": "official_manual",
        "publisher": "Fujifilm",
        "expected_batteries": [{"brand": "Fujifilm", "model": "NP-W126S"}],
    },
    {
        "brand": "Fujifilm",
        "series": "X100",
        "model": "X100V",
        "display_name": "FUJIFILM X100V",
        "aliases": ["Fujifilm X100V", "X100V"],
        "regional_names": {"global": ["FUJIFILM X100V"]},
        "category": "large_sensor_compact",
        "source_name": "Fujifilm X100V online manual specifications",
        "source_url": "https://fujifilm-dsc.com/en/manual/x100v/technical_notes/spec/index.html",
        "source_type": "official_manual",
        "publisher": "Fujifilm",
        "expected_batteries": [{"brand": "Fujifilm", "model": "NP-W126S"}],
    },
    {
        "brand": "Fujifilm",
        "series": "XF compact",
        "model": "XF10",
        "display_name": "FUJIFILM XF10",
        "aliases": ["Fujifilm XF10", "XF10"],
        "regional_names": {"global": ["FUJIFILM XF10"]},
        "category": "large_sensor_compact",
        "source_name": "Fujifilm XF10 online manual specifications",
        "source_url": "https://fujifilm-dsc.com/en/manual/xf10/technical_notes/spec/index.html",
        "source_type": "official_manual",
        "publisher": "Fujifilm",
        "expected_batteries": [{"brand": "Fujifilm", "model": "NP-95"}],
    },
]


def run(ctx):
    mark_brand_processed(ctx, BRAND)
    official_result = import_official_spec_records(ctx, BATCH_ID, RECORDS)
    page = fetch_text(CATALOG_URL)
    catalog_result = import_camera_wiki_catalog(
        ctx,
        CATALOG_BATCH_ID,
        "Camera-wiki Fujifilm digital cameras catalog",
        CATALOG_URL,
        "Camera-wiki",
        fujifilm_records(page, CATALOG_URL),
    )
    return merge_import_results(official_result, catalog_result, adapter_status="partial_adapter")
