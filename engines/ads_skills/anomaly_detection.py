"""Flags daily spend/conversion moves >2 standard deviations from the trailing mean.
Deterministic (no LLM call) — needs live Ads API daily data (Phase 1); no-ops on
manual-upload snapshot data, which isn't daily-granular enough for this check.
Writes directly to ActionItem for immediate surfacing, plus a paired recommendation
so it also shows up in the /ad-strategy review queue."""

import statistics
from datetime import date, timedelta

from engines.ads_skills import base
from models import db, GoogleAdsCampaignDaily, ActionItem

SKILL_ID = "anomaly_detection"

STD_DEV_THRESHOLD = 2


def _flag_outliers(values_by_date):
    values = list(values_by_date.values())
    if len(values) < 5:
        return []
    mean = statistics.mean(values)
    stdev = statistics.pstdev(values)
    if stdev == 0:
        return []
    return [
        (d, v, (v - mean) / stdev)
        for d, v in values_by_date.items()
        if abs((v - mean) / stdev) >= STD_DEV_THRESHOLD
    ]


def run():
    if not base.has_live_data():
        return []

    since = date.today() - timedelta(days=21)
    rows = db.session.query(GoogleAdsCampaignDaily).filter(GoogleAdsCampaignDaily.date >= since).all()
    if not rows:
        return []

    spend_by_date, conv_by_date = {}, {}
    for r in rows:
        spend_by_date[r.date] = spend_by_date.get(r.date, 0) + r.spend
        conv_by_date[r.date] = conv_by_date.get(r.date, 0) + r.conversions

    items = []
    for label, series in [("spend", spend_by_date), ("conversions", conv_by_date)]:
        for d, v, z in _flag_outliers(series):
            direction = "spiked" if z > 0 else "dropped"
            msg = f"Daily {label} {direction} to {v:.2f} on {d.isoformat()} ({z:+.1f} std dev from the 3-week mean)."
            db.session.add(ActionItem(
                severity="warning", category="ads", rule_id=f"ADS_ANOMALY_{label.upper()}",
                message=msg, cta_text="View Paid Ads", cta_url="/performance",
            ))
            items.append({
                "category": "alerts",
                "priority": "high",
                "title": f"Anomaly: daily {label} {direction} on {d.isoformat()}",
                "recommendation": f"Investigate what changed on {d.isoformat()} — check for a "
                                   f"budget/bid change, tracking issue, or seasonal event.",
                "rationale": msg,
            })
    if items:
        db.session.commit()
    return items
