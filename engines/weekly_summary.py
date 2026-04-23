"""
Weekly CEO Summary Generator
Pulls the past 7 days of data across all sources, calls Claude,
and returns a formatted plain-text summary ready to paste into an email.
"""

import json
import logging
import urllib.request
from datetime import date, timedelta

import config

logger = logging.getLogger(__name__)
MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """You write concise weekly performance summaries for the CEO of Archangel Trust, \
a California estate planning and probate law firm (San Diego + Apple Valley). \
The CEO is not a marketer — write in plain business language, no jargon.

Format the summary exactly like this (use these section headers, keep it tight):

WEEK ENDING [date]
──────────────────────────────────────────

PERFORMANCE AT A GLANCE
[3-5 bullet points with the most important numbers: bookings, ad spend, CPA, GMB calls, etc.]

ACTIONS TAKEN THIS WEEK
[Bullet list of what the marketing team implemented. If nothing, say "No changes implemented this week."]

WINS
[2-3 bullets on what worked. Be specific with numbers.]

CONCERNS
[2-3 bullets on what underperformed or needs attention. Be direct.]

RECOMMENDATIONS
[2-3 concrete next steps, ranked by impact.]

CHECK-IN DATES
[Bullet list: what to review and when, based on changes made.]

Keep the whole summary under 400 words. No emojis. No markdown formatting — use plain dashes for bullets."""


def _call_claude(api_key, prompt):
    payload = {
        "model": MODEL,
        "max_tokens": 1024,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": prompt}],
    }
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(payload).encode(),
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())
    return data["content"][0]["text"].strip()


