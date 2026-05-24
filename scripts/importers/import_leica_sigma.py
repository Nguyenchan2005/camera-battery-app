from __future__ import annotations

from .camera_wiki_rules import leica_sigma_records
from .common import fetch_text, import_camera_wiki_catalog, import_official_spec_records, mark_brand_processed, merge_import_results


BRAND = "Leica / Sigma"
BATCH_ID = "leica_sigma_remaining_official_specs"
CATALOG_BATCH_ID = "leica_sigma_camera_wiki_catalog_phase2"
LEICA_URL = "https://camera-wiki.org/wiki/Leica"
SIGMA_URL = "https://camera-wiki.org/wiki/Sigma"

RECORDS = [
    {
        "brand": "Leica",
        "series": "Q",
        "model": "Q3",
        "display_name": "Leica Q3",
        "aliases": ["LEICA Q3"],
        "regional_names": {"global": ["Leica Q3"]},
        "category": "large_sensor_compact",
        "source_name": "Leica Q3 technical specifications",
        "source_url": "https://leica-camera.com/en-US/photography/cameras/q/q3-black/technical-specification",
        "source_type": "official_manual",
        "publisher": "Leica",
        "expected_batteries": [{"brand": "Leica", "model": "BP-SCL6", "aliases": ["Leica BP-SCL6"]}],
    },
    *[
        {
            "brand": "Sigma",
            "series": "dp Quattro",
            "model": model,
            "display_name": display,
            "aliases": [display.replace("Sigma ", ""), model],
            "regional_names": {"global": [display]},
            "category": "large_sensor_compact",
            "source_name": f"Sigma {display} specifications",
            "source_url": f"https://www.sigma-global.com/en/cameras/{slug}/specification.html",
            "source_type": "official_manual",
            "publisher": "Sigma",
            "expected_batteries": [{"brand": "Sigma", "model": "BP-51"}],
        }
        for model, display, slug in [
            ("dp0 Quattro", "Sigma dp0 Quattro", "dp0-quattro"),
            ("dp1 Quattro", "Sigma dp1 Quattro", "dp1-quattro"),
            ("dp2 Quattro", "Sigma dp2 Quattro", "dp2-quattro"),
            ("dp3 Quattro", "Sigma dp3 Quattro", "dp3-quattro"),
        ]
    ],
]


def run(ctx):
    mark_brand_processed(ctx, BRAND)
    official_result = import_official_spec_records(ctx, BATCH_ID, RECORDS)
    leica_page = fetch_text(LEICA_URL)
    sigma_page = fetch_text(SIGMA_URL)
    catalog_result = import_camera_wiki_catalog(
        ctx,
        CATALOG_BATCH_ID,
        "Camera-wiki Leica/Sigma compact catalog",
        LEICA_URL,
        "Camera-wiki",
        leica_sigma_records(leica_page, LEICA_URL, sigma_page, SIGMA_URL),
    )
    return merge_import_results(official_result, catalog_result, adapter_status="partial_adapter")
