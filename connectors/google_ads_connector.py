"""Parse Google Ads CSV or HTML report uploads into the cache DB."""

import csv
import io
import re
from datetime import date, datetime
from models import db, GoogleAdsSnapshot, GoogleAdsKeyword, CacheMetadata

_DATE_FORMATS = ["%B %d, %Y", "%b %d, %Y", "%m/%d/%Y", "%Y-%m-%d"]


def _parse_date_range(lines):
    """Scan the first 5 lines for a 'Month D, YYYY - Month D, YYYY' pattern."""
    pattern = r"([A-Za-z]+ \d{1,2},?\s*\d{4})\s*[-–]\s*([A-Za-z]+ \d{1,2},?\s*\d{4})"
    for line in lines[:5]:
        m = re.search(pattern, line.strip().strip('"'))
        if m:
            for fmt in _DATE_FORMATS:
                try:
                    start = datetime.strptime(m.group(1).strip(), fmt).date()
                    end = datetime.strptime(m.group(2).strip(), fmt).date()
                    return start, end
                except ValueError:
                    continue
    return None, None


def _parse_csv(content: str):
    lines = content.splitlines()
    period_start, period_end = _parse_date_range(lines)

    # Skip Google Ads title/date preamble until we find the real header row.
    for i, line in enumerate(lines):
        if "," in line and re.search(r"\bClicks\b", line, re.IGNORECASE):
            content = "\n".join(lines[i:])
            break

    reader = csv.DictReader(io.StringIO(content))
    rows = list(reader)
    if not rows:
        raise ValueError("Empty CSV file")

    # Keep only rows with numeric Clicks (skip totals/header/footer)
    data_rows = []
    for row in rows:
        clicks_raw = row.get("Clicks", row.get("clicks", "")).strip().replace(",", "")
        if clicks_raw.isdigit():
            data_rows.append(row)

    if not data_rows:
        raise ValueError(
            "No data rows found — ensure you exported a keyword or campaign report"
        )

    def _float(row, *keys):
        for k in keys:
            v = row.get(k, "").strip().replace(",", "").replace("$", "").replace("%", "")
            try:
                return float(v)
            except ValueError:
                pass
        return 0.0

    total_clicks = sum(int(_float(r, "Clicks", "clicks")) for r in data_rows)
    total_impr = sum(int(_float(r, "Impressions", "impressions", "Impr.", "impr.")) for r in data_rows)
    total_cost = sum(_float(r, "Cost", "cost", "Spend", "spend") for r in data_rows)
    total_conv = sum(_float(r, "Conversions", "conversions") for r in data_rows)
    cpa = (total_cost / total_conv) if total_conv > 0 else 0
    conv_value = sum(_float(r, "Conv. value", "conversion_value", "ConversionValue") for r in data_rows)
    roas = (conv_value / total_cost) if total_cost > 0 else 0

    summary = {
        "total_clicks": total_clicks,
        "total_impressions": total_impr,
        "total_spend": round(total_cost, 2),
        "total_conversions": round(total_conv, 2),
        "cpa": round(cpa, 2),
        "roas": round(roas, 2),
        "period_start": period_start,
        "period_end": period_end,
    }

    keywords = []
    keyword_col = next(
        (col for col in data_rows[0].keys()
         if col.lower() in ("keyword", "search keyword", "search term")),
        None
    )
    if keyword_col:
        for r in data_rows:
            kw_clicks = int(_float(r, "Clicks", "clicks"))
            kw_cost = _float(r, "Cost", "cost", "Spend")
            kw_conv = _float(r, "Conversions", "conversions")
            keywords.append({
                "keyword": r.get(keyword_col, "").strip(),
                "match_type": r.get("Match type", r.get("match_type", "")).strip(),
                "campaign": r.get("Campaign", r.get("campaign", "")).strip(),
                "clicks": kw_clicks,
                "conversions": kw_conv,
                "cost": round(kw_cost, 2),
                "cpa": round(kw_cost / kw_conv, 2) if kw_conv > 0 else 0,
            })
        keywords.sort(key=lambda x: x["conversions"], reverse=True)

    return summary, keywords[:30]


