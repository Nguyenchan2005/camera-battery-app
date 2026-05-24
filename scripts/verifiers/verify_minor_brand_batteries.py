from __future__ import annotations

from .common import result_template, unresolved_for_brands, verify_from_camera_wiki_page


def run(ctx):
    result = result_template("Minor brands")
    brands = {"HP", "GE", "AgfaPhoto", "Vivitar", "Minolta", "Konica Minolta", "Leica", "Sigma"}
    for unresolved in unresolved_for_brands(ctx, brands):
        result["processed"] += 1
        verified, message = verify_from_camera_wiki_page(ctx, unresolved)
        if verified:
            result["verified"] += 1
            result["verified_camera_ids"].append(unresolved["camera_id"])
        else:
            result["still_unresolved"] += 1
    return result
