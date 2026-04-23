"""Google Analytics 4 connector — GA4 Data API v1beta."""

import json
import logging
from datetime import datetime

import config
from models import db, Ga4Summary, CacheMetadata

log = logging.getLogger(__name__)

PROPERTY = f"properties/{config.GA4_PROPERTY_ID}"
DATE_RANGE = {"startDate": "7daysAgo", "endDate": "today"}


def _get_service():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    creds = Credentials.from_authorized_user_file(config.GOOGLE_TOKEN_PATH)
    if not creds.valid and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return build("analyticsdata", "v1beta", credentials=creds)


def _run_report(svc, dimensions, metrics, dimension_filter=None, limit=10):
    body = {
        "dateRanges": [DATE_RANGE],
        "dimensions": [{"name": d} for d in dimensions],
        "metrics": [{"name": m} for m in metrics],
        "limit": limit,
    }
    if dimension_filter:
        body["dimensionFilter"] = dimension_filter
    return svc.properties().runReport(property=PROPERTY, body=body).execute()


def _row_val(row, index, numeric=False):
    try:
        v = row["dimensionValues"][index]["value"] if index < len(row.get("dimensionValues", [])) else ""
    except (KeyError, IndexError):
        v = ""
    if numeric:
        try:
            return float(v)
        except (ValueError, TypeError):
            return 0.0
    return v


def _metric_val(row, index):
    try:
        return float(row["metricValues"][index]["value"])
    except (KeyError, IndexError, ValueError):
        return 0.0


def fetch(app):
    try:
        svc = _get_service()

        # ── Overall summary ────────────────────────────────────────────────────
        summary_resp = _run_report(
            svc,
            dimensions=[],
            metrics=[
                "sessions", "activeUsers", "newUsers",
                "averageSessionDuration", "bounceRate",
            ],
            limit=1,
        )
        row = summary_resp.get("rows", [{}])[0] if summary_resp.get("rows") else {}
        sessions   = int(_metric_val(row, 0))
        act_users  = int(_metric_val(row, 1))
        new_users  = int(_metric_val(row, 2))
        avg_dur    = round(_metric_val(row, 3), 1)
        bounce     = round(_metric_val(row, 4) * 100, 1)  # API returns 0-1

        # ── Conversion events ──────────────────────────────────────────────────
        events_resp = _run_report(
            svc,
            dimensions=["eventName"],
            metrics=["eventCount"],
            dimension_filter={
                "filter": {
                    "fieldName": "eventName",
                    "inListFilter": {"values": config.GA4_CONVERSION_EVENTS},
                }
            },
            limit=20,
        )
        conversions = {}
        for r in events_resp.get("rows", []):
            name  = _row_val(r, 0)
            count = int(_metric_val(r, 0))
            conversions[name] = count
        # Ensure all tracked events appear even if zero
        for ev in config.GA4_CONVERSION_EVENTS:
            conversions.setdefault(ev, 0)

        # ── Channel breakdown ──────────────────────────────────────────────────
        channel_resp = _run_report(
            svc,
            dimensions=["sessionDefaultChannelGrouping"],
            metrics=["sessions"],
            limit=10,
        )
        channels = {}
        for r in channel_resp.get("rows", []):
            ch    = _row_val(r, 0) or "Other"
            count = int(_metric_val(r, 0))
            channels[ch] = count

        # ── Top landing pages ──────────────────────────────────────────────────
        pages_resp = _run_report(
            svc,
            dimensions=["landingPage"],
            metrics=["sessions", "bounceRate"],
            limit=10,
        )
        top_pages = []
        for r in pages_resp.get("rows", []):
            top_pages.append({
                "page":     _row_val(r, 0),
                "sessions": int(_metric_val(r, 0)),
                "bounce":   round(_metric_val(r, 1) * 100, 1),
            })

        with app.app_context():
            db.session.query(Ga4Summary).delete()
            db.session.add(Ga4Summary(
                date_range=f"{DATE_RANGE['startDate']} to {DATE_RANGE['endDate']}",
                sessions=sessions,
                active_users=act_users,
                new_users=new_users,
                avg_session_duration=avg_dur,
                bounce_rate=bounce,
                conversions_json=json.dumps(conversions),
                channels_json=json.dumps(channels),
                top_pages_json=json.dumps(top_pages),
            ))
            db.session.commit()
            CacheMetadata.get("ga4").mark_ok()
            log.info(f"GA4: {sessions} sessions, conversions={conversions}")

    except Exception as e:
        log.error(f"GA4 fetch failed: {e}")
        with app.app_context():
            CacheMetadata.get("ga4").mark_error(str(e))


def get_cached():
    row = db.session.query(Ga4Summary).order_by(Ga4Summary.refreshed_at.desc()).first()
    if not row:
        return None
    return {
        "date_range":          row.date_range,
        "sessions":            row.sessions,
        "active_users":        row.active_users,
        "new_users":           row.new_users,
        "avg_session_duration": row.avg_session_duration,
        "bounce_rate":         row.bounce_rate,
        "conversions":         json.loads(row.conversions_json or "{}"),
        "channels":            json.loads(row.channels_json or "{}"),
        "top_pages":           json.loads(row.top_pages_json or "[]"),
        "refreshed_at":        row.refreshed_at,
    }
