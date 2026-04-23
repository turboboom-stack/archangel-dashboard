"""Parses weekly competitor keyword markdown reports from tracking/weekly-reports/."""

import os
import re
import config
from datetime import datetime


def _parse_report(filepath):
    """Parse a single competitor keyword markdown report. Returns dict."""
    result = {
        "date": None,
        "competitors_analyzed": 0,
        "total_keywords": 0,
        "new_this_week": 0,
        "keywords": [],
        "new_keywords": [],
    }

    # Extract date from filename: 2026-04-06-competitor-keywords.md
    fname = os.path.basename(filepath)
    m = re.match(r"(\d{4}-\d{2}-\d{2})", fname)
    if m:
        result["date"] = m.group(1)

    try:
        with open(filepath, "r") as f:
            content = f.read()
    except OSError:
        return result

    # Header stats
    for pattern, key in [
        (r"\*\*Competitors analyzed\*\*[:\s]+(\d+)", "competitors_analyzed"),
        (r"\*\*Total unique keywords tracked\*\*[:\s]+(\d+)", "total_keywords"),
        (r"\*\*New keywords this week\*\*[:\s]+(\d+)", "new_this_week"),
    ]:
        m = re.search(pattern, content)
        if m:
            result[key] = int(m.group(1))

    # Top 30 table: | Keyword | Businesses | Category |
    in_table = False
    for line in content.splitlines():
        if "| Keyword |" in line:
            in_table = True
            continue
        if in_table:
            if line.startswith("|---"):
                continue
            if not line.startswith("|"):
                in_table = False
                continue
            parts = [p.strip() for p in line.strip("|").split("|")]
            if len(parts) >= 3 and parts[0] and parts[0] != "Keyword":
                result["keywords"].append({
                    "keyword": parts[0],
                    "businesses": int(parts[1]) if parts[1].isdigit() else 0,
                    "category": parts[2],
                })

    # New This Week section
    new_section = re.search(r"## New This Week\n+(.*?)(?:\n---|\Z)", content, re.DOTALL)
    if new_section:
        new_text = new_section.group(1).strip()
        if new_text and new_text.lower() != "none.":
            # Parse table if present
            for line in new_text.splitlines():
                if line.startswith("|") and "---" not in line and "Keyword" not in line:
                    parts = [p.strip() for p in line.strip("|").split("|")]
                    if parts and parts[0]:
                        result["new_keywords"].append(parts[0])

    return result


def fetch():
    """Return all parsed reports sorted by date, plus a week-over-week diff."""
    report_dir = config.COMPETITOR_REPORTS_DIR
    if not os.path.isdir(report_dir):
        return {"reports": [], "latest": None, "new_this_week": [], "error": "No reports dir"}

    files = sorted([
        os.path.join(report_dir, f)
        for f in os.listdir(report_dir)
        if f.endswith(".md") and re.match(r"\d{4}-\d{2}-\d{2}", f)
    ])

    reports = [_parse_report(fp) for fp in files]
    reports = [r for r in reports if r["date"]]
    reports.sort(key=lambda r: r["date"])

    latest = reports[-1] if reports else None
    prior = reports[-2] if len(reports) >= 2 else None

    # Compute new-this-week diff by keyword text
    new_this_week = []
    if latest and prior:
        prior_kws = {k["keyword"].lower() for k in prior["keywords"]}
        for kw in latest.get("keywords", []):
            if kw["keyword"].lower() not in prior_kws:
                new_this_week.append(kw)
    elif latest:
        new_this_week = latest.get("new_keywords", [])

    return {
        "reports": reports,
        "latest": latest,
        "new_this_week": new_this_week,
        "total_reports": len(reports),
    }
