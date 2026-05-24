from __future__ import annotations

import importlib
import json
import sys
import traceback
from pathlib import Path

from importers.common import (
    ImportContext,
    backfill_sources_and_verified_candidates,
    dedupe_compatibility_for_app_output,
    move_unknown_only_cameras_to_unresolved,
    write_import_reports,
)
from validate_and_export import validate


ROOT = Path(__file__).resolve().parents[1]

IMPORTER_MODULES = [
    "importers.import_sony",
    "importers.import_nikon",
    "importers.import_fujifilm",
    "importers.import_panasonic",
    "importers.import_olympus_om",
    "importers.import_ricoh_pentax",
    "importers.import_casio",
    "importers.import_kodak",
    "importers.import_samsung",
    "importers.import_leica_sigma",
    "importers.import_minolta_konica",
    "importers.import_minor_brands",
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


def run_importer(ctx: ImportContext, module_name: str) -> dict:
    module = importlib.import_module(module_name)
    snapshot = ctx.snapshot()
    try:
        result = module.run(ctx)
        return {
            "importer": module_name,
            "status": "ok",
            "adapter_status": result.get("adapter_status", "warning_only" if result.get("processed", 0) == 0 else "real_adapter"),
            "processed": result.get("processed", 0),
            "verified": result.get("verified", 0),
            "unresolved": result.get("unresolved", 0),
            "warnings": result.get("warnings", []),
        }
    except Exception as exc:
        ctx.restore(snapshot)
        error = {
            "importer": module_name,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }
        ctx.errors.append(error)
        return {
            "importer": module_name,
            "status": "error",
            "adapter_status": "warning_only",
            "processed": 0,
            "verified": 0,
            "unresolved": 0,
            "warnings": [str(exc)],
        }


def main() -> int:
    ctx = ImportContext.load(ROOT)
    before = counts(ctx)
    importer_results = []

    for module_name in IMPORTER_MODULES:
        importer_results.append(run_importer(ctx, module_name))

    dedupe_compatibility_for_app_output(ctx)
    backfill_sources_and_verified_candidates(ctx)
    move_unknown_only_cameras_to_unresolved(ctx)
    ctx.sort_all()

    try:
        validate(ctx.cameras, ctx.batteries, ctx.compatibility, ctx.candidates, ctx.sources, ctx.unresolved)
    except Exception as exc:
        ctx.errors.append(
            {
                "importer": "validate_before_merge",
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
        )
        write_import_reports(ctx, before, importer_results)
        print("Import failed validation; data/*.json was not modified.")
        print(str(exc))
        return 1

    ctx.write_all()
    write_import_reports(ctx, before, importer_results)

    after = counts(ctx)
    print(json.dumps({"before": before, "after": after, "importers": importer_results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
