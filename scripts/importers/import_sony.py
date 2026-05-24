from __future__ import annotations

from .camera_wiki_rules import sony_records
from .common import fetch_text, import_camera_wiki_catalog, import_official_spec_records, mark_brand_processed, merge_import_results


BRAND = "Sony"
BATCH_ID = "sony_remaining_official_specs"
CATALOG_BATCH_ID = "sony_camera_wiki_catalog_phase2"
CATALOG_URL = "https://camera-wiki.org/wiki/Sony"

RX_RECORDS = [
    ("DSC-RX100", "RX100", "Sony Cyber-shot DSC-RX100", ["Sony RX100"]),
    ("DSC-RX100M2", "RX100 II", "Sony Cyber-shot DSC-RX100 II", ["RX100M2", "RX100 II"]),
    ("DSC-RX100M3", "RX100 III", "Sony Cyber-shot DSC-RX100 III", ["RX100M3", "RX100 III"]),
    ("DSC-RX100M4", "RX100 IV", "Sony Cyber-shot DSC-RX100 IV", ["RX100M4", "RX100 IV"]),
    ("DSC-RX100M5", "RX100 V", "Sony Cyber-shot DSC-RX100 V", ["RX100M5", "RX100 V"]),
    ("DSC-RX100M5A", "RX100 VA", "Sony Cyber-shot DSC-RX100 VA", ["RX100M5A", "RX100 VA"]),
    ("DSC-RX100M6", "RX100 VI", "Sony Cyber-shot DSC-RX100 VI", ["RX100M6", "RX100 VI"]),
    ("DSC-RX100M7", "RX100 VII", "Sony Cyber-shot DSC-RX100 VII", ["RX100M7", "RX100 VII"]),
]

