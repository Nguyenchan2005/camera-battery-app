from __future__ import annotations

from .camera_wiki_rules import minolta_konica_records
from .common import fetch_text, import_camera_wiki_catalog, mark_brand_processed


BRAND = "Minolta / Konica Minolta"
CATALOG_BATCH_ID = "minolta_konica_camera_wiki_catalog_phase2"
MINOLTA_URL = "https://camera-wiki.org/wiki/Minolta"
KONICA_MINOLTA_URL = "https://camera-wiki.org/wiki/Konica_Minolta"


def run(ctx):
    mark_brand_processed(ctx, BRAND)
    minolta_page = fetch_text(MINOLTA_URL)
    konica_page = fetch_text(KONICA_MINOLTA_URL)
    return import_camera_wiki_catalog(
        ctx,
        CATALOG_BATCH_ID,
        "Camera-wiki Minolta/Konica Minolta DiMAGE catalog",
        MINOLTA_URL,
        "Camera-wiki",
        minolta_konica_records(minolta_page, MINOLTA_URL, konica_page, KONICA_MINOLTA_URL),
    )
