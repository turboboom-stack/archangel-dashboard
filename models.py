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