def _gather_data(app):
    """Pull one week of data from all sources. Returns a dict of facts."""
    from models import db, GoogleAdsSnapshot, GoogleAdsKeyword, AdRecommendation, ClioBooking
    from connectors import gmb_connector, gsc_connector, webflow_connector

    today = date.today()
    week_ago = today - timedelta(days=7)
    facts = {"week_ending": today.isoformat(), "week_start": week_ago.isoformat()}

    with app.app_context():
        # ── Bookings ──────────────────────────────────────────────────────────
        month_start = today.replace(day=1)
        bookings_week = (
            db.session.query(ClioBooking)
            .filter(ClioBooking.booking_date >= week_ago)
            .count()
        )
        bookings_month = (
            db.session.query(ClioBooking)
            .filter(ClioBooking.booking_date >= month_start)
            .count()
        )
        target = config.MONTHLY_TARGETS.get(
            today.strftime("%B").lower(), config.MONTHLY_TARGETS["default"]
        )
        facts["bookings_this_week"] = bookings_week
        facts["bookings_this_month"] = bookings_month
        facts["booking_target"] = target["bookings"]
        facts["cpa_target"] = target["cpa_max"]

        # ── Google Ads ────────────────────────────────────────────────────────
        snaps = (
            db.session.query(GoogleAdsSnapshot)
            .filter(GoogleAdsSnapshot.snapshot_date >= week_ago)
            .order_by(GoogleAdsSnapshot.snapshot_date.desc())
            .all()
        )
        if snaps:
            latest = snaps[0]
            facts["ads_spend"] = round(latest.total_spend, 2)
            facts["ads_clicks"] = latest.total_clicks
            facts["ads_conversions"] = round(latest.total_conversions, 1)
            facts["ads_cpa"] = round(latest.cpa, 2)
            facts["ads_impressions"] = latest.total_impressions
            facts["ads_period"] = (
                f"{latest.period_start} to {latest.period_end}"
                if latest.period_start and latest.period_end
                else latest.snapshot_date.isoformat()
            )
            # Top and worst keywords by CPA
            kws = (
                db.session.query(GoogleAdsKeyword)
                .filter_by(snapshot_id=latest.id)
                .filter(GoogleAdsKeyword.clicks > 0)
                .all()
            )
            if kws:
                by_conv = sorted(kws, key=lambda k: k.conversions, reverse=True)
                top3 = [f'"{k.keyword}" ({k.conversions:.0f} conv, ${k.cost:.0f} spend)' for k in by_conv[:3]]
                worst = [
                    k for k in kws
                    if k.cost > 20 and k.conversions == 0
                ]
                worst3 = [f'"{k.keyword}" (${k.cost:.0f} spent, 0 conv)' for k in sorted(worst, key=lambda k: k.cost, reverse=True)[:3]]
                facts["top_keywords"] = top3
                facts["zero_conv_keywords"] = worst3
        else:
            facts["ads_note"] = "No Google Ads data uploaded this week."

        # ── AdRecommendations ─────────────────────────────────────────────────
        implemented = (
            db.session.query(AdRecommendation)
            .filter(AdRecommendation.status == "implemented")
            .filter(AdRecommendation.implemented_at >= week_ago)
            .order_by(AdRecommendation.implemented_at)
            .all()
        )
        facts["implemented_changes"] = [
            {
                "title": r.title,
                "notes": r.implementation_notes or "",
                "follow_up_date": r.follow_up_date.isoformat() if r.follow_up_date else None,
            }
            for r in implemented
        ]

        pending_followup = (
            db.session.query(AdRecommendation)
            .filter(AdRecommendation.status == "implemented")
            .filter(AdRecommendation.follow_up_date != None)
            .filter(AdRecommendation.follow_up_notes == None)
            .all()
        )
        facts["pending_followups"] = [
            {"title": r.title, "follow_up_date": r.follow_up_date.isoformat()}
            for r in pending_followup
        ]

        approved_pending = (
            db.session.query(AdRecommendation)
            .filter_by(status="approved")
            .count()
        )
        facts["approved_not_yet_implemented"] = approved_pending

        # ── GMB ───────────────────────────────────────────────────────────────
        gmb = gmb_connector.get_cached()
        sd = gmb.get("SD", {})
        av = gmb.get("AV", {})
        if sd:
            facts["gmb_sd_calls"] = getattr(sd, "calls", sd.get("calls", 0) if isinstance(sd, dict) else 0)
            facts["gmb_sd_web_clicks"] = getattr(sd, "website_clicks", sd.get("website_clicks", 0) if isinstance(sd, dict) else 0)
        if av:
            facts["gmb_av_calls"] = getattr(av, "calls", av.get("calls", 0) if isinstance(av, dict) else 0)
            facts["gmb_av_web_clicks"] = getattr(av, "website_clicks", av.get("website_clicks", 0) if isinstance(av, dict) else 0)

        # ── GSC ───────────────────────────────────────────────────────────────
        gsc = gsc_connector.get_cached()
        summary = gsc.get("summary")
        if summary:
            facts["gsc_clicks"] = getattr(summary, "total_clicks", 0)
            facts["gsc_impressions"] = getattr(summary, "total_impressions", 0)
            facts["gsc_avg_position"] = round(getattr(summary, "avg_position", 0), 1)

        # ── Webflow ───────────────────────────────────────────────────────────
        wf = webflow_connector.get_cached(month_start=month_start)
        facts["posts_this_month"] = wf.get("published_this_month", 0)

        # ── GA4 ───────────────────────────────────────────────────────────────
        from connectors import ga4_connector
        ga4 = ga4_connector.get_cached()
        if ga4:
            facts["ga4_sessions"]   = ga4["sessions"]
            facts["ga4_new_users"]  = ga4["new_users"]
            facts["ga4_bounce"]     = ga4["bounce_rate"]
            facts["ga4_avg_dur"]    = ga4["avg_session_duration"]
            facts["ga4_conversions"] = ga4["conversions"]
            facts["ga4_channels"]   = ga4["channels"]
            top = ga4["top_pages"][:3]
            facts["ga4_top_pages"]  = [f"{p['page']} ({p['sessions']} sessions)" for p in top]

    return facts


