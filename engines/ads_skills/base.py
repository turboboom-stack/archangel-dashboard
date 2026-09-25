"""Shared helpers for the ads_skills package: business-rules text, performance-data
text blocks (live Ads API data when available, manual-upload snapshot as fallback),
and the Claude call wrapper every skill uses."""

import logging
from datetime import date, timedelta

import config
from engines import claude_client
from models import db, GoogleAdsSnapshot, GoogleAdsKeyword, GoogleAdsCampaignDaily, \
    GoogleAdsKeywordDaily, GoogleAdsSearchTerm

logger = logging.getLogger(__name__)


def business_rules_block():
    r = config.AD_STRATEGY_RULES
    sd_note = ("do not recommend increasing SD spend; only efficiency/keyword/bid changes "
               "within its existing budget.") if r["sd_status"] == "paused" \
              else "SD is active and can receive budget recommendations."
    split = r["estate_probate_split"]
    lines = [
        "## Business Rules (must be followed in every recommendation)",
        "- Firm: Archangel Trust, estate planning and probate law, San Diego and Apple Valley, CA.",
        f"- San Diego budget status: {r['sd_status'].upper()} — {sd_note}",
        f"- Apple Valley budget status: {r['av_status'].upper()} — this is the current growth priority.",
        f"- Keyword/budget weighting target: {int(split['estate_planning']*100)}% estate planning/wills/"
        f"trusts, {int(split['probate']*100)}% probate. Reduce probate's weight, don't eliminate it.",
        f"- Target CPA: under ${r['cpa_ceiling_default']}.",
        f"- Primary conversion goal: consultation bookings via {r['calendly_url']}.",
    ]
    if r.get("no_free_consultation_language"):
        lines.append(
            "- NEVER use \"free consultation\" (or \"free call\", \"free meeting\", etc.) in any "
            "customer-facing copy — ad headlines/descriptions, landing page briefs, or anything "
            "else a prospect would read. Refer to it as a \"consultation\" or \"conversation\" "
            "without the word \"free\"."
        )
    return "\n".join(lines)


def monthly_target():
    return config.MONTHLY_TARGETS.get(date.today().strftime("%B").lower(), config.MONTHLY_TARGETS["default"])


def has_live_data():
    return db.session.query(GoogleAdsCampaignDaily.id).first() is not None


def campaign_rows(days=14):
    since = date.today() - timedelta(days=days)
    return (
        db.session.query(GoogleAdsCampaignDaily)
        .filter(GoogleAdsCampaignDaily.date >= since)
        .order_by(GoogleAdsCampaignDaily.date.desc())
        .all()
    )


def keyword_rows(days=14, limit=60):
    since = date.today() - timedelta(days=days)
    return (
        db.session.query(GoogleAdsKeywordDaily)
        .filter(GoogleAdsKeywordDaily.date >= since)
        .order_by(GoogleAdsKeywordDaily.cost.desc())
        .limit(limit)
        .all()
    )


def search_term_rows(days=14, limit=100):
    since = date.today() - timedelta(days=days)
    return (
        db.session.query(GoogleAdsSearchTerm)
        .filter(GoogleAdsSearchTerm.date >= since)
        .order_by(GoogleAdsSearchTerm.cost.desc())
        .limit(limit)
        .all()
    )


def _legacy_snapshot_block():
    """Fallback built from manual CSV-upload snapshots, used until live Ads API data exists."""
    snapshots = (
        db.session.query(GoogleAdsSnapshot)
        .order_by(GoogleAdsSnapshot.snapshot_date.desc())
        .limit(10)
        .all()
    )
    if not snapshots:
        return "No Google Ads data available yet (no CSV upload and no live API data)."

    lines = ["### Period Snapshots (most recent first, from manual CSV upload)"]
    for s in snapshots:
        period = (f"{s.period_start.strftime('%b %d')}–{s.period_end.strftime('%b %d')}"
                  if s.period_start and s.period_end else "")
        lines.append(
            f"- {period}: spend=${s.total_spend:.2f}, clicks={s.total_clicks}, "
            f"conv={s.total_conversions:.1f}, CPA=${s.cpa:.2f}, impr={s.total_impressions}"
        )

    keywords = (
        db.session.query(GoogleAdsKeyword)
        .filter_by(snapshot_id=snapshots[0].id)
        .order_by(GoogleAdsKeyword.cost.desc())
        .limit(20)
        .all()
    )
    if keywords:
        lines.append("\n### Top Keywords (most recent snapshot)")
        for kw in keywords:
            lines.append(
                f'- "{kw.keyword}" [{kw.match_type}] | campaign: {kw.campaign} | '
                f"clicks={kw.clicks}, conv={kw.conversions:.1f}, cost=${kw.cost:.2f}, CPA=${kw.cpa:.2f}"
            )
    return "\n".join(lines)


