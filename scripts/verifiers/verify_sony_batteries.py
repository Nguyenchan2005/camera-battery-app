from __future__ import annotations

from .common import (
    result_template,
    risky_short_sony_model,
    sony_support_url,
    unresolved_for_brands,
    verify_from_camera_wiki_page,
    verify_from_source,
)


def run(ctx):
    result = result_template("Sony")
    support_checks = 0
    for unresolved in unresolved_for_brands(ctx, {"Sony"}):
        result["processed"] += 1
        verified, message = verify_from_camera_wiki_page(ctx, unresolved)
        if not verified:
            candidate = next((row for row in ctx.candidates if row["camera_id"] == unresolved["camera_id"]), None)
            source_url = sony_support_url(candidate["model"] if candidate else unresolved["display_name"])
            if source_url and candidate and not risky_short_sony_model(candidate["model"]) and support_checks < 60:
                support_checks += 1
                verified, message = verify_from_source(
                    ctx,
                    unresolved,
                    source_url,
                    f"Sony support {candidate['model']} specifications",
                    "official_manual",
                    "high",
                    "Sony",
                    use_reader=True,
                )
                result["checked_urls"].append(source_url)
        if verified:
            result["verified"] += 1
            result["verified_camera_ids"].append(unresolved["camera_id"])
        else:
            result["still_unresolved"] += 1
            if message not in {"No individual Camera-wiki page.", "No battery mapping extracted."}:
                result["warnings"].append({"camera": unresolved["display_name"], "message": message})
    return result
