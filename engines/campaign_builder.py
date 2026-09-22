"""
Ad Consultant campaign generator — takes the wizard's answers (goal, budget, location,
keyword direction, landing page preference) and produces a complete, reviewable campaign
package via Claude: keywords, RSA headlines/descriptions, budget breakdown, targeting,
a landing page suggestion, and step-by-step implementation instructions.

Nothing here ever touches the live Google Ads account — it only creates a CampaignPackage
row for human review, same as every other AI-generated recommendation in this app.
"""

import json
import logging

import config
from engines import claude_client
from engines.ads_skills import base as skills_base

logger = logging.getLogger(__name__)

# Known static marketing pages on archangeltrust.com (not tracked in WebflowPost, which
# only covers the Blog Posts CMS collection) — gives the model real candidates to suggest
# from instead of inventing a URL.
KNOWN_SITE_PAGES = [
    "Home (archangeltrust.com/)",
    "Apple Valley Estate Planning Attorney (/apple-valley-estate-planning-attorney)",
    "San Diego / California Estate Planning (/california-estate-planning)",
    "Estate Planning Services (/estate-planning-services)",
    "Probate (/probate)",
    "Advanced Planning & Special Needs Trusts (/advanced-planning)",
    "Attorney Profile (/attorney-profile-estate-planning-attorney-near-me)",
    "Contact (/contact)",
]

SYSTEM_PROMPT = """You are a Google Ads consultant building a new campaign proposal for \
Archangel Trust, a California estate planning and probate law firm (San Diego and Apple \
Valley). You're given the client's goal, budget, target location, and any keyword or \
landing-page direction they provided — produce a complete, ready-to-review campaign package.

If the requested location conflicts with the business rules below (e.g. San Diego is \
currently paused), still produce the package but say so plainly in the summary — don't \
silently ignore the conflict or silently refuse.

Return a JSON object with exactly these fields:
- "campaign_name": short descriptive name (e.g. "AV - Living Trusts - Search")
- "summary": 2-3 sentences explaining the approach and any conflicts/caveats
- "keywords": array of 10-15 objects {"keyword": "...", "match_type": "Phrase"|"Exact"|"Broad"}
- "headlines": array of 8-10 RSA headlines, each under 30 characters
- "descriptions": array of 3-4 RSA descriptions, each under 90 characters
- "budget_breakdown": 1-2 sentences on how the monthly budget translates to daily budget and expected pacing
- "targeting": 1-2 sentences on geographic/demographic targeting recommendations
- "landing_page_suggestion": which existing page to send traffic to and why (pick from the provided list, or say a new page is needed and describe it)
- "instructions": numbered, step-by-step instructions for building this campaign in the Google Ads UI

Return only the JSON object, no other text."""


GOAL_LABELS = {
    "more_consultations": "Drive more consultation bookings",
    "brand_awareness": "Build brand awareness in a new area",
    "specific_service": "Promote a specific service",
    "other": "Other (see notes)",
}


def _build_prompt(goal, goal_freeform, budget_monthly, location, keyword_direction, landing_page_preference):
    rules = skills_base.business_rules_block()
    target = skills_base.monthly_target()

    lines = [
        rules,
        "",
        "## Campaign Request",
        f"- Goal: {GOAL_LABELS.get(goal, goal)}",
    ]
    if goal_freeform:
        lines.append(f"- Additional notes on goal: {goal_freeform}")
    lines.append(f"- Monthly budget: ${budget_monthly:.0f}")
    lines.append(f"- Location: {location}")
    if keyword_direction:
        lines.append(f"- Keyword direction from client: {keyword_direction}")
    else:
        lines.append("- No specific keyword direction given — suggest based on the goal and business rules.")
    if landing_page_preference:
        lines.append(f"- Landing page preference from client: {landing_page_preference}")

    lines.append("\n## Known site pages (pick from these for the landing page suggestion, unless a new page is clearly warranted)")
    for p in KNOWN_SITE_PAGES:
        lines.append(f"- {p}")

    lines.append(f"\nMonthly booking goal: {target['bookings']}, target CPA: under ${target['cpa_max']}.")

    return "\n".join(lines)


def _as_text(value):
    """Claude sometimes returns a text field as a list of strings/steps instead of one
    string despite the prompt asking for a string — normalize either shape to text."""
    if isinstance(value, list):
        return "\n".join(str(v) for v in value)
    return value or ""


def generate(goal, goal_freeform, budget_monthly, location, keyword_direction, landing_page_preference):
    """Generate and persist a CampaignPackage. Must be called within an active Flask
    request/app context (it is only ever invoked synchronously from a route handler,
    unlike engines that also run from background threads). Returns (package, error_msg)."""
    if not config.ANTHROPIC_API_KEY:
        return None, "ANTHROPIC_API_KEY not configured"

    from models import db, CampaignPackage

    prompt = _build_prompt(goal, goal_freeform, budget_monthly, location, keyword_direction, landing_page_preference)

    try:
        result = claude_client.call_json(SYSTEM_PROMPT, prompt, max_tokens=4096, cache_system=False)
    except Exception as e:
        logger.error(f"Campaign builder failed: {e}")
        return None, str(e)

    pkg = CampaignPackage(
        goal=goal,
        goal_freeform=goal_freeform,
        budget_monthly=budget_monthly,
        location=location,
        keyword_direction=keyword_direction,
        landing_page_preference=landing_page_preference,
        campaign_name=_as_text(result.get("campaign_name", "New Campaign")),
        summary=_as_text(result.get("summary", "")),
        keywords_json=json.dumps(result.get("keywords", [])),
        headlines_json=json.dumps(result.get("headlines", [])),
        descriptions_json=json.dumps(result.get("descriptions", [])),
        budget_breakdown=_as_text(result.get("budget_breakdown", "")),
        targeting=_as_text(result.get("targeting", "")),
        landing_page_suggestion=_as_text(result.get("landing_page_suggestion", "")),
        instructions=_as_text(result.get("instructions", "")),
    )
    db.session.add(pkg)
    db.session.commit()
    return pkg, None
