"""Registry of ad-strategy analysis skills. Each module exposes SKILL_ID and run() ->
list[dict] shaped like AdRecommendation fields (category/priority/title/recommendation/
rationale). engines/ads_analyzer.py iterates this registry and persists the results.

9 of the 15 skills from the "Claude Skills for Google Ads" framework, prioritized for a
small 2-location legal account. Deferred (not built): Quality Score Analysis, Ad Copy A/B
Generator, Landing Page Match Scorer, ROAS Forecasting, Executive Summary Generator
(overlaps engines/weekly_summary.py), Competitor Benchmark Report (needs Auction Insights API).
"""

from engines.ads_skills import (
    cpa_spike_diagnosis,
    wasted_spend_audit,
    search_term_leakage,
    impression_share_gap,
    budget_reallocation,
    negative_keyword_mining,
    bid_strategy_selector,
    weekly_digest,
    anomaly_detection,
)

SKILLS = {
    cpa_spike_diagnosis.SKILL_ID: cpa_spike_diagnosis,
    wasted_spend_audit.SKILL_ID: wasted_spend_audit,
    search_term_leakage.SKILL_ID: search_term_leakage,
    impression_share_gap.SKILL_ID: impression_share_gap,
    budget_reallocation.SKILL_ID: budget_reallocation,
    negative_keyword_mining.SKILL_ID: negative_keyword_mining,
    bid_strategy_selector.SKILL_ID: bid_strategy_selector,
    weekly_digest.SKILL_ID: weekly_digest,
    anomaly_detection.SKILL_ID: anomaly_detection,
}
