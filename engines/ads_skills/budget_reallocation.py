"""Models spend-shift scenarios, hard-constrained to Apple Valley since San Diego is paused."""

from engines.ads_skills import base

SKILL_ID = "budget_reallocation"

SYSTEM_PROMPT = """You are a Google Ads budget strategist. Model up to 3 budget-reallocation \
scenarios for growing qualified consultation bookings, given the account's current performance.

Hard constraint: if San Diego budget status (below) is PAUSED, do not model or recommend any \
scenario that increases San Diego spend — every scenario must route incremental budget to \
Apple Valley or to efficiency changes (bids/keywords/negatives) within existing budgets. If SD \
is ACTIVE, you may include SD scenarios.

For each scenario, estimate the directional impact on booking volume and CPA using the data \
provided — be explicit that these are directional estimates, not guarantees.

""" + base.RECOMMENDATION_JSON_SPEC


def run():
    rules = base.business_rules_block()
    data = base.performance_data_block(days=30)
    target = base.monthly_target()
    user_prompt = (
        f"{rules}\n\n{data}\n\n"
        f"Monthly booking goal: {target['bookings']}, target CPA: under ${target['cpa_max']}\n\n"
        "Model budget-reallocation scenarios for maximizing bookings within these constraints."
    )
    return base.call_skill(SYSTEM_PROMPT, user_prompt)