def _build_prompt(facts):
    lines = [f"Generate a weekly CEO summary for the week ending {facts['week_ending']}.\n"]

    lines.append("## Data\n")

    # Bookings
    lines.append(f"Bookings this week: {facts.get('bookings_this_week', 'unknown')}")
    lines.append(f"Bookings this month: {facts.get('bookings_this_month', 'unknown')} (target: {facts.get('booking_target', 'unknown')})")

    # Ads
    if "ads_spend" in facts:
        period = facts.get("ads_period", "")
        lines.append(f"\nGoogle Ads ({period}):")
        lines.append(f"  Spend: ${facts['ads_spend']}")
        lines.append(f"  Clicks: {facts['ads_clicks']}, Conversions: {facts['ads_conversions']}, CPA: ${facts['ads_cpa']} (target: <${facts['cpa_target']})")
        lines.append(f"  Impressions: {facts['ads_impressions']}")
        if facts.get("top_keywords"):
            lines.append(f"  Top converting keywords: {', '.join(facts['top_keywords'])}")
        if facts.get("zero_conv_keywords"):
            lines.append(f"  Zero-conversion keywords (wasted spend): {', '.join(facts['zero_conv_keywords'])}")
    elif "ads_note" in facts:
        lines.append(f"\nGoogle Ads: {facts['ads_note']}")

    # GMB
    if "gmb_sd_calls" in facts or "gmb_av_calls" in facts:
        lines.append(f"\nGMB — San Diego: {facts.get('gmb_sd_calls', '?')} calls, {facts.get('gmb_sd_web_clicks', '?')} website clicks")
        lines.append(f"GMB — Apple Valley: {facts.get('gmb_av_calls', '?')} calls, {facts.get('gmb_av_web_clicks', '?')} website clicks")

    # GSC
    if "gsc_clicks" in facts:
        lines.append(f"\nOrganic search: {facts['gsc_clicks']} clicks, {facts['gsc_impressions']} impressions, avg position {facts['gsc_avg_position']}")

    # Content
    lines.append(f"\nBlog posts published this month: {facts.get('posts_this_month', 0)}")

    # GA4
    if "ga4_sessions" in facts:
        dur = facts["ga4_avg_dur"]
        lines.append(f"\nSite Analytics (last 7 days):")
        lines.append(f"  Sessions: {facts['ga4_sessions']}, New users: {facts['ga4_new_users']}")
        lines.append(f"  Avg session: {int(dur // 60)}m {int(dur % 60)}s, Bounce rate: {facts['ga4_bounce']}%")
        if facts.get("ga4_conversions"):
            for ev, count in facts["ga4_conversions"].items():
                lines.append(f"  {ev}: {count}")
        if facts.get("ga4_channels"):
            ch = ", ".join(f"{k}: {v}" for k, v in facts["ga4_channels"].items())
            lines.append(f"  Traffic: {ch}")
        if facts.get("ga4_top_pages"):
            lines.append(f"  Top pages: {', '.join(facts['ga4_top_pages'])}")

    # Changes made
    lines.append("\n## Changes Implemented This Week")
    changes = facts.get("implemented_changes", [])
    if changes:
        for c in changes:
            fu = f" (check results: {c['follow_up_date']})" if c.get("follow_up_date") else ""
            lines.append(f"- {c['title']}: {c['notes']}{fu}")
    else:
        lines.append("- None")

    # Pending follow-ups
    followups = facts.get("pending_followups", [])
    if followups:
        lines.append("\n## Upcoming Check-In Dates")
        for f in followups:
            lines.append(f"- {f['follow_up_date']}: Review results of \"{f['title']}\"")

    n = facts.get("approved_not_yet_implemented", 0)
    if n:
        lines.append(f"\nNote: {n} approved recommendation(s) not yet implemented.")

    return "\n".join(lines)


def generate(app):
    """Returns (summary_text, error_msg)."""
    api_key = config.ANTHROPIC_API_KEY
    if not api_key:
        return None, "ANTHROPIC_API_KEY not configured"
    try:
        facts = _gather_data(app)
        prompt = _build_prompt(facts)
        logger.info("Generating weekly CEO summary...")
        text = _call_claude(api_key, prompt)
        return text, None
    except Exception as e:
        logger.error(f"Weekly summary error: {e}")
        return None, str(e)
