"""Google Search Console connector.

Live mode: Search Console API via shared OAuth.
Stub mode: realistic estate planning query data.
"""

from datetime import date, timedelta
import config
from models import db, GscQuery, GscSummary, CacheMetadata


STUB_QUERIES = [
    {"query": "estate planning attorney apple valley", "clicks": 24, "impressions": 310, "ctr": 0.077, "position": 3.2},
    {"query": "living trust attorney apple valley ca", "clicks": 18, "impressions": 280, "ctr": 0.064, "position": 4.1},
    {"query": "probate attorney san diego", "clicks": 9, "impressions": 420, "ctr": 0.021, "position": 12.4},
    {"query": "estate planning san diego", "clicks": 6, "impressions": 390, "ctr": 0.015, "position": 14.7},
    {"query": "archangel trust", "clicks": 31, "impressions": 44, "ctr": 0.70, "position": 1.1},
    {"query": "victoria martin attorney", "clicks": 12, "impressions": 18, "ctr": 0.67, "position": 1.3},
    {"query": "how long does probate take", "clicks": 14, "impressions": 820, "ctr": 0.017, "position": 8.9},
    {"query": "living trust vs will california", "clicks": 7, "impressions": 640, "ctr": 0.011, "position": 11.2},
    {"query": "probate attorney victorville", "clicks": 5, "impressions": 180, "ctr": 0.028, "position": 6.8},
    {"query": "estate planning hesperia ca", "clicks": 4, "impressions": 95, "ctr": 0.042, "position": 5.3},
    {"query": "trust administration attorney", "clicks": 3, "impressions": 210, "ctr": 0.014, "position": 15.6},
    {"query": "conservatorship attorney san bernardino", "clicks": 2, "impressions": 145, "ctr": 0.014, "position": 9.2},
    {"query": "power of attorney california", "clicks": 5, "impressions": 1100, "ctr": 0.005, "position": 22.4},
    {"query": "what is probate court", "clicks": 11, "impressions": 1800, "ctr": 0.006, "position": 18.3},
    {"query": "special needs trust attorney ca", "clicks": 2, "impressions": 88, "ctr": 0.023, "position": 7.1},
]


def _fetch_live():
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise RuntimeError("google-api-python-client not installed") from exc

    creds = Credentials.from_authorized_user_file(config.GOOGLE_TOKEN_PATH)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())

    service = build("searchconsole", "v1", credentials=creds, cache_discovery=False)
    end = date.today().isoformat()
    start = (date.today() - timedelta(days=28)).isoformat()

    resp = service.searchanalytics().query(
        siteUrl="https://www.archangeltrust.com/",
        body={"startDate": start, "endDate": end, "dimensions": ["query"], "rowLimit": 50}
    ).execute()

    rows = resp.get("rows", [])
    queries = [
        {
            "query": row["keys"][0],
            "clicks": row.get("clicks", 0),
            "impressions": row.get("impressions", 0),
            "ctr": round(row.get("ctr", 0), 4),
            "position": round(row.get("position", 0), 1),
        }
        for row in rows
    ]

    total_clicks = sum(q["clicks"] for q in queries)
    total_impr = sum(q["impressions"] for q in queries)
    avg_pos = (
        sum(q["position"] * q["impressions"] for q in queries) / total_impr
        if total_impr else 0
    )
    return queries, {
        "total_clicks": total_clicks,
        "total_impressions": total_impr,
        "avg_position": round(avg_pos, 1),
        "date_range": f"{start} to {end}",
    }


def fetch(app):
    meta = CacheMetadata.get("gsc")

    with app.app_context():
        if config.STUBS["gsc"]:
            queries = STUB_QUERIES
            total_clicks = sum(q["clicks"] for q in queries)
            total_impr = sum(q["impressions"] for q in queries)
            avg_pos = round(
                sum(q["position"] * q["impressions"] for q in queries) / total_impr, 1
            ) if total_impr else 0
            summary = {
                "total_clicks": total_clicks,
                "total_impressions": total_impr,
                "avg_position": avg_pos,
                "date_range": "last 28 days (stub)",
            }
        else:
            try:
                queries, summary = _fetch_live()
            except Exception as e:
                meta.mark_error(str(e))
                return {"error": str(e)}

        db.session.execute(db.delete(GscQuery))
        db.session.execute(db.delete(GscSummary))

        for q in queries:
            db.session.add(GscQuery(**q))

        db.session.add(GscSummary(
            total_clicks=summary["total_clicks"],
            total_impressions=summary["total_impressions"],
            avg_position=summary["avg_position"],
            date_range=summary["date_range"],
        ))
        db.session.commit()

        if config.STUBS["gsc"]:
            meta.mark_stub()
        else:
            meta.mark_ok()

    return {"ok": True, "queries": len(queries)}


def get_cached():
    queries = db.session.query(GscQuery).order_by(GscQuery.impressions.desc()).all()
    summary = db.session.query(GscSummary).order_by(GscSummary.refreshed_at.desc()).first()
    return {"queries": queries, "summary": summary}
