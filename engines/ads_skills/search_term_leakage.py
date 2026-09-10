"""Finds systematic negative-keyword gaps in the search-terms report, and checks the
90/10 estate-planning/probate weighting is actually being reflected in what triggers ads."""

from engines.ads_skills import base

SKILL_ID = "search_term_leakage"

SYSTEM_PROMPT = """You are a Google Ads search-term analyst. You are given the account's recent \
search-terms report. Find SYSTEMATIC leakage — patterns of irrelevant or off-strategy queries \
triggering ads, not just one-off bad terms. Specifically check:

1. Categories of irrelevant intent (DIY/free/job-seeking/unrelated-legal-topic queries) \
   burning spend across multiple terms, suggesting a missing negative-keyword list rather \
   than one-off exclusions.
2. Whether probate-intent queries are over-represented relative to the account's 90/10 \
   estate-planning/probate weighting target — if so, flag it as a signal that match types \
   or keyword lists need tightening, not just a negative-keyword fix.

""" + base.RECOMMENDATION_JSON_SPEC


def run():
    if not base.has_live_data():
        return []  # needs the live search-terms report (Phase 1) — no meaningful signal from CSV snapshots

    rules = base.business_rules_block()
    data = base.performance_data_block(days=14)
    user_prompt = f"{rules}\n\n{data}\n\nFind systematic search-term leakage patterns."
    return base.call_skill(SYSTEM_PROMPT, user_prompt)
