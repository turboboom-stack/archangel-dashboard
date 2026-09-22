"""
Opportunities — "non-traditional" idea generator. The Opportunities page already shows
the conventional signals (organic ranking gaps from Search Console, competitor keyword
gaps, the blog keyword queue) as plain tables; this module's job is specifically to look
past those and surface angles that don't show up in any of those tables on their own —
underused ad formats/extensions, day-parting, seasonal/local tie-ins, channels besides
search, LSA positioning, etc.

Runs in a background thread + poll, same pattern as engines/campaign_builder.py — this
is a genuine per-idea generation call (up to ~8 ideas with rationale) and shouldn't share
a request thread that a proxy might time out.
"""

import json
import logging
import threading

import config
from engines import claude_client
from engines.ads_skills import base as skills_base

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a marketing strategist for Archangel Trust, a California estate \
planning and probate law firm (San Diego and Apple Valley), looking for growth opportunities \
that a conventional keyword/competitor report would NOT surface — the client already has \
that data in front of them separately. Your job is specifically the non-obvious angles:

- Underused Google Ads formats/extensions (sitelinks, callouts, structured snippets, lead \
  form extensions, call extensions)
- Timing opportunities (day-parting based on when consultations actually happen, seasonal or \
  local-event tie-ins relevant to estate planning — tax season, back-to-school guardianship \
  questions, etc.)
- Channels beyond search (YouTube/display remarketing to past site visitors, Local Services \
  Ads positioning, community sponsorship or local partnerships as a non-ad lead channel)
- Structural gaps implied by the data given (e.g. a query ranking well organically that has \
  no corresponding paid keyword, or a competitor keyword category with no matching service page)

Do not just restate what's already in the data as a table row — each idea should require a \
specific action the client hasn't already been shown elsewhere. Only propose ideas you can \
justify from the data provided or well-established local-services-marketing practice — don't \
invent fake statistics.

Return a JSON array of 5-8 idea objects, each with:
- "category": one of "ad_format", "timing", "channel", "structural_gap", "local"
- "title": short, specific (under 80 chars)
- "description": what to actually do (2-3 sentences)
- "rationale": why this is worth trying, referencing the data given where possible

Return only the JSON array, no other text."""


def _build_prompt(gsc_data, seo_data, report_data, kw_data):
    rules = skills_base.business_rules_block()
    lines = [rules, "", "## Current Signals"]

    if gsc_data and gsc_data.get("summary"):
        s = gsc_data["summary"]  # GscSummary ORM object, not a dict
        lines.append(f"- Organic search (28d): {s.total_clicks or 0} clicks, "
                     f"avg position #{(s.avg_position or 0):.1f}")
    top_queries = (gsc_data or {}).get("queries", [])[:10]
    if top_queries:
        lines.append("- Top organic queries: " + ", ".join(q.query for q in top_queries))

    if seo_data and seo_data.get("aggregated"):
        top_competitor_kws = seo_data["aggregated"][:15]
        lines.append("- Top competitor keywords (category — sites using): " +
                     ", ".join(f"{k.get('keyword')} ({k.get('category')})" for k in top_competitor_kws))

    if report_data and report_data.get("new_this_week"):
        new_kws = report_data["new_this_week"][:10]
        lines.append("- New competitor keywords this week: " +
                     ", ".join(k.get("keyword", str(k)) if isinstance(k, dict) else str(k) for k in new_kws))

    if kw_data and kw_data.get("counts"):
        lines.append(f"- Content keyword queue: {kw_data['counts']}")

    return "\n".join(lines)


def _generate_sync(app):
    if not config.ANTHROPIC_API_KEY:
        return "ANTHROPIC_API_KEY not configured"

    with app.app_context():
        from models import db, OpportunityIdea
        from connectors import gsc_connector, seo_db_connector, competitor_reports_connector, keywords_connector

        gsc_data = gsc_connector.get_cached()
        seo_data = seo_db_connector.fetch()
        report_data = competitor_reports_connector.fetch()
        kw_data = keywords_connector.fetch()

        prompt = _build_prompt(gsc_data, seo_data, report_data, kw_data)

        try:
            ideas = claude_client.call_json(SYSTEM_PROMPT, prompt, max_tokens=2048, cache_system=False)
        except Exception as e:
            logger.error(f"Opportunity finder failed: {e}")
            return str(e)

        if not isinstance(ideas, list):
            return "Unexpected response shape from Claude"

        # Replace the previous batch — these are meant to reflect current signals, not accumulate.
        db.session.query(OpportunityIdea).delete()
        for idea in ideas:
            db.session.add(OpportunityIdea(
                category=idea.get("category", "structural_gap"),
                title=idea.get("title", ""),
                description=idea.get("description", ""),
                rationale=idea.get("rationale", ""),
            ))
        db.session.commit()
        return None


_lock = threading.Lock()
_running = False
_last_error = None


def generate_background(app):
    global _running, _last_error
    if not _lock.acquire(blocking=False):
        return False
    _running = True
    _last_error = None

    def _worker():
        global _running, _last_error
        try:
            _last_error = _generate_sync(app)
        finally:
            _running = False
            _lock.release()

    threading.Thread(target=_worker, daemon=True).start()
    return True


def is_running():
    return _running


def get_last_error():
    return _last_error
