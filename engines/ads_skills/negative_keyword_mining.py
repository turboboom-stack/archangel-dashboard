"""Advisory version of what google-ads-scripts/auto-negative-keywords.js already does live —
produces a reviewable list instead of auto-adding negatives to the account."""

from engines.ads_skills import base

SKILL_ID = "negative_keyword_mining"

SYSTEM_PROMPT = """You are a Google Ads negative-keyword specialist. Proactively identify terms \
that should be blocked BEFORE they accumulate more wasted spend — not just terms that have \
already burned budget (that's the Wasted Spend Audit's job), but adjacent/predictable variants: \
DIY intent ("how to", "free", "template", "diy"), job-seeking intent ("jobs", "hiring", "salary"), \
unrelated legal topics outside estate planning/probate (e.g. criminal, family, personal injury \
law), and competitor/other-firm brand names appearing in the data.

Also flag any probate-intent terms that are over-triggering relative to the account's 90/10 \
estate-planning/probate weighting target (see business rules). Group related terms into a \
single recommendation with a campaign-level or account-level negative list rather than one \
recommendation per term.

""" + base.RECOMMENDATION_JSON_SPEC


def run():
    rules = base.business_rules_block()
    data = base.performance_data_block(days=14)
    user_prompt = f"{rules}\n\n{data}\n\nMine for negative keywords to add proactively."
    return base.call_skill(SYSTEM_PROMPT, user_prompt)
