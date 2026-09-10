"""Separates 'lost impression share (budget)' from 'lost impression share (rank)' so
budget-reallocation recommendations are justified by real headroom, not guesswork."""

from engines.ads_skills import base

SKILL_ID = "impression_share_gap"

SYSTEM_PROMPT = """You are a Google Ads budget/bidding analyst. You are given campaign-level \
search impression share and its two loss components: budget-lost IS (ads not showing because \
the daily budget ran out) and rank-lost IS (ads not showing because of low Ad Rank — bids, \
Quality Score, or ad relevance).

These require different fixes: budget-lost IS means "there is real headroom to spend more \
productively if budget increases"; rank-lost IS means "more budget won't help until bids/QS/ad \
relevance improve first." Only recommend a budget increase for a campaign where budget-lost IS \
is the dominant loss. For San Diego, per the business rules below, report the finding but do \
NOT recommend a budget increase — recommend Apple Valley or efficiency changes instead.

""" + base.RECOMMENDATION_JSON_SPEC


def run():
    if not base.has_live_data():
        return []  # impression-share metrics only exist in live Google Ads API data (Phase 1)

    rules = base.business_rules_block()
    data = base.performance_data_block(days=14)
    user_prompt = f"{rules}\n\n{data}\n\nAnalyze impression-share loss by budget vs. rank per campaign."
    return base.call_skill(SYSTEM_PROMPT, user_prompt)
