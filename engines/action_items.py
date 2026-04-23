"""Rule-based action items engine.

Each rule function returns an ActionItem dict (or list of dicts) or None.
The engine runs all rules over current cached data and persists results.
"""

import json
from datetime import datetime, date
from models import db, ActionItem, GoogleAdsSnapshot, GmbInsight, GscQuery, WebflowPost, ClioBooking
import config
import connectors.competitor_reports_connector as cr_conn
import connectors.seo_db_connector as seo_conn


SEVERITY_RANK = {"critical": 0, "warning": 1, "opportunity": 2}


def _item(severity, category, rule_id, message, cta_text=None, cta_url=None):
    return {
        "severity": severity,
        "category": category,
        "rule_id": rule_id,
        "message": message,
        "cta_text": cta_text or "",
        "cta_url": cta_url or "",
    }


def _month_start():
    return date.today().replace(day=1)


# ── Rules ─────────────────────────────────────────────────────────────────────

def rule_ads_high_cpa():
    snap = (
        db.session.query(GoogleAdsSnapshot)
        .order_by(GoogleAdsSnapshot.snapshot_date.desc())
        .first()
    )
    if snap and snap.cpa > 0 and snap.cpa > 150:
        return _item(
            "critical", "ads", "ADS_HIGH_CPA",
            f"Google Ads CPA is ${snap.cpa:.0f} — target is <$150. Pause poor keywords and review match types.",
            "View Paid Ads", "/paid-ads"
        )


def rule_ads_no_data():
    snap = (
        db.session.query(GoogleAdsSnapshot)
        .order_by(GoogleAdsSnapshot.snapshot_date.desc())
        .first()
    )
    if not snap:
        return _item(
            "warning", "ads", "ADS_NO_DATA",
            "No Google Ads data uploaded yet. Export the weekly performance report and upload it.",
            "Upload Report", "/paid-ads"
        )
    days = (date.today() - snap.snapshot_date).days
    if days >= 10:
        return _item(
            "warning", "ads", "ADS_NO_DATA",
            f"Google Ads data is {days} days old. Upload a fresh weekly report.",
            "Upload Report", "/paid-ads"
        )


def rule_booking_behind():
    today = date.today()
    if today.day < 15:
        return None
    month_name = today.strftime("%B").lower()
    target = config.MONTHLY_TARGETS.get(month_name, config.MONTHLY_TARGETS["default"])["bookings"]
    actual = db.session.query(ClioBooking).filter(ClioBooking.booking_date >= _month_start()).count()
    if actual < int(target * 0.6):
        return _item(
            "critical", "bookings", "BOOKING_BEHIND",
            f"Only {actual} bookings this month vs. {target} target. Review Ads spend and GMB conversion path.",
            "Log Booking", "/bookings"
        )


def rule_gmb_no_post_sd():
    row = (
        db.session.query(GmbInsight)
        .filter_by(location="SD")
        .order_by(GmbInsight.refreshed_at.desc())
        .first()
    )
    if not row:
        return None
    if row.last_post_date:
        days = (date.today() - row.last_post_date).days
        if days >= 7:
            return _item(
                "warning", "gmb", "GMB_NO_POST_SD",
                f"No GMB post for San Diego in {days} days. Post weekly to maintain local visibility.",
                "View GMB", "/gmb"
            )
    else:
        return _item(
            "warning", "gmb", "GMB_NO_POST_SD",
            "No GMB post date recorded for San Diego. Verify last post and set up weekly posting.",
            "View GMB", "/gmb"
        )


def rule_gmb_no_post_av():
    row = (
        db.session.query(GmbInsight)
        .filter_by(location="AV")
        .order_by(GmbInsight.refreshed_at.desc())
        .first()
    )
    if not row or not row.last_post_date:
        return None
    days = (date.today() - row.last_post_date).days
    if days >= 7:
        return _item(
            "warning", "gmb", "GMB_NO_POST_AV",
            f"No GMB post for Apple Valley in {days} days. Post weekly.",
            "View GMB", "/gmb"
        )