def _live_data_block(days=14):
    campaigns = campaign_rows(days)
    if not campaigns:
        return None

    by_campaign = {}
    for r in campaigns:
        c = by_campaign.setdefault(r.campaign_id, {
            "name": r.campaign_name, "location": r.location, "spend": 0.0,
            "clicks": 0, "conversions": 0.0, "impr_share": None, "budget_lost_is": None,
        })
        c["spend"] += r.spend
        c["clicks"] += r.clicks
        c["conversions"] += r.conversions
        if r.search_impression_share is not None:
            c["impr_share"] = r.search_impression_share
            c["budget_lost_is"] = r.search_budget_lost_is

    lines = [f"### Campaign Performance (last {days} days, live Google Ads API data)"]
    for c in by_campaign.values():
        cpa = round(c["spend"] / c["conversions"], 2) if c["conversions"] else 0
        is_str = f"{c['impr_share']*100:.0f}%" if c["impr_share"] is not None else "n/a"
        lost_str = f", budget-lost IS={c['budget_lost_is']*100:.0f}%" if c["budget_lost_is"] is not None else ""
        lines.append(
            f"- {c['name']} [{c['location']}]: spend=${c['spend']:.2f}, clicks={c['clicks']}, "
            f"conv={c['conversions']:.1f}, CPA=${cpa}, search impr. share={is_str}{lost_str}"
        )

    kws = keyword_rows(days, limit=30)
    if kws:
        lines.append(f"\n### Top Keywords by cost (last {days} days)")
        for kw in kws:
            qs = f", QS={kw.quality_score}" if kw.quality_score else ""
            lines.append(
                f'- "{kw.keyword_text}" [{kw.match_type}] | clicks={kw.clicks}, '
                f"conv={kw.conversions:.1f}, cost=${kw.cost:.2f}, CPA=${kw.cpa:.2f}{qs}"
            )

    terms = search_term_rows(days, limit=30)
    if terms:
        lines.append(f"\n### Search Terms (last {days} days, top by cost)")
        for t in terms:
            lines.append(f'- "{t.search_term}" | clicks={t.clicks}, conv={t.conversions:.1f}, cost=${t.cost:.2f}')

    return "\n".join(lines)


def performance_data_block(days=14):
    """Prefer live Ads API data; fall back to the manual-upload snapshot until Phase 1 cuts over."""
    return _live_data_block(days) or _legacy_snapshot_block()


def call_skill(system_prompt, user_prompt, max_tokens=2048):
    """Call Claude for a skill and parse its JSON-array response into a list of dicts.
    Returns [] (and logs) on failure — one bad skill run shouldn't break the others."""
    try:
        result = claude_client.call_json(system_prompt, user_prompt, max_tokens=max_tokens)
        return result if isinstance(result, list) else []
    except Exception as e:
        logger.error(f"ads_skills call failed: {e}")
        return []


RECOMMENDATION_JSON_SPEC = """Return a JSON array of recommendation objects (empty array if none apply).
Each object must have:
- "category": one of "budget", "keywords", "bids", "negatives", "copy", "structure", "tracking", "alerts"
- "priority": one of "high", "medium", "low"
- "title": short action title (under 80 chars)
- "recommendation": what to do, written as a clear instruction (1-2 sentences)
- "rationale": data-backed reasoning referencing specific numbers from the data provided
Return only the JSON array, no other text."""
