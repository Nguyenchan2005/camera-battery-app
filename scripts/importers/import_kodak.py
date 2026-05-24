from __future__ import annotations

from .camera_wiki_rules import kodak_records
from .common import fetch_text, import_camera_wiki_catalog, mark_brand_processed


BRAND = "Kodak / Kodak PIXPRO"
CATALOG_BATCH_ID = "kodak_camera_wiki_catalog_phase2"
CATALOG_URL = "https://camera-wiki.org/wiki/Kodak"


def run(ctx):
    mark_brand_processed(ctx, BRAND)
    page = fetch_text(CATALOG_URL)
    return import_camera_wiki_catalog(
        ctx,
        CATALOG_BATCH_ID,
        "Camera-wiki Kodak catalog",
        CATALOG_URL,
        "Camera-wiki",
        kodak_records(page, CATALOG_URL),
    )
