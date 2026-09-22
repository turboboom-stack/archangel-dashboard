"""
Home-page advisor briefing — a short, plain-English narrative summarizing how things
are going, generated from the same KPI/action-item data the rest of the dashboard uses.
Cached in DailyBriefing; regenerated when stale (see is_stale/STALE_HOURS) rather than
on every page load.
"""

import logging
from datetime import date, datetime, timedelta

import config
from engines import claude_client

logger = logging.getLogger(__name__)

STALE_HOURS = 6

SYSTEM_PROMPT = """You are a trusted advisor briefing the owner of Archangel Trust, a \
California estate planning and probate law firm (San Diego and Apple Valley), at the start \
of their day. You're given today's key numbers and any flagged action items.

Write 2-4 sentences, plain conversational English, no jargon, no bullet points, no markdown. \
Reference at least one real number naturally in a sentence (not as a separate stat callout). \
Lead with the most important thing — usually whether bookings are pacing on/ahead/behind \
target — then note one genuine win and one genuine concern if the data supports them. If \
there isn't a real win or concern, don't invent one — just report the state plainly. Never \
use exclamation points or hype language; this is a calm, factual, advisor tone.

Return only the briefing text, nothing else."""


def _build_prompt(target, bookings_count, month_name, live_cpa, action_items, clio):
    lines = [
        f"Today: {date.today().strftime('%B %d, %Y')}",
        f"{month_name} booking goal: {bookings_count} of {target['bookings']} so far.",
        f"Target CPA: under ${target['cpa_max']}.",
    ]
    if live_cpa is not None:
        lines.append(f"Current Google Ads CPA: ${live_cpa:.0f}.")
    if clio and clio.get("status") == "ok":
        lines.append(f"Active matters in Clio: {clio.get('active_matters', 0)}.")
        lines.append(f"Billed revenue, last 30 days: ${clio.get('revenue_30d', 0):,.0f}.")

    if action_items:
        lines.append("\nFlagged items today:")
        for item in action_items[:6]:
            lines.append(f"- [{item.severity}] {item.message}")
    else:
        lines.append("\nNo flagged action items today.")

    return "\n".join(lines)


def generate(app):
    """Generate and persist a fresh briefing. Returns (text, error_msg)."""
    if not config.ANTHROPIC_API_KEY:
        return None, "ANTHROPIC_API_KEY not configured"

    with app.app_context():
        from models import db, DailyBriefing, ActionItem, ClioBooking
        from connectors import google_ads_api_connector, clio_connector
        import config as cfg

        month = date.today().strftime("%B").lower()
        target = cfg.MONTHLY_TARGETS.get(month, cfg.MONTHLY_TARGETS["default"])
        month_start = date.today().replace(day=1)
        bookings_count = (
            db.session.query(ClioBooking)
            .filter(ClioBooking.booking_date >= month_start)
            .count()
        )

        ads_data = google_ads_api_connector.get_cached(days=14)
        live_cpa = None
        if ads_data["campaigns"]:
            total_spend = sum(c["spend"] for c in ads_data["campaigns"])
            total_conv = sum(c["conversions"] for c in ads_data["campaigns"])
            if total_conv > 0:
                live_cpa = total_spend / total_conv

        action_items = (
            db.session.query(ActionItem)
            .filter_by(is_dismissed=False)
            .order_by(ActionItem.generated_at.desc())
            .all()
        )
        clio_data = clio_connector.get_cached()

        prompt = _build_prompt(target, bookings_count, date.today().strftime("%B"), live_cpa, action_items, clio_data)

        try:
            text = claude_client.call(SYSTEM_PROMPT, prompt, max_tokens=300, cache_system=False)
        except Exception as e:
            logger.error(f"Briefing generation failed: {e}")
            return None, str(e)

        db.session.add(DailyBriefing(text=text))
        db.session.commit()
        return text, None


def get_or_generate(app):
    """Return the cached briefing if fresh, otherwise generate a new one inline."""
    from models import db, DailyBriefing

    latest = db.session.query(DailyBriefing).order_by(DailyBriefing.generated_at.desc()).first()
    if latest and (datetime.utcnow() - latest.generated_at) < timedelta(hours=STALE_HOURS):
        return latest.text, None

    text, error = generate(app)
    if text:
        return text, None
    # Generation failed — fall back to a stale cached copy if we have one, rather than nothing.
    return (latest.text if latest else None), error
