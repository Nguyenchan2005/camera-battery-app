from __future__ import annotations

from .camera_wiki_rules import minor_brand_records
from .common import fetch_text, import_camera_wiki_catalog, mark_brand_processed


BRAND = "Minor brands"
CATALOG_BATCH_ID = "minor_brands_camera_wiki_catalog_phase2"
SOURCE_URLS = {
    "GE": "https://camera-wiki.org/wiki/General_Imaging",
    "Vivitar": "https://camera-wiki.org/wiki/Vivitar",
    "HP": "https://camera-wiki.org/wiki/Hewlett-Packard",
    "AgfaPhoto": "https://camera-wiki.org/wiki/Agfa",
}


def run(ctx):
    mark_brand_processed(ctx, BRAND)
    pages = {
        brand: (fetch_text(url), url)
        for brand, url in SOURCE_URLS.items()
    }
    return import_camera_wiki_catalog(
        ctx,
        CATALOG_BATCH_ID,
        "Camera-wiki minor-brand compact catalog",
        SOURCE_URLS["GE"],
        "Camera-wiki",
        minor_brand_records(pages),
    )
