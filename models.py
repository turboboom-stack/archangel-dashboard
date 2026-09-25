"""SQLAlchemy models for the dashboard cache database."""

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class CacheMetadata(db.Model):
    __tablename__ = "cache_metadata"
    id = db.Column(db.Integer, primary_key=True)
    source_key = db.Column(db.String(64), unique=True, nullable=False)
    last_refreshed = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(32), default="never")  # never / ok / error / stubbed
    error_msg = db.Column(db.Text, nullable=True)

    @classmethod
    def get(cls, key):
        row = db.session.query(cls).filter_by(source_key=key).first()
        if not row:
            row = cls(source_key=key, status="never")
            db.session.add(row)
            db.session.commit()
        return row

    def mark_ok(self):
        self.last_refreshed = datetime.utcnow()
        self.status = "ok"
        self.error_msg = None
        db.session.commit()

    def mark_stub(self):
        self.last_refreshed = datetime.utcnow()
        self.status = "stubbed"
        self.error_msg = None
        db.session.commit()

    def mark_error(self, msg):
        self.last_refreshed = datetime.utcnow()
        self.status = "error"
        self.error_msg = str(msg)
        db.session.commit()


class GoogleAdsSnapshot(db.Model):
    __tablename__ = "google_ads_snapshots"
    id = db.Column(db.Integer, primary_key=True)
    snapshot_date = db.Column(db.Date, nullable=False)
    period_start = db.Column(db.Date, nullable=True)
    period_end = db.Column(db.Date, nullable=True)
    total_spend = db.Column(db.Float, default=0)
    total_clicks = db.Column(db.Integer, default=0)
    total_impressions = db.Column(db.Integer, default=0)
    total_conversions = db.Column(db.Float, default=0)
    cpa = db.Column(db.Float, default=0)
    roas = db.Column(db.Float, default=0)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

    keywords = db.relationship("GoogleAdsKeyword", backref="snapshot", cascade="all, delete-orphan")


class GoogleAdsKeyword(db.Model):
    __tablename__ = "google_ads_keywords"
    id = db.Column(db.Integer, primary_key=True)
    snapshot_id = db.Column(db.Integer, db.ForeignKey("google_ads_snapshots.id"), nullable=False)
    keyword = db.Column(db.String(256))
    match_type = db.Column(db.String(32))
    campaign = db.Column(db.String(256))
    clicks = db.Column(db.Integer, default=0)
    conversions = db.Column(db.Float, default=0)
    cost = db.Column(db.Float, default=0)
    cpa = db.Column(db.Float, default=0)


class GoogleAdsCampaignDaily(db.Model):
    """Live Google Ads API campaign-level daily performance (google_ads_api_connector)."""
    __tablename__ = "google_ads_campaign_daily"
    __table_args__ = (db.UniqueConstraint("date", "campaign_id", name="uq_ads_campaign_daily"),)
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    campaign_id = db.Column(db.String(32), nullable=False)
    campaign_name = db.Column(db.String(256))
    location = db.Column(db.String(8))  # 'SD' / 'AV' / 'UNK'
    status = db.Column(db.String(32))
    channel_type = db.Column(db.String(64))
    spend = db.Column(db.Float, default=0)
    clicks = db.Column(db.Integer, default=0)
    impressions = db.Column(db.Integer, default=0)
    conversions = db.Column(db.Float, default=0)
    conversion_value = db.Column(db.Float, default=0)
    cpa = db.Column(db.Float, default=0)
    ctr = db.Column(db.Float, default=0)
    avg_cpc = db.Column(db.Float, default=0)
    search_impression_share = db.Column(db.Float, nullable=True)
    search_budget_lost_is = db.Column(db.Float, nullable=True)
    search_rank_lost_is = db.Column(db.Float, nullable=True)
    refreshed_at = db.Column(db.DateTime, default=datetime.utcnow)


class GoogleAdsAdGroupDaily(db.Model):
    """Live Google Ads API ad-group-level daily performance."""
    __tablename__ = "google_ads_adgroup_daily"
    __table_args__ = (db.UniqueConstraint("date", "ad_group_id", name="uq_ads_adgroup_daily"),)
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    campaign_id = db.Column(db.String(32), nullable=False)
    ad_group_id = db.Column(db.String(32), nullable=False)
    ad_group_name = db.Column(db.String(256))
    spend = db.Column(db.Float, default=0)
    clicks = db.Column(db.Integer, default=0)
    impressions = db.Column(db.Integer, default=0)
    conversions = db.Column(db.Float, default=0)
    cpa = db.Column(db.Float, default=0)
    refreshed_at = db.Column(db.DateTime, default=datetime.utcnow)


