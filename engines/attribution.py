"""
Lead attribution: ties ClioBooking rows to Google Ads campaigns/keywords via
gclid/UTM params, and de-dupes across the three paths that can create a booking
row for the same real person — /webhook/clio, /webhook/calendly, and
clio_connector.fetch()'s own new-contacts sync.
"""

from datetime import date, timedelta

import config
from models import db, ClioBooking

MATCH_WINDOW_DAYS = 14


def location_for(text):
    """Match a campaign/source string against config.GOOGLE_ADS_LOCATION_MAP."""
    if not text:
        return ""
    haystack = f" {text.lower()} "
    for needle, loc in config.GOOGLE_ADS_LOCATION_MAP.items():
        if needle in haystack:
            return loc
    return ""


def upsert_booking(email=None, phone=None, gclid=None, source=None, campaign=None,
                    notes=None, booking_date=None, clio_id=None):
    """
    Find an existing ClioBooking for the same person (by clio_id, then by email within
    MATCH_WINDOW_DAYS) and fill in tracking fields it's missing, rather than inserting
    a duplicate row. Creates a new row only if no match is found.

    Returns (booking, created: bool).
    """
    booking_date = booking_date or date.today()

    existing = None
    if clio_id:
        existing = db.session.query(ClioBooking).filter_by(clio_id=clio_id).first()
    if not existing and email:
        window_start = booking_date - timedelta(days=MATCH_WINDOW_DAYS)
        existing = (
            db.session.query(ClioBooking)
            .filter(db.func.lower(ClioBooking.email) == email.lower())
            .filter(ClioBooking.booking_date >= window_start)
            .order_by(ClioBooking.entered_at.desc())
            .first()
        )

    loc = location_for(campaign) or location_for(source)

    if existing:
        if clio_id and not existing.clio_id:
            existing.clio_id = clio_id
        if gclid and not existing.gclid:
            existing.gclid = gclid
        if campaign and not existing.campaign:
            existing.campaign = campaign
        if source and (not existing.source or existing.source == "clio_grow"):
            existing.source = source
        if phone and not existing.phone:
            existing.phone = phone
        if loc and not existing.location:
            existing.location = loc
        if notes and not existing.notes:
            existing.notes = notes
        db.session.commit()
        return existing, False

    booking = ClioBooking(
        booking_date=booking_date,
        location=loc,
        source=source or "",
        campaign=campaign or "",
        notes=notes or "",
        gclid=gclid or None,
        email=email or None,
        phone=phone or None,
        clio_id=clio_id,
    )
    db.session.add(booking)
    db.session.commit()
    return booking, True


def summary(days=30):
    """gclid coverage % and attributed CPA (Ads spend / attributed bookings) in-window."""
    from connectors import google_ads_connector

    since = date.today() - timedelta(days=days)
    bookings = db.session.query(ClioBooking).filter(ClioBooking.booking_date >= since).all()
    total = len(bookings)
    attributed = sum(1 for b in bookings if b.gclid)
    coverage = round(100 * attributed / total, 1) if total else 0.0

    spend = 0.0
    ads_data = google_ads_connector.get_cached()
    for snap in ads_data["snapshots"]:
        if snap.period_end and snap.period_end >= since:
            spend += snap.total_spend

    return {
        "days": days,
        "total_bookings": total,
        "attributed_bookings": attributed,
        "gclid_coverage_pct": coverage,
        "spend_in_window": round(spend, 2),
        "attributed_cpa": round(spend / attributed, 2) if attributed else None,
    }
