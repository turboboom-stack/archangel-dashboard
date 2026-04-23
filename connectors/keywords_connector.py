"""Reads keywords.json from the seo-content-engine — no auth required."""

import json
import os
import config

def fetch():
    """Return keyword counts by status and the top pending keywords by volume."""
    try:
        with open(config.KEYWORDS_JSON_PATH, "r") as f:
            keywords = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        return {"error": str(e), "counts": {}, "top_pending": [], "top_published": []}

    counts = {"pending": 0, "generated": 0, "published": 0}
    top_pending = []
    top_published = []

    for kw in keywords:
        status = kw.get("status", "pending")
        counts[status] = counts.get(status, 0) + 1
        if status == "pending":
            top_pending.append(kw)
        elif status == "published":
            top_published.append(kw)

    top_pending.sort(key=lambda x: x.get("volume") or 0, reverse=True)
    top_published.sort(key=lambda x: x.get("volume") or 0, reverse=True)

    # Count generated posts in posts/ dir
    generated_count = 0
    if os.path.isdir(config.POSTS_DIR):
        generated_count = len([f for f in os.listdir(config.POSTS_DIR) if f.endswith(".json")])

    return {
        "counts": counts,
        "generated_files": generated_count,
        "top_pending": top_pending[:10],
        "top_published": top_published[:10],
        "total": len(keywords),
    }
