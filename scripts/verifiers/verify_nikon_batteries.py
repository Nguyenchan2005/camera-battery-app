from __future__ import annotations

from .common import (
    nikon_japan_spec_url,
    result_template,
    unresolved_for_brands,
    verify_from_camera_wiki_page,
    verify_from_source,
)


def run(ctx):
    result = result_template("Nikon")
    official_checks = 0
    for unresolved in unresolved_for_brands(ctx, {"Nikon"}):
        result["processed"] += 1
        candidate = next((row for row in ctx.candidates if row["camera_id"] == unresolved["camera_id"]), None)
        verified = False
        message = "Candidate missing."
        if candidate:
            source_url = nikon_japan_spec_url(candidate["model"])
            if source_url and official_checks < 160:
                official_checks += 1
                verified, message = verify_from_source(
                    ctx,
                    unresolved,
                    source_url,
                    f"Nikon Japan {candidate['model']} specifications",
                    "official_manual",
                    "high",
                    "Nikon",
                )
                result["checked_urls"].append(source_url)
        if not verified:
            verified, message = verify_from_camera_wiki_page(ctx, unresolved)
        if verified:
            result["verified"] += 1
            result["verified_camera_ids"].append(unresolved["camera_id"])
        else:
            result["still_unresolved"] += 1
            if message not in {"No individual Camera-wiki page.", "No battery mapping extracted."}:
                result["warnings"].append({"camera": unresolved["display_name"], "message": message})
    return result