def _parse_html(content: str):
    def _find_value(label, text):
        pattern = rf"<th[^>]*>{re.escape(label)}</th>\s*<td[^>]*>(.*?)</td>"
        m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if m:
            raw = re.sub(r"<[^>]+>", "", m.group(1)).strip()
            raw = raw.replace(",", "").replace("$", "").replace("%", "")
            try:
                return float(raw)
            except ValueError:
                pass
        return 0.0

    spend = (_find_value("Spend", content)
             or _find_value("Total Spend", content)
             or _find_value("Cost", content))
    clicks = int(_find_value("Clicks", content))
    impressions = int(_find_value("Impressions", content))
    conversions = _find_value("Conversions", content)
    cpa = _find_value("CPA", content) or _find_value("Cost per conversion", content)
    if cpa == 0 and conversions > 0 and spend > 0:
        cpa = round(spend / conversions, 2)

    # Try to extract date range from HTML text
    text_content = re.sub(r"<[^>]+>", " ", content)
    lines = text_content.splitlines()
    period_start, period_end = _parse_date_range(lines)

    keywords = []
    kw_table = re.search(
        r"<table[^>]*>.*?Keyword.*?</table>", content, re.IGNORECASE | re.DOTALL
    )
    if kw_table:
        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", kw_table.group(0), re.DOTALL)
        for row in rows[1:]:
            cells = [re.sub(r"<[^>]+>", "", c).strip()
                     for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL)]
            if len(cells) >= 4 and cells[0]:
                def _c(v):
                    try:
                        return float(v.replace(",", "").replace("$", ""))
                    except (ValueError, AttributeError):
                        return 0
                keywords.append({
                    "keyword": cells[0],
                    "match_type": "",
                    "campaign": "",
                    "clicks": int(_c(cells[1])) if len(cells) > 1 else 0,
                    "conversions": _c(cells[2]) if len(cells) > 2 else 0,
                    "cost": _c(cells[3]) if len(cells) > 3 else 0,
                    "cpa": _c(cells[4]) if len(cells) > 4 else 0,
                })

    return {
        "total_spend": round(spend, 2),
        "total_clicks": clicks,
        "total_impressions": impressions,
        "total_conversions": round(conversions, 2),
        "cpa": round(cpa, 2),
        "roas": 0,
        "period_start": period_start,
        "period_end": period_end,
    }, keywords[:30]


def save_upload(file_content: bytes, filename: str):
    meta = CacheMetadata.get("google_ads")
    try:
        content = file_content.decode("utf-8", errors="replace")
        if filename.lower().endswith((".html", ".htm")):
            summary, keywords = _parse_html(content)
        else:
            summary, keywords = _parse_csv(content)
    except Exception as e:
        meta.mark_error(str(e))
        return None, str(e)

    period_start = summary.get("period_start")
    period_end = summary.get("period_end")
    snapshot_date = period_end or date.today()

    # Dedup: replace existing snapshot for the same period
    if period_start and period_end:
        existing = (
            db.session.query(GoogleAdsSnapshot)
            .filter_by(period_start=period_start, period_end=period_end)
            .first()
        )
        if existing:
            db.session.query(GoogleAdsKeyword).filter_by(snapshot_id=existing.id).delete()
            db.session.delete(existing)
            db.session.flush()

    snap = GoogleAdsSnapshot(
        snapshot_date=snapshot_date,
        period_start=period_start,
        period_end=period_end,
        total_spend=summary["total_spend"],
        total_clicks=summary["total_clicks"],
        total_impressions=summary["total_impressions"],
        total_conversions=summary["total_conversions"],
        cpa=summary["cpa"],
        roas=summary["roas"],
    )
    db.session.add(snap)
    db.session.flush()

    for kw in keywords:
        db.session.add(GoogleAdsKeyword(
            snapshot_id=snap.id,
            keyword=kw["keyword"],
            match_type=kw["match_type"],
            campaign=kw["campaign"],
            clicks=kw["clicks"],
            conversions=kw["conversions"],
            cost=kw["cost"],
            cpa=kw["cpa"],
        ))

    db.session.commit()
    meta.mark_ok()
    return snap, None


def get_cached():
    snapshots = (
        db.session.query(GoogleAdsSnapshot)
        .order_by(GoogleAdsSnapshot.snapshot_date.asc())
        .all()
    )

    latest_keywords = []
    if snapshots:
        latest_keywords = (
            db.session.query(GoogleAdsKeyword)
            .filter_by(snapshot_id=snapshots[-1].id)
            .order_by(GoogleAdsKeyword.conversions.desc())
            .all()
        )

    return {"snapshots": snapshots, "latest_keywords": latest_keywords}
