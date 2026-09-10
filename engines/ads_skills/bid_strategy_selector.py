"""Recommends Target CPA vs. Maximize Conversions vs. Manual CPC based on actual
conversion volume — Target CPA needs meaningful history to work well."""

from engines.ads_skills import base

SKILL_ID = "bid_strategy_selector"

SYSTEM_PROMPT = """You are a Google Ads bid-strategy consultant. Recommend the most appropriate \
bid strategy per campaign given its actual conversion volume over the period provided:

- Manual CPC: appropriate when monthly conversion volume is very low (under ~10/month) — \
  automated strategies need conversion history to learn from and will underperform with too \
  little data.
- Maximize Conversions (optionally with a target CPA cap once ~15-30 conversions/month exist): \
  appropriate once there's enough volume for Google's algorithm to optimize against, but not \
  yet enough to lock in a hard CPA target.
- Target CPA: appropriate only once conversion volume is consistent and high enough \
  (generally 30+ conversions in the last 30 days) for the algorithm to hit a specific target \
  reliably.

State the current estimated monthly conversion volume you're basing each recommendation on.

""" + base.RECOMMENDATION_JSON_SPEC


def run():
    rules = base.business_rules_block()
    data = base.performance_data_block(days=30)
    target = base.monthly_target()
    user_prompt = (
        f"{rules}\n\n{data}\n\n"
        f"Target CPA ceiling: ${target['cpa_max']}\n\n"
        "Recommend bid strategy per campaign based on actual conversion volume."
    )
    return base.call_skill(SYSTEM_PROMPT, user_prompt)
