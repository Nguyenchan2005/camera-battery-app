from __future__ import annotations

from .common import (
    fujifilm_manual_urls,
    result_template,
    unresolved_for_brands,
    verify_from_camera_wiki_page,
    verify_from_source,
)


def run(ctx):
    result = result_template("Fujifilm")
    manual_checks = 0
    for unresolved in unresolved_for_brands(ctx, {"Fujifilm"}):
        result["processed"] += 1
        candidate = next((row for row in ctx.candidates if row["camera_id"] == unresolved["camera_id"]), None)
        verified = False
        message = "Candidate missing."
        if candidate and manual_checks < 90:
            # Phase 3 keeps this bounded: the first Fujifilm official manual
            # pattern covers the common FinePix naming scheme; deeper brute
            # force is left to manual follow-up if it misses.
            for source_url in fujifilm_manual_urls(candidate["model"])[:1]:
                manual_checks += 1
                verified, message = verify_from_source(
                    ctx,
                    unresolved,
                    source_url,
                    f"Fujifilm {candidate['model']} owner manual",
                    "official_manual",
                    "high",
                    "Fujifilm",
                    use_reader=True,
                )
                result["checked_urls"].append(source_url)
                if verified or "HTTP Error 404" not in message:
                    break
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
