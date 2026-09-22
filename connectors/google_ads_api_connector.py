"""
Live Google Ads API connector.

No-ops until config.ADS_API_ENABLED is True (i.e. until GOOGLE_ADS_DEVELOPER_TOKEN
and GOOGLE_ADS_CUSTOMER_ID are set — see Phase 0 of
/Users/jordan/.claude/plans/okay-before-that-we-deep-sprout.md).

Reuses the shared Google OAuth token (config.GOOGLE_TOKEN_PATH, same one GA4/GSC/GMB
use) for the refresh_token/client_id/client_secret — no separate google-ads.yaml.

Pulls a trailing 14-day window on every refresh (Ads conversion data has attribution
lag, so re-pulling recent days catches late-arriving conversions) and upserts by
(date, id). On first-ever run it backfills 90 days instead for immediate history.
"""

import json
import logging
from datetime import date, timedelta

import config
from models import db, CacheMetadata, GoogleAdsCampaignDaily, GoogleAdsAdGroupDaily, \
    GoogleAdsKeywordDaily, GoogleAdsSearchTerm

log = logging.getLogger(__name__)

MICROS = 1_000_000


def _get_client():
    from google.ads.googleads.client import GoogleAdsClient

    with open(config.GOOGLE_TOKEN_PATH) as f:
        token = json.load(f)

    creds = {
        "developer_token": config.GOOGLE_ADS_DEVELOPER_TOKEN,
        "client_id": token["client_id"],
        "client_secret": token["client_secret"],
        "refresh_token": token["refresh_token"],
        "use_proto_plus": True,
    }
    if config.GOOGLE_ADS_LOGIN_CUSTOMER_ID:
        creds["login_customer_id"] = config.GOOGLE_ADS_LOGIN_CUSTOMER_ID

    return GoogleAdsClient.load_from_dict(creds)


def _parse_date(d):
    """segments.date comes back from the Ads API as a 'YYYY-MM-DD' string, not a
    Python date object — SQLite's Date column rejects anything else."""
    return d if isinstance(d, date) else date.fromisoformat(str(d))


def _location_for(campaign_name):
    name = f" {campaign_name.lower()} "
    for needle, loc in config.GOOGLE_ADS_LOCATION_MAP.items():
        if needle in name:
            return loc
    return "UNK"


def _has_any_history():
    return db.session.query(GoogleAdsCampaignDaily.id).first() is not None


def _run_query(ga_service, customer_id, query):
    return ga_service.search_stream(customer_id=customer_id, query=query)


def _upsert_campaigns(rows, window_start, window_end):
    for r in rows:
        c = r.campaign
        m = r.metrics
        d = _parse_date(r.segments.date)
        row = (
            db.session.query(GoogleAdsCampaignDaily)
            .filter_by(date=d, campaign_id=str(c.id))
            .first()
        )
        if not row:
            row = GoogleAdsCampaignDaily(date=d, campaign_id=str(c.id))
            db.session.add(row)

        spend = m.cost_micros / MICROS
        conversions = m.conversions
        row.campaign_name = c.name
        row.location = _location_for(c.name)
        row.status = c.status.name
        row.channel_type = c.advertising_channel_type.name
        row.spend = spend
        row.clicks = m.clicks
        row.impressions = m.impressions
        row.conversions = conversions
        row.conversion_value = m.conversions_value
        row.cpa = round(spend / conversions, 2) if conversions > 0 else 0
        row.ctr = m.ctr
        row.avg_cpc = (m.average_cpc / MICROS) if m.average_cpc else 0
        row.search_impression_share = getattr(m, "search_impression_share", None)
        row.search_budget_lost_is = getattr(m, "search_budget_lost_impression_share", None)
        row.search_rank_lost_is = getattr(m, "search_rank_lost_impression_share", None)