def rule_gmb_review_stale():
    rows = (
        db.session.query(GmbInsight)
        .filter_by(location="SD")
        .order_by(GmbInsight.refreshed_at.desc())
        .limit(2)
        .all()
    )
    if len(rows) < 2:
        return None
    latest, prior = rows[0], rows[1]
    days_apart = (latest.refreshed_at - prior.refreshed_at).days
    if days_apart >= 30 and latest.review_count == prior.review_count:
        return _item(
            "opportunity", "gmb", "GMB_REVIEW_STALE",
            f"SD review count ({latest.review_count}) unchanged in {days_apart}+ days. Send a review request to recent clients.",
            "View GMB", "/gmb"
        )


def rule_gsc_low_hanging():
    opportunities = (
        db.session.query(GscQuery)
        .filter(GscQuery.impressions > 100, GscQuery.position > 10)
        .order_by(GscQuery.impressions.desc())
        .limit(3)
        .all()
    )
    return [
        _item(
            "opportunity", "seo", "GSC_LOW_HANGING",
            f'"{q.query}" gets {q.impressions} impressions but ranks #{q.position:.0f}. '
            f'Optimize this page or write a dedicated post.',
            "View SEO", "/seo"
        )
        for q in opportunities
    ]


def rule_content_gap():
    try:
        with open(config.KEYWORDS_JSON_PATH) as f:
            archangel_kws = {k["keyword"].lower() for k in json.load(f)}
    except Exception:
        return None

    competitor_report = cr_conn.fetch()
    if not competitor_report.get("latest"):
        return None

    all_competitor_kws = competitor_report["latest"].get("keywords", [])
    gaps = [
        kw for kw in all_competitor_kws
        if (kw["keyword"].lower() not in archangel_kws
            and len(kw["keyword"].split()) >= 2
            and kw.get("businesses", 0) >= 2
            and kw.get("category") != "Other")
    ][:3]

    return [
        _item(
            "opportunity", "competitor", "CONTENT_GAP",
            f'{g["businesses"]} competitors use "{g["keyword"]}" ({g["category"]}) — no Archangel content. Add to pipeline.',
            "View Competitors", "/competitor-intel"
        )
        for g in gaps
    ]


def rule_content_velocity():
    today = date.today()
    posts_this_month = (
        db.session.query(WebflowPost)
        .filter(WebflowPost.is_draft == False, WebflowPost.publish_date >= _month_start())
        .count()
    )
    target = config.MONTHLY_TARGETS.get(
        today.strftime("%B").lower(), config.MONTHLY_TARGETS["default"]
    )["posts"]
    if posts_this_month < 4:
        return _item(
            "warning", "content", "CONTENT_VELOCITY",
            f"Only {posts_this_month} blog posts published this month (target: {target}). Run the content engine.",
            "View Pipeline", "/content-pipeline"
        )


def rule_keyword_queue_low():
    try:
        with open(config.KEYWORDS_JSON_PATH) as f:
            keywords = json.load(f)
    except Exception:
        return None
    generated = [k for k in keywords if k.get("status") == "generated"]
    pending = [k for k in keywords if k.get("status") == "pending"]
    if not generated:
        return _item(
            "opportunity", "content", "KEYWORD_QUEUE_LOW",
            f"No posts in 'generated' state. Run the content engine on {len(pending)} pending keywords.",
            "View Pipeline", "/content-pipeline"
        )


# ── Engine runner ─────────────────────────────────────────────────────────────

ALL_RULES = [
    rule_ads_high_cpa,
    rule_ads_no_data,
    rule_booking_behind,
    rule_gmb_no_post_sd,
    rule_gmb_no_post_av,
    rule_gmb_review_stale,
    rule_gsc_low_hanging,
    rule_content_gap,
    rule_content_velocity,
    rule_keyword_queue_low,
]


def run_all():
    raw_items = []
    for rule_fn in ALL_RULES:
        try:
            result = rule_fn()
            if result is None:
                continue
            if isinstance(result, list):
                raw_items.extend(result)
            else:
                raw_items.append(result)
        except Exception:
            pass

    db.session.execute(db.delete(ActionItem).where(ActionItem.is_dismissed == False))

    for item_data in raw_items:
        db.session.add(ActionItem(**item_data))

    db.session.commit()
    return len(raw_items)


def get_all(dismissed=False):
    q = db.session.query(ActionItem)
    if not dismissed:
        q = q.filter_by(is_dismissed=False)
    items = q.order_by(ActionItem.generated_at.desc()).all()
    items.sort(key=lambda x: SEVERITY_RANK.get(x.severity, 9))
    return items
