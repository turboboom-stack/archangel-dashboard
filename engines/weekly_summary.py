"""
Bi-weekly CEO Marketing Update Generator
Pulls the past 14 days of data across all sources, calls Claude,
and returns a plain-text email-ready update for the CEO.
"""

import json
import logging
import urllib.request
from datetime import date, timedelta

import config

logger = logging.getLogger(__name__)
MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """You write bi-weekly marketing updates for the CEO of Archangel Trust, \
a California estate planning and probate law firm with offices in San Diego and Apple Valley.

The CEO is not a marketer. Write in plain, conversational business English — no acronyms, \
no jargon, no technical terms. If you mention a number, give it one short phrase of context \
so it means something ("51 people clicked our ad and filled out the contact form" not \
"51 ad conversion events recorded"). Lead with what matters to a business owner: \
are we getting leads? Are bookings growing?

Highlight positive momentum prominently. When something is up week-over-week, say so clearly \
and explain briefly why it matters for the business. Be honest about concerns but frame them \
constructively — one line, no dwelling.

Format exactly like this (plain text, dashes for bullets, no markdown):

[Month] Marketing Update — [date range]
──────────────────────────────────────────

BUSINESS SNAPSHOT
[2-3 sentences. How many bookings this period, how close to goal, and one-line overall read \
on whether momentum is positive or flat. Make this feel like a trusted advisor talking, \
not a report.]

WHAT'S GROWING
[3-4 bullets on positive trends — website visitors, organic search growth, ad leads, \
people finding us online. Use plain numbers and explain what they mean for the business. \
If week-over-week data is available, lead with the growth percentage and what drove it.]

WHAT WE DID THIS PERIOD
[Bullet list of changes made. Write for a non-marketer: what was changed and why it matters \
for getting more leads or bookings. If nothing, say "No changes this period."]

WHAT TO WATCH
[1-2 bullets only. Things that directly affect leads or revenue. Skip anything purely technical.]

CONTENT PUBLISHED
[List each blog post title on its own line with a dash. Just titles, no commentary.]

WHAT'S NEXT
[2-3 concrete next steps with a one-line business rationale for each.]

Keep the whole update under 500 words. No emojis. Plain text only."""


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


def _pct_change(current, previous):
    """Return a formatted % change string, e.g. '+18%' or '-5%'."""
    if not previous:
        return None
    change = round((current - previous) / previous * 100)
    return f"+{change}%" if change >= 0 else f"{change}%"


def _gather_data(app):
    """Pull 14 days of data from all sources. Returns a dict of facts."""
    from models import db, GoogleAdsSnapshot, GoogleAdsKeyword, AdRecommendation, ClioBooking, Ga4Summary, WebflowPost
    from connectors import gmb_connector, gsc_connector, webflow_connector

    today = date.today()
    week_ago = today - timedelta(days=14)
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

        # ── GA4 (current + previous period for week-over-week) ────────────────
        from connectors import ga4_connector
        ga4 = ga4_connector.get_cached()
        if ga4:
            facts["ga4_sessions"]    = ga4["sessions"]
            facts["ga4_new_users"]   = ga4["new_users"]
            facts["ga4_bounce"]      = ga4["bounce_rate"]
            facts["ga4_avg_dur"]     = ga4["avg_session_duration"]
            facts["ga4_conversions"] = ga4["conversions"]
            facts["ga4_channels"]    = ga4["channels"]
            top = ga4["top_pages"][:3]
            facts["ga4_top_pages"]   = [f"{p['page']} ({p['sessions']} sessions)" for p in top]

            # Compare to previous snapshot for growth context
            prev = (
                db.session.query(Ga4Summary)
                .order_by(Ga4Summary.refreshed_at.desc())
                .offset(1)
                .first()
            )
            if prev:
                facts["ga4_sessions_prev"]  = prev.sessions
                facts["ga4_new_users_prev"] = prev.new_users
                facts["ga4_sessions_change"] = _pct_change(ga4["sessions"], prev.sessions)
                facts["ga4_new_users_change"] = _pct_change(ga4["new_users"], prev.new_users)
                conv_total = sum(ga4["conversions"].values())
                prev_conv = sum(json.loads(prev.conversions_json or "{}").values())
                facts["ga4_conversions_total"] = conv_total
                facts["ga4_conversions_change"] = _pct_change(conv_total, prev_conv)

        # ── Recently published blog posts ─────────────────────────────────────
        recent_posts = (
            db.session.query(WebflowPost)
            .filter(
                WebflowPost.is_draft == False,
                WebflowPost.publish_date >= week_ago,
            )
            .order_by(WebflowPost.publish_date.desc())
            .all()
        )
        facts["recent_posts"] = [p.name for p in recent_posts]

    return facts


