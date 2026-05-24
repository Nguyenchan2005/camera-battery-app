from __future__ import annotations

from .camera_wiki_rules import casio_records
from .common import fetch_text, import_camera_wiki_catalog, mark_brand_processed


BRAND = "Casio"
CATALOG_BATCH_ID = "casio_camera_wiki_catalog_phase2"
CATALOG_URL = "https://camera-wiki.org/wiki/Casio"


def run(ctx):
    mark_brand_processed(ctx, BRAND)
    page = fetch_text(CATALOG_URL)
    return import_camera_wiki_catalog(
        ctx,
        CATALOG_BATCH_ID,
        "Camera-wiki Casio catalog",
        CATALOG_URL,
        "Camera-wiki",
        casio_records(page, CATALOG_URL),
    )
