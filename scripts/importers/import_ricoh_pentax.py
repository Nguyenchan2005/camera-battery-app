from __future__ import annotations

from .camera_wiki_rules import ricoh_pentax_records
from .common import fetch_text, import_camera_wiki_catalog, import_official_spec_records, mark_brand_processed, merge_import_results


BRAND = "Ricoh / Pentax"
BATCH_ID = "ricoh_pentax_remaining_official_specs"
CATALOG_BATCH_ID = "ricoh_pentax_camera_wiki_catalog_phase2"
RICOH_URL = "https://camera-wiki.org/wiki/Ricoh"
PENTAX_URL = "https://camera-wiki.org/wiki/Pentax"

RECORDS = [
    {
        "brand": "Ricoh",
        "series": "GR",
        "model": "GR III",
        "display_name": "RICOH GR III",
        "aliases": ["Ricoh GR III", "GR III"],
        "regional_names": {"global": ["RICOH GR III"]},
        "category": "large_sensor_compact",
        "source_name": "Ricoh Imaging GR III/GR IIIx specifications",
        "source_url": "https://www.ricoh-imaging.co.jp/english/products/gr-3/spec/",
        "source_type": "official_manual",
        "publisher": "Ricoh",
        "expected_batteries": [{"brand": "Ricoh", "model": "DB-110"}],
    },
    {
        "brand": "Ricoh",
        "series": "GR",
        "model": "GR IIIx",
        "display_name": "RICOH GR IIIx",
        "aliases": ["Ricoh GR IIIx", "GR IIIx"],
        "regional_names": {"global": ["RICOH GR IIIx"]},
        "category": "large_sensor_compact",
        "source_name": "Ricoh Imaging GR III/GR IIIx specifications",
        "source_url": "https://www.ricoh-imaging.co.jp/english/products/gr-3/spec/",
        "source_type": "official_manual",
        "publisher": "Ricoh",
        "expected_batteries": [{"brand": "Ricoh", "model": "DB-110"}],
    },
    {
        "brand": "Pentax",
        "series": "WG",
        "model": "WG-90",
        "display_name": "PENTAX WG-90",
        "aliases": ["Pentax WG-90", "Ricoh WG-90"],
        "regional_names": {"global": ["PENTAX WG-90"]},
        "category": "waterproof_compact",
        "source_name": "Ricoh Imaging WG-90 specifications",
        "source_url": "https://www.ricoh-imaging.co.jp/english/products/wg-90/spec/",
        "source_type": "official_manual",
        "publisher": "Ricoh",
        "expected_batteries": [{"brand": "Pentax", "model": "D-LI92"}],
    },
]


def run(ctx):
    mark_brand_processed(ctx, BRAND)
    official_result = import_official_spec_records(ctx, BATCH_ID, RECORDS)
    ricoh_page = fetch_text(RICOH_URL)
    pentax_page = fetch_text(PENTAX_URL)
    catalog_result = import_camera_wiki_catalog(
        ctx,
        CATALOG_BATCH_ID,
        "Camera-wiki Ricoh/Pentax compact catalog",
        RICOH_URL,
        "Camera-wiki",
        ricoh_pentax_records(ricoh_page, RICOH_URL, pentax_page, PENTAX_URL),
    )
    return merge_import_results(official_result, catalog_result, adapter_status="partial_adapter")
