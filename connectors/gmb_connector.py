"""Google My Business Insights connector.

Live mode: Business Profile Performance API via shared OAuth.
Stub mode: realistic hardcoded data (config.STUBS["gmb"] = True).
"""

from datetime import date, timedelta
import config
from models import db, GmbInsight, CacheMetadata


STUB_DATA = {
    "SD": {
        "calls": 38,
        "website_clicks": 74,
        "direction_requests": 22,
        "review_count": 47,
        "avg_rating": 4.8,
        "last_post_date": (date.today() - timedelta(days=5)).isoformat(),
        "search_impressions": 1240,
        "map_views": 890,
    },
    "AV": {
        "calls": 21,
        "website_clicks": 35,
        "direction_requests": 14,
        "review_count": 23,
        "avg_rating": 4.9,
        "last_post_date": (date.today() - timedelta(days=3)).isoformat(),
        "search_impressions": 680,
        "map_views": 420,
    },
}


def _fetch_live(location_key, location_id):
    import json
    import urllib.request

    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
    except ImportError as exc:
        raise RuntimeError("google-auth not installed") from exc

    creds = Credentials.from_authorized_user_file(config.GOOGLE_TOKEN_PATH)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())

    end_date = date.today()
    start_date = end_date - timedelta(days=28)

    url = (
        f"https://businessprofileperformance.googleapis.com/v1/"
        f"locations/{location_id}:fetchMultiDailyMetricsTimeSeries"
        f"?dailyMetrics=CALL_CLICKS&dailyMetrics=WEBSITE_CLICKS"
        f"&dailyMetrics=BUSINESS_DIRECTION_REQUESTS"
        f"&dailyMetrics=BUSINESS_IMPRESSIONS_DESKTOP_MAPS"
        f"&dailyMetrics=BUSINESS_IMPRESSIONS_MOBILE_MAPS"
        f"&dailyRange.start_date.year={start_date.year}"
        f"&dailyRange.start_date.month={start_date.month}"
        f"&dailyRange.start_date.day={start_date.day}"
        f"&dailyRange.end_date.year={end_date.year}"
        f"&dailyRange.end_date.month={end_date.month}"
        f"&dailyRange.end_date.day={end_date.day}"
    )

    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {creds.token}",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())

    totals = {"calls": 0, "website_clicks": 0, "direction_requests": 0,
              "search_impressions": 0, "map_views": 0}
    metric_map = {
        "CALL_CLICKS": "calls",
        "WEBSITE_CLICKS": "website_clicks",
        "BUSINESS_DIRECTION_REQUESTS": "direction_requests",
        "BUSINESS_IMPRESSIONS_DESKTOP_MAPS": "map_views",
        "BUSINESS_IMPRESSIONS_MOBILE_MAPS": "map_views",
    }
    for outer in data.get("multiDailyMetricTimeSeries", []):
        for series in outer.get("dailyMetricTimeSeries", []):
            dest_key = metric_map.get(series.get("dailyMetric", ""))
            if not dest_key:
                continue
            for pt in series.get("timeSeries", {}).get("datedValues", []):
                totals[dest_key] += int(pt.get("value", 0) or 0)

    return {**totals, "review_count": 0, "avg_rating": 0, "last_post_date": None}


def fetch(app):
    meta = CacheMetadata.get("gmb")
    location_map = {"SD": config.GMB_LOCATION_SD, "AV": config.GMB_LOCATION_AV}

    with app.app_context():
        for loc_key, loc_id in location_map.items():
            if config.STUBS["gmb"]:
                d = STUB_DATA[loc_key]
            else:
                try:
                    d = _fetch_live(loc_key, loc_id)
                except Exception as e:
                    meta.mark_error(str(e))
                    return {"error": str(e)}

            last_post = None
            lp = d.get("last_post_date")
            if lp:
                try:
                    last_post = date.fromisoformat(str(lp))
                except ValueError:
                    pass

            db.session.add(GmbInsight(
                location=loc_key,
                calls=d["calls"],
                website_clicks=d["website_clicks"],
                direction_requests=d["direction_requests"],
                review_count=d["review_count"],
                avg_rating=d["avg_rating"],
                last_post_date=last_post,
                search_impressions=d.get("search_impressions", 0),
                map_views=d.get("map_views", 0),
            ))

        db.session.commit()
        if config.STUBS["gmb"]:
            meta.mark_stub()
        else:
            meta.mark_ok()

    return {"ok": True}


def get_cached():
    result = {}
    for loc in ("SD", "AV"):
        row = (
            db.session.query(GmbInsight)
            .filter_by(location=loc)
            .order_by(GmbInsight.refreshed_at.desc())
            .first()
        )
        result[loc] = row
    return result
