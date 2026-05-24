from __future__ import annotations

from .camera_wiki_rules import panasonic_records
from .common import fetch_text, import_camera_wiki_catalog, mark_brand_processed


BRAND = "Panasonic"
CATALOG_BATCH_ID = "panasonic_camera_wiki_catalog_phase2"
CATALOG_URL = "https://camera-wiki.org/wiki/Panasonic"


def run(ctx):
    mark_brand_processed(ctx, BRAND)
    page = fetch_text(CATALOG_URL)
    return import_camera_wiki_catalog(
        ctx,
        CATALOG_BATCH_ID,
        "Camera-wiki Panasonic catalog",
        CATALOG_URL,
        "Camera-wiki",
        panasonic_records(page, CATALOG_URL),
    )