RECORDS = [
    *[
        {
            "brand": "Sony",
            "series": "Cyber-shot DSC-RX100",
            "model": code,
            "display_name": display,
            "aliases": [code, *aliases],
            "regional_names": {"japan": [code], "global": [display]},
            "category": "premium_compact",
            "source_name": f"Sony Japan {code} specifications",
            "source_url": f"https://www.sony.jp/cyber-shot/products/{code}/spec.html",
            "source_type": "official_manual",
            "publisher": "Sony",
            "expected_batteries": [{"brand": "Sony", "model": "NP-BX1"}],
        }
        for code, model, display, aliases in RX_RECORDS
    ],
    {
        "brand": "Sony",
        "series": "Cyber-shot DSC-RX10",
        "model": "DSC-RX10M3",
        "display_name": "Sony Cyber-shot DSC-RX10 III",
        "aliases": ["DSC-RX10M3", "RX10 III", "RX10M3"],
        "regional_names": {"japan": ["DSC-RX10M3"], "global": ["Sony Cyber-shot DSC-RX10 III"]},
        "category": "bridge_superzoom",
        "source_name": "Sony Japan DSC-RX10M3 specifications",
        "source_url": "https://www.sony.jp/cyber-shot/products/DSC-RX10M3/spec.html",
        "source_type": "official_manual",
        "publisher": "Sony",
        "expected_batteries": [{"brand": "Sony", "model": "NP-FW50"}],
    },
    {
        "brand": "Sony",
        "series": "Cyber-shot DSC-RX10",
        "model": "DSC-RX10M4",
        "display_name": "Sony Cyber-shot DSC-RX10 IV",
        "aliases": ["DSC-RX10M4", "RX10 IV", "RX10M4"],
        "regional_names": {"japan": ["DSC-RX10M4"], "global": ["Sony Cyber-shot DSC-RX10 IV"]},
        "category": "bridge_superzoom",
        "source_name": "Sony Japan DSC-RX10M4 specifications",
        "source_url": "https://www.sony.jp/cyber-shot/products/DSC-RX10M4/spec.html",
        "source_type": "official_manual",
        "publisher": "Sony",
        "expected_batteries": [{"brand": "Sony", "model": "NP-FW50"}],
    },
    {
        "brand": "Sony",
        "series": "Cyber-shot DSC-RX1",
        "model": "DSC-RX1",
        "display_name": "Sony Cyber-shot DSC-RX1",
        "aliases": ["DSC-RX1", "RX1"],
        "regional_names": {"japan": ["DSC-RX1"], "global": ["Sony Cyber-shot DSC-RX1"]},
        "category": "large_sensor_compact",
        "source_name": "Sony Japan DSC-RX1 specifications",
        "source_url": "https://www.sony.jp/cyber-shot/products/DSC-RX1/spec.html",
        "source_type": "official_manual",
        "publisher": "Sony",
        "expected_batteries": [{"brand": "Sony", "model": "NP-BX1"}],
    },
    {
        "brand": "Sony",
        "series": "Cyber-shot DSC-RX1",
        "model": "DSC-RX1R",
        "display_name": "Sony Cyber-shot DSC-RX1R",
        "aliases": ["DSC-RX1R", "RX1R"],
        "regional_names": {"japan": ["DSC-RX1R"], "global": ["Sony Cyber-shot DSC-RX1R"]},
        "category": "large_sensor_compact",
        "source_name": "Sony Japan DSC-RX1R specifications",
        "source_url": "https://www.sony.jp/cyber-shot/products/DSC-RX1R/spec.html",
        "source_type": "official_manual",
        "publisher": "Sony",
        "expected_batteries": [{"brand": "Sony", "model": "NP-BX1"}],
    },
    {
        "brand": "Sony",
        "series": "Cyber-shot DSC-RX1",
        "model": "DSC-RX1RM2",
        "display_name": "Sony Cyber-shot DSC-RX1R II",
        "aliases": ["DSC-RX1RM2", "RX1R II", "RX1RM2"],
        "regional_names": {"japan": ["DSC-RX1RM2"], "global": ["Sony Cyber-shot DSC-RX1R II"]},
        "category": "large_sensor_compact",
        "source_name": "Sony Japan DSC-RX1RM2 specifications",
        "source_url": "https://www.sony.jp/cyber-shot/products/DSC-RX1RM2/spec.html",
        "source_type": "official_manual",
        "publisher": "Sony",
        "expected_batteries": [{"brand": "Sony", "model": "NP-BX1"}],
    },
    {
        "brand": "Sony",
        "series": "VLOGCAM ZV",
        "model": "ZV-1",
        "display_name": "Sony ZV-1",
        "aliases": ["VLOGCAM ZV-1"],
        "regional_names": {"japan": ["VLOGCAM ZV-1"], "global": ["Sony ZV-1"]},
        "category": "premium_compact",
        "source_name": "Sony Japan ZV-1 specifications",
        "source_url": "https://www.sony.jp/vlogcam/products/ZV-1/specification.html",
        "source_type": "official_manual",
        "publisher": "Sony",
        "expected_batteries": [{"brand": "Sony", "model": "NP-BX1"}],
    },
    {
        "brand": "Sony",
        "series": "VLOGCAM ZV",
        "model": "ZV-1M2",
        "display_name": "Sony ZV-1 II",
        "aliases": ["VLOGCAM ZV-1 II", "ZV-1M2"],
        "regional_names": {"japan": ["VLOGCAM ZV-1 II", "ZV-1M2"], "global": ["Sony ZV-1 II"]},
        "category": "premium_compact",
        "source_name": "Sony Japan ZV-1 II specifications",
        "source_url": "https://www.sony.jp/vlogcam/products/ZV-1M2/spec/",
        "source_type": "official_manual",
        "publisher": "Sony",
        "expected_batteries": [{"brand": "Sony", "model": "NP-BX1"}],
    },
]


def run(ctx):
    mark_brand_processed(ctx, BRAND)
    official_result = import_official_spec_records(ctx, BATCH_ID, RECORDS)
    page = fetch_text(CATALOG_URL)
    catalog_result = import_camera_wiki_catalog(
        ctx,
        CATALOG_BATCH_ID,
        "Camera-wiki Sony catalog",
        CATALOG_URL,
        "Camera-wiki",
        sony_records(page, CATALOG_URL),
    )
    return merge_import_results(official_result, catalog_result, adapter_status="partial_adapter")
