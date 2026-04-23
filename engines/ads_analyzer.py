"""
Ads Strategy Analyzer
Reads Google Ads performance data from the DB, calls Claude API,
and writes AdRecommendation rows directly to the DB.
"""

import json
import logging
import threading
import urllib.request
import urllib.error
from datetime import datetime, date, timedelta

import config

logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-6"
CALENDLY_URL = "https://calendly.com/archangel-trust-cmartin/consultation"

SYSTEM_PROMPT = """You are a Google Ads strategist managing campaigns for Archangel Trust, \
an estate planning and probate law firm in California. Locations: San Diego and Apple Valley (High Desert). \
Target CPA is under $150. Primary goal: drive consultation bookings via Calendly.

You analyze performance data and generate specific, actionable recommendations. \
Each recommendation must be directly implementable in Google Ads.

Return a JSON array of 3-5 recommendation objects. Each object must have:
- "category": one of "budget", "keywords", "bids", "negatives", "copy"
- "priority": one of "high", "medium", "low"
- "title": short action title (under 80 chars)
- "recommendation": what to do, written as a clear instruction (1-2 sentences)
- "rationale": data-backed reasoning referencing specific numbers from the data provided

Return only the JSON array, no other text."""


def _call_claude(api_key, user_prompt):
    payload = {
        "model": MODEL,
        "max_tokens": 1024,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": user_prompt}],
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
    with urllib.request.urlopen(req, timeout=90) as resp:
        data = json.loads(resp.read())
    return data["content"][0]["text"].strip()


def _build_prompt(snapshots, keywords):
    lines = ["## Google Ads Performance Data\n"]

    if snapshots:
        lines.append("### Period Snapshots (most recent first)")
        for s in snapshots[:6]:
            period = ""
            if s.period_start and s.period_end:
                period = f"{s.period_start.strftime('%b %d')}–{s.period_end.strftime('%b %d')}"
            lines.append(
                f"- {period}: spend=${s.total_spend:.2f}, clicks={s.total_clicks}, "
                f"conv={s.total_conversions:.1f}, CPA=${s.cpa:.2f}, impr={s.total_impressions}"
            )
    else:
        lines.append("No snapshot data available yet.")

    if keywords:
        lines.append("\n### Top Keywords (most recent snapshot)")
        for kw in keywords[:20]:
            lines.append(
                f"- \"{kw.keyword}\" [{kw.match_type}] | campaign: {kw.campaign} | "
                f"clicks={kw.clicks}, conv={kw.conversions:.1f}, cost=${kw.cost:.2f}, CPA=${kw.cpa:.2f}"
            )

    target = config.MONTHLY_TARGETS.get(date.today().strftime("%B").lower(), config.MONTHLY_TARGETS["default"])
    lines.append(f"\n### Targets")
    lines.append(f"- Target CPA: under ${target['cpa_max']}")
    lines.append(f"- Monthly booking goal: {target['bookings']}")
    lines.append(f"\nToday: {date.today().isoformat()}")

    return "\n".join(lines)


def run_analysis(app):
    """Run analysis in the given Flask app context. Returns (count, error_msg)."""
    api_key = config.ANTHROPIC_API_KEY
    if not api_key:
        return 0, "ANTHROPIC_API_KEY not configured"

    with app.app_context():
        from models import db, GoogleAdsSnapshot, GoogleAdsKeyword, AdRecommendation

        snapshots = (
            db.session.query(GoogleAdsSnapshot)
            .order_by(GoogleAdsSnapshot.snapshot_date.desc())
            .limit(10)
            .all()
        )

        keywords = []
        if snapshots:
            latest_id = snapshots[0].id
            keywords = (
                db.session.query(GoogleAdsKeyword)
                .filter_by(snapshot_id=latest_id)
                .order_by(GoogleAdsKeyword.cost.desc())
                .limit(30)
                .all()
            )

        prompt = _build_prompt(snapshots, keywords)
        logger.info("Calling Claude for ad strategy analysis...")

        try:
            raw = _call_claude(api_key, prompt)
        except Exception as e:
            logger.error(f"Claude API error: {e}")
            return 0, str(e)

        # Strip markdown fences if present
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
            text = text.rsplit("```", 1)[0].strip()

        try:
            recs = json.loads(text)
        except json.JSONDecodeError as e:
            logger.error(f"Could not parse Claude response as JSON: {e}\nRaw: {raw[:500]}")
            return 0, f"Invalid JSON from Claude: {e}"

        version = f"ads-analyzer-{date.today().isoformat()}"
        count = 0
        for r in recs:
            rec = AdRecommendation(
                category=r.get("category", "general"),
                priority=r.get("priority", "medium"),
                title=r.get("title", ""),
                recommendation=r.get("recommendation", ""),
                rationale=r.get("rationale", ""),
                agent_version=version,
            )
            db.session.add(rec)
            count += 1

        db.session.commit()
        logger.info(f"Added {count} recommendations to DB.")
        return count, None


_analysis_lock = threading.Lock()
_analysis_running = False


def run_analysis_background(app):
    """Spawn a background thread to run analysis. Returns False if already running."""
    global _analysis_running
    if not _analysis_lock.acquire(blocking=False):
        return False
    _analysis_running = True

    def _worker():
        global _analysis_running
        try:
            run_analysis(app)
        finally:
            _analysis_running = False
            _analysis_lock.release()

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    return True


def is_running():
    return _analysis_running