class GoogleAdsKeywordDaily(db.Model):
    """Live Google Ads API keyword-level daily performance, incl. quality score."""
    __tablename__ = "google_ads_keyword_daily"
    __table_args__ = (db.UniqueConstraint("date", "keyword_id", name="uq_ads_keyword_daily"),)
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    campaign_id = db.Column(db.String(32), nullable=False)
    ad_group_id = db.Column(db.String(32), nullable=False)
    keyword_id = db.Column(db.String(32), nullable=False)
    keyword_text = db.Column(db.String(256))
    match_type = db.Column(db.String(32))
    quality_score = db.Column(db.Integer, nullable=True)
    expected_ctr = db.Column(db.String(32), nullable=True)          # BELOW_AVERAGE / AVERAGE / ABOVE_AVERAGE
    ad_relevance = db.Column(db.String(32), nullable=True)
    landing_page_exp = db.Column(db.String(32), nullable=True)
    impressions = db.Column(db.Integer, default=0)
    clicks = db.Column(db.Integer, default=0)
    cost = db.Column(db.Float, default=0)
    conversions = db.Column(db.Float, default=0)
    cpa = db.Column(db.Float, default=0)
    refreshed_at = db.Column(db.DateTime, default=datetime.utcnow)


class GoogleAdsSearchTerm(db.Model):
    """Live Google Ads API search-terms report — feeds negative-keyword/leakage skills."""
    __tablename__ = "google_ads_search_terms"
    __table_args__ = (
        db.UniqueConstraint("date", "campaign_id", "ad_group_id", "search_term", name="uq_ads_search_term"),
    )
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    campaign_id = db.Column(db.String(32), nullable=False)
    ad_group_id = db.Column(db.String(32), nullable=False)
    search_term = db.Column(db.String(512))
    matched_keyword = db.Column(db.String(256), nullable=True)
    match_type = db.Column(db.String(32), nullable=True)
    clicks = db.Column(db.Integer, default=0)
    impressions = db.Column(db.Integer, default=0)
    cost = db.Column(db.Float, default=0)
    conversions = db.Column(db.Float, default=0)
    refreshed_at = db.Column(db.DateTime, default=datetime.utcnow)


class GmbInsight(db.Model):
    __tablename__ = "gmb_insights"
    id = db.Column(db.Integer, primary_key=True)
    location = db.Column(db.String(8), nullable=False)  # 'SD' or 'AV'
    refreshed_at = db.Column(db.DateTime, default=datetime.utcnow)
    calls = db.Column(db.Integer, default=0)
    website_clicks = db.Column(db.Integer, default=0)
    direction_requests = db.Column(db.Integer, default=0)
    review_count = db.Column(db.Integer, default=0)
    avg_rating = db.Column(db.Float, default=0)
    last_post_date = db.Column(db.Date, nullable=True)
    search_impressions = db.Column(db.Integer, default=0)
    map_views = db.Column(db.Integer, default=0)


class GscQuery(db.Model):
    __tablename__ = "gsc_queries"
    id = db.Column(db.Integer, primary_key=True)
    refreshed_at = db.Column(db.DateTime, default=datetime.utcnow)
    query = db.Column(db.String(512))
    clicks = db.Column(db.Integer, default=0)
    impressions = db.Column(db.Integer, default=0)
    ctr = db.Column(db.Float, default=0)
    position = db.Column(db.Float, default=0)


class GscSummary(db.Model):
    __tablename__ = "gsc_summary"
    id = db.Column(db.Integer, primary_key=True)
    refreshed_at = db.Column(db.DateTime, default=datetime.utcnow)
    total_clicks = db.Column(db.Integer, default=0)
    total_impressions = db.Column(db.Integer, default=0)
    avg_position = db.Column(db.Float, default=0)
    date_range = db.Column(db.String(64))


class WebflowPost(db.Model):
    __tablename__ = "webflow_posts"
    id = db.Column(db.Integer, primary_key=True)
    cms_id = db.Column(db.String(128), unique=True, nullable=False)
    name = db.Column(db.String(512))
    slug = db.Column(db.String(512))
    is_draft = db.Column(db.Boolean, default=True)
    publish_date = db.Column(db.DateTime, nullable=True)
    last_published = db.Column(db.DateTime, nullable=True)
    refreshed_at = db.Column(db.DateTime, default=datetime.utcnow)


class ClioBooking(db.Model):
    __tablename__ = "clio_bookings"
    id = db.Column(db.Integer, primary_key=True)
    clio_id = db.Column(db.String(64), nullable=True)  # Clio matter ID, None for manual entries
    booking_date = db.Column(db.Date, nullable=False)
    location = db.Column(db.String(8))  # 'SD' or 'AV'
    source = db.Column(db.String(128))
    campaign = db.Column(db.String(256))
    entered_at = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text)
    gclid = db.Column(db.String(256), nullable=True)   # Google Click ID for offline conversion import
    email = db.Column(db.String(256), nullable=True)
    phone = db.Column(db.String(64), nullable=True)
    lsa_lead_id = db.Column(db.String(128), nullable=True)   # Google LSA lead ID if matched
    lsa_charged = db.Column(db.Boolean, nullable=True)       # whether LSA charged for this lead