def _build_prompt(facts):
    lines = [
        f"Generate a bi-weekly marketing update for the period ending {facts['week_ending']} "
        f"(covering {facts['week_start']} to {facts['week_ending']}).\n"
    ]
    lines.append("## Data for this period\n")

    # Bookings
    lines.append(f"Consultation bookings this period: {facts.get('bookings_this_week', 'unknown')}")
    lines.append(f"Bookings this month so far: {facts.get('bookings_this_month', 'unknown')} (monthly goal: {facts.get('booking_target', 'unknown')})")

    # GA4 website analytics
    if "ga4_sessions" in facts:
        dur = facts["ga4_avg_dur"]
        lines.append(f"\nWebsite traffic (last 14 days):")
        sess_change = facts.get("ga4_sessions_change")
        new_change  = facts.get("ga4_new_users_change")
        lines.append(f"  Total website visitors: {facts['ga4_sessions']}" + (f" ({sess_change} vs prior period)" if sess_change else ""))
        lines.append(f"  New visitors: {facts['ga4_new_users']}" + (f" ({new_change} vs prior period)" if new_change else ""))
        lines.append(f"  Average time on site: {int(dur // 60)}m {int(dur % 60)}s")
        lines.append(f"  Bounce rate: {facts['ga4_bounce']}%")
        conv_total = facts.get("ga4_conversions_total")
        conv_change = facts.get("ga4_conversions_change")
        if conv_total is not None:
            lines.append(f"  Total lead actions (contact form fills, ad conversions): {conv_total}" + (f" ({conv_change} vs prior period)" if conv_change else ""))
        if facts.get("ga4_conversions"):
            for ev, count in facts["ga4_conversions"].items():
                lines.append(f"    - {ev}: {count}")
        if facts.get("ga4_channels"):
            ch = ", ".join(f"{k}: {v} visitors" for k, v in facts["ga4_channels"].items())
            lines.append(f"  Where visitors came from: {ch}")
        if facts.get("ga4_top_pages"):
            lines.append(f"  Most visited pages: {', '.join(facts['ga4_top_pages'])}")

    # Google Ads
    if "ads_spend" in facts:
        lines.append(f"\nPaid advertising:")
        lines.append(f"  Ad spend: ${facts['ads_spend']}")
        lines.append(f"  People who clicked our ads: {facts['ads_clicks']}")
        lines.append(f"  Leads generated from ads: {facts['ads_conversions']}")
        lines.append(f"  Cost per lead: ${facts['ads_cpa']} (target: under ${facts['cpa_target']})")
        if facts.get("top_keywords"):
            lines.append(f"  Best performing searches: {', '.join(facts['top_keywords'])}")
        if facts.get("zero_conv_keywords"):
            lines.append(f"  Searches with no leads (potential waste): {', '.join(facts['zero_conv_keywords'])}")
    elif "ads_note" in facts:
        lines.append(f"\nPaid advertising: {facts['ads_note']}")

    # Organic search
    if "gsc_clicks" in facts:
        lines.append(f"\nOrganic Google search (people finding us without ads):")
        lines.append(f"  Clicks from Google: {facts['gsc_clicks']}")
        lines.append(f"  Times we appeared in search results: {facts['gsc_impressions']}")
        lines.append(f"  Average ranking position: #{facts['gsc_avg_position']}")

    # GMB
    if "gmb_sd_calls" in facts or "gmb_av_calls" in facts:
        lines.append(f"\nGoogle Business Profile (people finding us on Google Maps):")
        lines.append(f"  San Diego — calls: {facts.get('gmb_sd_calls', '?')}, website clicks: {facts.get('gmb_sd_web_clicks', '?')}")
        lines.append(f"  Apple Valley — calls: {facts.get('gmb_av_calls', '?')}, website clicks: {facts.get('gmb_av_web_clicks', '?')}")

    # Blog content
    lines.append(f"\nBlog posts published this month: {facts.get('posts_this_month', 0)}")
    recent = facts.get("recent_posts", [])
    if recent:
        lines.append(f"Posts published this period:")
        for title in recent:
            lines.append(f"  - {title}")
    else:
        lines.append("No new posts published this period.")

    # Changes made
    lines.append("\n## Changes made this period")
    changes = facts.get("implemented_changes", [])
    if changes:
        for c in changes:
            fu = f" (check results by: {c['follow_up_date']})" if c.get("follow_up_date") else ""
            lines.append(f"- {c['title']}: {c['notes']}{fu}")
    else:
        lines.append("- None")

    followups = facts.get("pending_followups", [])
    if followups:
        lines.append("\n## Upcoming check-in dates")
        for f in followups:
            lines.append(f"- {f['follow_up_date']}: review \"{f['title']}\"")

    n = facts.get("approved_not_yet_implemented", 0)
    if n:
        lines.append(f"\nNote: {n} approved change(s) are queued but not yet live.")

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
