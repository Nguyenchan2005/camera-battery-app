from __future__ import annotations

import importlib
import json
import sys
import traceback
from pathlib import Path

from importers.common import ImportContext, dedupe_compatibility_for_app_output
from validate_and_export import validate
from verifiers.common import (
    merge_results,
    run_http_status_checks,
    write_phase3_reports,
)


ROOT = Path(__file__).resolve().parents[1]

VERIFIER_MODULES = [
    "verifiers.verify_fujifilm_batteries",
    "verifiers.verify_nikon_batteries",
    "verifiers.verify_kodak_batteries",
    "verifiers.verify_olympus_batteries",
    "verifiers.verify_casio_batteries",
    "verifiers.verify_sony_batteries",
    "verifiers.verify_panasonic_batteries",
    "verifiers.verify_samsung_batteries",
    "verifiers.verify_ricoh_pentax_batteries",
    "verifiers.verify_minor_brand_batteries",
]

KNOWN_BROKEN_URLS = [
    "https://leica-camera.com/en-AT/photography/cameras/q/q2-disney/technical-specification",
]


def counts(ctx: ImportContext) -> dict[str, int]:
    return {
        "cameras": len(ctx.cameras),
        "batteries": len(ctx.batteries),
        "compatibility": len(ctx.compatibility),
        "candidates": len(ctx.candidates),
        "sources": len(ctx.sources),
        "unresolved": len(ctx.unresolved),
    }


def run_verifier(ctx: ImportContext, module_name: str) -> dict:
    module = importlib.import_module(module_name)
    snapshot = ctx.snapshot()
    try:
        result = module.run(ctx)
        result["module"] = module_name
        return result
    except Exception as exc:
        ctx.restore(snapshot)
        return {
            "module": module_name,
            "verifier": module_name,
            "processed": 0,
            "verified": 0,
            "still_unresolved": 0,
            "warnings": [
                {
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                }
            ],
            "checked_urls": [],
            "verified_camera_ids": [],
        }


def main() -> int:
    ctx = ImportContext.load(ROOT)
    before = counts(ctx)
    verifier_results = []

    for module_name in VERIFIER_MODULES:
        verifier_results.append(run_verifier(ctx, module_name))

    dedupe_compatibility_for_app_output(ctx)
    ctx.sort_all()

    try:
        validate(ctx.cameras, ctx.batteries, ctx.compatibility, ctx.candidates, ctx.sources, ctx.unresolved)
    except Exception as exc:
        print("Phase 3 verification failed validation; data/*.json was not modified.")
        print(str(exc))
        return 1

    merged = merge_results(verifier_results)
    phase3_verified_ids = {
        row["camera_id"]
        for row in ctx.candidates
        if row.get("candidate_batch") == "phase3_verified_from_unresolved"
        and row.get("candidate_status") == "verified_battery"
    }
    urls_to_check = [
        row["source_url"]
        for row in ctx.compatibility
        if row["camera_id"] in (set(merged["verified_camera_ids"]) | phase3_verified_ids)
    ]
    http_status_rows = run_http_status_checks(urls_to_check, extra_urls=KNOWN_BROKEN_URLS, limit=220)

    ctx.write_all()
    write_phase3_reports(ctx, before, verifier_results, http_status_rows)

    after = counts(ctx)
    compact_results = [
        {
            "verifier": result["verifier"],
            "processed": result["processed"],
            "verified": result["verified"],
            "still_unresolved": result["still_unresolved"],
            "warnings": len(result.get("warnings", [])),
        }
        for result in verifier_results
    ]
    print(json.dumps({"before": before, "after": after, "verifiers": compact_results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
