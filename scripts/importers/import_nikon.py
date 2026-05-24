from __future__ import annotations

from .camera_wiki_rules import nikon_records
from .common import fetch_text, import_camera_wiki_catalog, import_official_spec_records, mark_brand_processed, merge_import_results


BRAND = "Nikon"
BATCH_ID = "nikon_remaining_official_specs"
CATALOG_BATCH_ID = "nikon_camera_wiki_catalog_phase2"
CATALOG_URL = "https://camera-wiki.org/wiki/Nikon_Coolpix"

RECORDS = [
    {
        "brand": "Nikon",
        "series": "COOLPIX P",
        "model": "COOLPIX P1100",
        "display_name": "Nikon COOLPIX P1100",
        "aliases": ["Coolpix P1100", "P1100"],
        "regional_names": {"global": ["COOLPIX P1100"]},
        "category": "bridge_superzoom",
        "source_name": "Nikon Global COOLPIX P1100 specifications",
        "source_url": "https://imaging.nikon.com/imaging/lineup/coolpix/p/p1100/",
        "source_type": "official_manual",
        "publisher": "Nikon",
        "expected_batteries": [{"brand": "Nikon", "model": "EN-EL20a", "aliases": ["EN-EL20A"]}],
    },
    {
        "brand": "Nikon",
        "series": "COOLPIX P",
        "model": "COOLPIX P1000",
        "display_name": "Nikon COOLPIX P1000",
        "aliases": ["Coolpix P1000", "P1000"],
        "regional_names": {"global": ["COOLPIX P1000"]},
        "category": "bridge_superzoom",
        "source_name": "Nikon Global COOLPIX P1000 specifications",
        "source_url": "https://imaging.nikon.com/imaging/lineup/coolpix/p/p1000/",
        "source_type": "official_manual",
        "publisher": "Nikon",
        "expected_batteries": [{"brand": "Nikon", "model": "EN-EL20a", "aliases": ["EN-EL20A"]}],
    },
    {
        "brand": "Nikon",
        "series": "COOLPIX P",
        "model": "COOLPIX P950",
        "display_name": "Nikon COOLPIX P950",
        "aliases": ["Coolpix P950", "P950"],
        "regional_names": {"global": ["COOLPIX P950"]},
        "category": "bridge_superzoom",
        "source_name": "Nikon Global COOLPIX P950 specifications",
        "source_url": "https://imaging.nikon.com/imaging/lineup/coolpix/p/p950/",
        "source_type": "official_manual",
        "publisher": "Nikon",
        "expected_batteries": [{"brand": "Nikon", "model": "EN-EL20a", "aliases": ["EN-EL20A"]}],
    },
]


def run(ctx):
    mark_brand_processed(ctx, BRAND)
    official_result = import_official_spec_records(ctx, BATCH_ID, RECORDS)
    page = fetch_text(CATALOG_URL)
    catalog_result = import_camera_wiki_catalog(
        ctx,
        CATALOG_BATCH_ID,
        "Camera-wiki Nikon Coolpix catalog",
        CATALOG_URL,
        "Camera-wiki",
        nikon_records(page, CATALOG_URL),
    )
    return merge_import_results(official_result, catalog_result, adapter_status="partial_adapter")
