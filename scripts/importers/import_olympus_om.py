from __future__ import annotations

from .camera_wiki_rules import olympus_records
from .common import fetch_text, import_camera_wiki_catalog, mark_brand_processed, merge_import_results


BRAND = "Olympus / OM System"
CATALOG_BATCH_ID = "olympus_camera_wiki_catalog_phase2"
STYLUS_BATCH_ID = "olympus_stylus_camera_wiki_catalog_phase2"
CATALOG_URL = "https://camera-wiki.org/wiki/Olympus"
STYLUS_URL = "https://camera-wiki.org/wiki/Olympus_Stylus_%C2%B5_digital_cameras"


def run(ctx):
    mark_brand_processed(ctx, BRAND)
    page = fetch_text(CATALOG_URL)
    stylus_page = fetch_text(STYLUS_URL)
    main_result = import_camera_wiki_catalog(
        ctx,
        CATALOG_BATCH_ID,
        "Camera-wiki Olympus catalog",
        CATALOG_URL,
        "Camera-wiki",
        olympus_records(page, CATALOG_URL),
    )
    stylus_result = import_camera_wiki_catalog(
        ctx,
        STYLUS_BATCH_ID,
        "Camera-wiki Olympus Stylus/mju digital catalog",
        STYLUS_URL,
        "Camera-wiki",
        olympus_records(stylus_page, STYLUS_URL),
    )
    return merge_import_results(main_result, stylus_result)
