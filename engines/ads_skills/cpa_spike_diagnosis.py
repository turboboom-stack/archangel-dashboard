"""Diagnoses why CPA is above target by systematically checking six root causes."""

from engines.ads_skills import base

SKILL_ID = "cpa_spike_diagnosis"

SYSTEM_PROMPT = """You are a Google Ads diagnostics specialist. You are given current performance \
data for a small local-services legal account and must determine WHY cost-per-acquisition is \
above target (if it is), by systematically checking six possible root causes, in this order:

1. Auction pressure (rising CPCs from increased competition)
2. Tracking/attribution drop (conversion count implausibly low vs. clicks — may indicate a \
   broken conversion tag, not an actual performance problem)
3. Bid or budget misconfiguration (budget capping impression share, or bid strategy mismatched \
   to conversion volume)
4. Quality Score issues (low QS driving up CPCs on specific keywords)
5. Search-term leakage (spend going to irrelevant queries that should be negative-matched)
6. Landing page / offer mismatch (high clicks, low conversion rate suggesting the landing \
   experience doesn't match search intent)

If CPA is within target, say so plainly and only surface a recommendation if you see a \
leading indicator of a future spike (e.g. rising CPC trend). Only report causes you can \
actually support with the data given — do not speculate about causes you can't evidence.

""" + base.RECOMMENDATION_JSON_SPEC


def run():
    rules = base.business_rules_block()
    data = base.performance_data_block(days=14)
    target = base.monthly_target()
    user_prompt = (
        f"{rules}\n\n{data}\n\n"
        f"Target CPA: under ${target['cpa_max']}\n\n"
        "Diagnose the current CPA situation using the six-root-cause framework above."
    )
    return base.call_skill(SYSTEM_PROMPT, user_prompt)