def _upsert_ad_groups(rows):
    for r in rows:
        ag = r.ad_group
        m = r.metrics
        d = _parse_date(r.segments.date)
        row = (
            db.session.query(GoogleAdsAdGroupDaily)
            .filter_by(date=d, ad_group_id=str(ag.id))
            .first()
        )
        if not row:
            row = GoogleAdsAdGroupDaily(date=d, ad_group_id=str(ag.id))
            db.session.add(row)

        spend = m.cost_micros / MICROS
        conversions = m.conversions
        row.campaign_id = str(r.campaign.id)
        row.ad_group_name = ag.name
        row.spend = spend
        row.clicks = m.clicks
        row.impressions = m.impressions
        row.conversions = conversions
        row.cpa = round(spend / conversions, 2) if conversions > 0 else 0


_QS_MAP = {0: None, 2: "BELOW_AVERAGE", 3: "AVERAGE", 4: "ABOVE_AVERAGE"}


def _upsert_keywords(rows):
    for r in rows:
        crit = r.ad_group_criterion
        kw = crit.keyword
        m = r.metrics
        d = _parse_date(r.segments.date)
        row = (
            db.session.query(GoogleAdsKeywordDaily)
            .filter_by(date=d, keyword_id=str(crit.criterion_id))
            .first()
        )
        if not row:
            row = GoogleAdsKeywordDaily(date=d, keyword_id=str(crit.criterion_id))
            db.session.add(row)

        spend = m.cost_micros / MICROS
        conversions = m.conversions
        qi = crit.quality_info
        row.campaign_id = str(r.campaign.id)
        row.ad_group_id = str(r.ad_group.id)
        row.keyword_text = kw.text
        row.match_type = kw.match_type.name
        row.quality_score = qi.quality_score or None
        row.expected_ctr = qi.creative_quality_score.name if qi.creative_quality_score else None
        row.ad_relevance = qi.post_click_quality_score.name if qi.post_click_quality_score else None
        row.landing_page_exp = qi.post_click_quality_score.name if qi.post_click_quality_score else None
        row.impressions = m.impressions
        row.clicks = m.clicks
        row.cost = spend
        row.conversions = conversions
        row.cpa = round(spend / conversions, 2) if conversions > 0 else 0


def _upsert_search_terms(rows):
    for r in rows:
        st = r.search_term_view
        m = r.metrics
        d = _parse_date(r.segments.date)
        row = (
            db.session.query(GoogleAdsSearchTerm)
            .filter_by(date=d, campaign_id=str(r.campaign.id),
                       ad_group_id=str(r.ad_group.id), search_term=st.search_term)
            .first()
        )
        if not row:
            row = GoogleAdsSearchTerm(
                date=d, campaign_id=str(r.campaign.id),
                ad_group_id=str(r.ad_group.id), search_term=st.search_term,
            )
            db.session.add(row)

        row.matched_keyword = r.segments.keyword.info.text if r.segments.keyword else None
        row.match_type = r.segments.keyword.info.match_type.name if r.segments.keyword else None
        row.clicks = m.clicks
        row.impressions = m.impressions
        row.cost = m.cost_micros / MICROS
        row.conversions = m.conversions


