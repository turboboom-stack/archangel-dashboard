"""Central configuration for the Archangel Command Center dashboard."""

import os
from pathlib import Path

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def _load_env():
    env = {}
    p = Path(BASE_DIR) / ".env"
    if p.exists():
        for line in p.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env

_env = _load_env()
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY") or _env.get("ANTHROPIC_API_KEY", "")
GA4_PROPERTY_ID   = os.environ.get("GA4_PROPERTY_ID") or _env.get("GA4_PROPERTY_ID", "390363293")

GA4_CONVERSION_EVENTS = [
    "ads_conversion_Contact_Us_1",
    "form_start",
    "form_submit",
]
ARCHANGEL_DIR = os.path.dirname(BASE_DIR)

# ── External data paths ──────────────────────────────────────────────────────
SEO_DB_PATH = os.path.join(ARCHANGEL_DIR, "estate_planning_seo_analyzer", "estate_planning_seo.db")
KEYWORDS_JSON_PATH = os.path.join(ARCHANGEL_DIR, "archangel-marketing", "seo-content-engine", "keywords.json")
POSTS_DIR = os.path.join(ARCHANGEL_DIR, "archangel-marketing", "seo-content-engine", "posts")
COMPETITOR_REPORTS_DIR = os.path.join(ARCHANGEL_DIR, "tracking", "weekly-reports")
WEBFLOW_ENV_PATH = os.path.join(ARCHANGEL_DIR, "webflow-blog-scheduler", ".env")
GOOGLE_CREDENTIALS_PATH = os.path.join(ARCHANGEL_DIR, "automations", "google-auth-setup", "credentials.json")
GOOGLE_TOKEN_PATH = os.path.join(ARCHANGEL_DIR, "automations", "google-auth-setup", "token.json")

# ── Webflow ───────────────────────────────────────────────────────────────────
WEBFLOW_API_BASE = "https://api.webflow.com/v2"
WEBFLOW_SITE_ID = "63ac55346093abd87bb7c94b"
WEBFLOW_COLLECTION_ID = "698a3ae9e9fbd2025949aff5"

# ── GMB ───────────────────────────────────────────────────────────────────────
GMB_ACCOUNT_ID = "15426524260327885681"
GMB_LOCATION_SD = "11305825743805504309"
GMB_LOCATION_AV = "13038354335424408062"

# ── Monthly KPI targets ───────────────────────────────────────────────────────
MONTHLY_TARGETS = {
    "april":  {"bookings": 15, "cpa_max": 150, "posts": 8},
    "may":    {"bookings": 25, "cpa_max": 120, "posts": 8},
    "june":   {"bookings": 30, "cpa_max": 100, "posts": 8},
    "default":{"bookings": 15, "cpa_max": 150, "posts": 8},
}

# ── Hosted-deployment support ─────────────────────────────────────────────────
import tempfile as _tempfile

SECRET_KEY = os.environ.get("SECRET_KEY") or _env.get("SECRET_KEY") or "archangel-dashboard-2026"

# Allow Railway (or any host) to point the DB at a persistent volume via DATA_DIR env var
DATA_DIR = os.environ.get("DATA_DIR") or _env.get("DATA_DIR") or BASE_DIR

# If the Google token file is absent (server env) but available as env var, write to a temp file.
# On Railway: set GOOGLE_TOKEN_JSON = contents of token.json (the whole JSON string)
_google_token_json = os.environ.get("GOOGLE_TOKEN_JSON") or _env.get("GOOGLE_TOKEN_JSON")
if _google_token_json and not os.path.exists(GOOGLE_TOKEN_PATH):
    _tmp = _tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    _tmp.write(_google_token_json)
    _tmp.close()
    GOOGLE_TOKEN_PATH = _tmp.name

# Same for Clio token — seed clio_token.json from CLIO_TOKEN_JSON env var on first boot
_clio_token_file = os.path.join(BASE_DIR, "clio_token.json")
_clio_token_json = os.environ.get("CLIO_TOKEN_JSON") or _env.get("CLIO_TOKEN_JSON")
if _clio_token_json and not os.path.exists(_clio_token_file):
    with open(_clio_token_file, "w") as _f:
        _f.write(_clio_token_json)

# ── Stub flags ─────────────────────────────────────────────────────────────────
# Set to False once OAuth / API is confirmed working for that source.
STUBS = {
    "gmb": False,  # LIVE — Business Profile Performance API working
    "gsc": False,  # LIVE — Search Console working
    "ga4": False,
    "google_ads": False,  # always file upload — no stub
}
