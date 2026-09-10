"""Flags spend going to search terms/keywords with clicks but no conversions."""

from engines.ads_skills import base

SKILL_ID = "wasted_spend_audit"

SYSTEM_PROMPT = """You are a Google Ads efficiency auditor. Identify spend that produced clicks \
but zero (or near-zero) conversions — this is money that should be redirected or cut.

Use these thresholds as priors (matched to what the account's own live negative-keyword \
automation already enforces, in google-ads-scripts/auto-negative-keywords.js): a search term \
or keyword with >=10 clicks and 0 conversions, OR CPA more than 2x the target CPA, is a strong \
candidate for a negative keyword or pause. Don't just restate the thresholds — reference the \
actual terms/keywords and numbers from the data provided.

""" + base.RECOMMENDATION_JSON_SPEC


def run():
    rules = base.business_rules_block()
    data = base.performance_data_block(days=14)
    target = base.monthly_target()
    user_prompt = (
        f"{rules}\n\n{data}\n\n"
        f"Target CPA: under ${target['cpa_max']}\n\n"
        "Audit for wasted spend: clicks with no conversions, or CPA far above target."
    )
    return base.call_skill(SYSTEM_PROMPT, user_prompt)