class AdRecommendation(db.Model):
    __tablename__ = "ad_recommendations"
    id             = db.Column(db.Integer, primary_key=True)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)
    category       = db.Column(db.String(50))   # budget / keywords / bids / negatives / copy
    priority       = db.Column(db.String(10))   # high / medium / low
    title          = db.Column(db.String(200))
    recommendation = db.Column(db.Text)
    rationale      = db.Column(db.Text)
    status               = db.Column(db.String(20), default="pending")  # pending / approved / rejected / implemented
    reviewed_at          = db.Column(db.DateTime, nullable=True)
    agent_version        = db.Column(db.String(50), nullable=True)
    implemented_at       = db.Column(db.DateTime, nullable=True)
    implementation_notes = db.Column(db.Text, nullable=True)   # what the agent actually did
    follow_up_date       = db.Column(db.Date, nullable=True)   # when to check results
    follow_up_notes      = db.Column(db.Text, nullable=True)   # results logged after checking
    instructions         = db.Column(db.Text, nullable=True)   # step-by-step Google Ads UI instructions


class Ga4Summary(db.Model):
    __tablename__ = "ga4_summary"
    id                   = db.Column(db.Integer, primary_key=True)
    refreshed_at         = db.Column(db.DateTime, default=datetime.utcnow)
    date_range           = db.Column(db.String(64))          # e.g. "last 7 days"
    sessions             = db.Column(db.Integer, default=0)
    active_users         = db.Column(db.Integer, default=0)
    new_users            = db.Column(db.Integer, default=0)
    avg_session_duration = db.Column(db.Float, default=0)    # seconds
    bounce_rate          = db.Column(db.Float, default=0)    # 0-100
    # Conversion event counts (JSON string: {"event_name": count, ...})
    conversions_json     = db.Column(db.Text, default="{}")
    # Channel breakdown (JSON string: {"Organic Search": sessions, ...})
    channels_json        = db.Column(db.Text, default="{}")
    # Top landing pages (JSON string: [{"page": "/path", "sessions": n}, ...])
    top_pages_json       = db.Column(db.Text, default="[]")


class CampaignPackage(db.Model):
    __tablename__ = "campaign_packages"
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Wizard inputs
    goal = db.Column(db.String(64))
    goal_freeform = db.Column(db.Text, nullable=True)
    budget_monthly = db.Column(db.Float)
    location = db.Column(db.String(8))  # SD / AV / BOTH
    keyword_direction = db.Column(db.Text, nullable=True)
    landing_page_mode = db.Column(db.String(16), default="existing")  # existing / custom
    landing_page_preference = db.Column(db.Text, nullable=True)  # notes either mode

    # Generated output
    campaign_name = db.Column(db.String(256))
    summary = db.Column(db.Text)
    keywords_json = db.Column(db.Text, default="[]")       # [{"keyword": "...", "match_type": "..."}]
    headlines_json = db.Column(db.Text, default="[]")      # ["...", ...]
    descriptions_json = db.Column(db.Text, default="[]")   # ["...", ...]
    budget_breakdown = db.Column(db.Text)
    targeting = db.Column(db.Text)
    landing_page_suggestion = db.Column(db.Text)   # existing-page pick + why
    landing_page_prompt = db.Column(db.Text, nullable=True)  # brief for the external landing-page tool (custom mode)

    status = db.Column(db.String(20), default="draft")  # draft / approved / rejected
    reviewed_at = db.Column(db.DateTime, nullable=True)

    # Step-by-step implementation tracking
    current_step = db.Column(db.Integer, default=0)  # how many steps marked done
    deployed_at = db.Column(db.DateTime, nullable=True)


class OpportunityIdea(db.Model):
    __tablename__ = "opportunity_ideas"
    id = db.Column(db.Integer, primary_key=True)
    generated_at = db.Column(db.DateTime, default=datetime.utcnow)
    category = db.Column(db.String(64))  # e.g. ad_format, seasonal, channel, keyword_gap, local
    title = db.Column(db.String(200))
    description = db.Column(db.Text)
    rationale = db.Column(db.Text)


class DailyBriefing(db.Model):
    __tablename__ = "daily_briefings"
    id = db.Column(db.Integer, primary_key=True)
    generated_at = db.Column(db.DateTime, default=datetime.utcnow)
    text = db.Column(db.Text)


class ActionItem(db.Model):
    __tablename__ = "action_items"
    id = db.Column(db.Integer, primary_key=True)
    generated_at = db.Column(db.DateTime, default=datetime.utcnow)
    severity = db.Column(db.String(16))   # critical / warning / opportunity
    category = db.Column(db.String(32))   # ads / gmb / seo / content / competitor / bookings
    rule_id = db.Column(db.String(64))
    message = db.Column(db.Text)
    cta_text = db.Column(db.String(128))
    cta_url = db.Column(db.String(512))
    is_dismissed = db.Column(db.Boolean, default=False)