def fetch(app):
    if not config.ADS_API_ENABLED:
        with app.app_context():
            CacheMetadata.get("google_ads_api").mark_stub()
        return

    with app.app_context():
        try:
            client = _get_client()
            ga_service = client.get_service("GoogleAdsService")
            customer_id = config.GOOGLE_ADS_CUSTOMER_ID

            days_back = 14 if _has_any_history() else 90
            window_start = date.today() - timedelta(days=days_back)
            window_end = date.today() - timedelta(days=1)  # yesterday — today's data is incomplete
            date_clause = f"segments.date BETWEEN '{window_start.isoformat()}' AND '{window_end.isoformat()}'"

            campaign_query = f"""
                SELECT campaign.id, campaign.name, campaign.status, campaign.advertising_channel_type,
                       segments.date, metrics.cost_micros, metrics.clicks, metrics.impressions,
                       metrics.conversions, metrics.conversions_value, metrics.ctr, metrics.average_cpc,
                       metrics.search_impression_share, metrics.search_budget_lost_impression_share,
                       metrics.search_rank_lost_impression_share
                FROM campaign
                WHERE {date_clause}
            """
            ad_group_query = f"""
                SELECT campaign.id, ad_group.id, ad_group.name, segments.date,
                       metrics.cost_micros, metrics.clicks, metrics.impressions, metrics.conversions
                FROM ad_group
                WHERE {date_clause}
            """
            keyword_query = f"""
                SELECT campaign.id, ad_group.id, ad_group_criterion.criterion_id,
                       ad_group_criterion.keyword.text, ad_group_criterion.keyword.match_type,
                       ad_group_criterion.quality_info.quality_score,
                       ad_group_criterion.quality_info.creative_quality_score,
                       ad_group_criterion.quality_info.post_click_quality_score,
                       segments.date, metrics.impressions, metrics.clicks, metrics.cost_micros,
                       metrics.conversions
                FROM keyword_view
                WHERE {date_clause}
            """
            search_term_query = f"""
                SELECT campaign.id, ad_group.id, search_term_view.search_term,
                       segments.date, segments.keyword.info.text, segments.keyword.info.match_type,
                       metrics.clicks, metrics.impressions, metrics.cost_micros, metrics.conversions
                FROM search_term_view
                WHERE {date_clause}
            """

            for batch in _run_query(ga_service, customer_id, campaign_query):
                _upsert_campaigns(batch.results, window_start, window_end)
            db.session.commit()

            for batch in _run_query(ga_service, customer_id, ad_group_query):
                _upsert_ad_groups(batch.results)
            db.session.commit()

            for batch in _run_query(ga_service, customer_id, keyword_query):
                _upsert_keywords(batch.results)
            db.session.commit()

            for batch in _run_query(ga_service, customer_id, search_term_query):
                _upsert_search_terms(batch.results)
            db.session.commit()

            CacheMetadata.get("google_ads_api").mark_ok()
            log.info(f"Google Ads API: refreshed {days_back}-day window ({window_start} to {window_end})")

        except Exception as e:
            log.error(f"Google Ads API fetch failed: {e}")
            db.session.rollback()
            CacheMetadata.get("google_ads_api").mark_error(str(e))


def get_cached(days=14):
    """Aggregate campaign-level data for the last N days, grouped by campaign."""
    since = date.today() - timedelta(days=days)
    rows = (
        db.session.query(GoogleAdsCampaignDaily)
        .filter(GoogleAdsCampaignDaily.date >= since)
        .order_by(GoogleAdsCampaignDaily.date.desc())
        .all()
    )

    by_campaign = {}
    for r in rows:
        c = by_campaign.setdefault(r.campaign_id, {
            "campaign_name": r.campaign_name, "location": r.location, "status": r.status,
            "spend": 0.0, "clicks": 0, "impressions": 0, "conversions": 0.0,
            "search_impression_share": None, "search_budget_lost_is": None,
        })
        c["spend"] += r.spend
        c["clicks"] += r.clicks
        c["impressions"] += r.impressions
        c["conversions"] += r.conversions
        if r.search_impression_share is not None:
            c["search_impression_share"] = r.search_impression_share
            c["search_budget_lost_is"] = r.search_budget_lost_is

    campaigns = []
    for cid, c in by_campaign.items():
        c["campaign_id"] = cid
        c["cpa"] = round(c["spend"] / c["conversions"], 2) if c["conversions"] > 0 else 0
        campaigns.append(c)
    campaigns.sort(key=lambda c: c["spend"], reverse=True)

    search_terms = (
        db.session.query(GoogleAdsSearchTerm)
        .filter(GoogleAdsSearchTerm.date >= since, GoogleAdsSearchTerm.conversions == 0,
                GoogleAdsSearchTerm.clicks >= 3)
        .order_by(GoogleAdsSearchTerm.cost.desc())
        .limit(30)
        .all()
    )

    return {"campaigns": campaigns, "wasted_search_terms": search_terms, "days": days}
