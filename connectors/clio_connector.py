"""
Clio Grow + Manage connector.
Pulls consultations (Grow) and active matters + revenue (Manage).
Token auto-refreshes using stored client credentials.
"""

import json
import logging
import urllib.parse
import urllib.request
from datetime import datetime, date, timedelta
from pathlib import Path

import config
from models import db, ClioBooking, CacheMetadata

log = logging.getLogger(__name__)

SCRIPT_DIR = Path(config.BASE_DIR)
TOKEN_FILE  = SCRIPT_DIR / "clio_token.json"
API_BASE  = "https://app.clio.com/api/v4"
TOKEN_URL = "https://app.clio.com/oauth/token"


# ── Auth ───────────────────────────────────────────────────────────────────────

def _load_token():
    if not TOKEN_FILE.exists():
        raise FileNotFoundError(
            f"clio_token.json not found. Run: python3 clio_auth_setup.py"
        )
    return json.loads(TOKEN_FILE.read_text())


def _refresh_token(token_data):
    payload = urllib.parse.urlencode({
        "grant_type":    "refresh_token",
        "refresh_token": token_data["refresh_token"],
        "client_id":     token_data["client_id"],
        "client_secret": token_data["client_secret"],
    }).encode()
    req = urllib.request.Request(
        TOKEN_URL,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        new_token = json.loads(resp.read())
    # Preserve client creds
    new_token.setdefault("client_id",     token_data["client_id"])
    new_token.setdefault("client_secret", token_data["client_secret"])
    TOKEN_FILE.write_text(json.dumps(new_token, indent=2))
    log.info("Clio token refreshed.")
    return new_token


def _get_token():
    token = _load_token()
    # Clio tokens expire in 1 hour; check expires_at if present
    expires_at = token.get("expires_at")
    if expires_at:
        try:
            exp = datetime.fromisoformat(expires_at)
            if datetime.utcnow() >= exp - timedelta(minutes=5):
                token = _refresh_token(token)
        except (ValueError, TypeError):
            pass
    return token["access_token"]


# ── API helpers ────────────────────────────────────────────────────────────────

def _get(path, params=None):
    access_token = _get_token()
    url = f"{API_BASE}/{path}.json"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type":  "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        if e.code == 401:
            # Token expired — force refresh and retry once
            token_data = _load_token()
            new_token  = _refresh_token(token_data)
            req.add_header("Authorization", f"Bearer {new_token['access_token']}")
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read())
        raise Exception(f"Clio API {e.code}: {body[:200]}")


def _paginate(path, params=None):
    """Yield all items across paginated responses."""
    params = dict(params or {})
    params.setdefault("limit", 200)
    page = 1
    while True:
        params["page"] = page
        data = _get(path, params)
        items = data.get("data", [])
        if not items:
            break
        yield from items
        meta = data.get("meta", {})
        if not meta.get("paging", {}).get("next"):
            break
        page += 1


# ── Data fetchers ──────────────────────────────────────────────────────────────

def _fetch_new_contacts(days=30):
    """
    Pull contacts created in the last N days from Clio.
    Clio Grow pipeline stages aren't exposed via v4 API, so new contacts
    serve as the closest proxy for recent leads/consultations.
    Ordered by id desc (higher id = newer) to stop pagination early.
    """
    since = (date.today() - timedelta(days=days)).isoformat()
    contacts = []
    for contact in _paginate("contacts", {
        "fields": "id,name,type,created_at,primary_email_address,primary_phone_number",
        "order":  "id(desc)",
    }):
        created_raw = contact.get("created_at", "")
        if not created_raw:
            continue
        if created_raw[:10] < since:
            break  # ids desc ≈ created desc — past our window
        contacts.append({
            "clio_id":    f"contact-{contact.get('id', '')}",
            "name":       contact.get("name", ""),
            "email":      contact.get("primary_email_address") or "",
            "phone":      contact.get("primary_phone_number") or "",
            "created_at": created_raw[:10],
        })
    return contacts


def _fetch_active_matters():
    """Pull count of open matters from Clio Manage."""
    data = _get("matters", {"status": "open", "fields": "id", "limit": 1})
    return data.get("meta", {}).get("records", 0)


def _fetch_recent_revenue(days=30):
    """Pull billed amounts from the last N days, sorted desc to stop early."""
    since = (date.today() - timedelta(days=days)).isoformat()
    total = 0.0
    for bill in _paginate("bills", {
        "fields": "id,total,issued_at,state",
        "order":  "issued_at(desc)",
    }):
        issued = bill.get("issued_at", "")
        state  = bill.get("state", "")
        if not issued:
            continue
        if issued[:10] < since:
            break  # sorted desc — past our window, stop
        if state not in ("void", "draft"):
            total += float(bill.get("total") or 0)
    return round(total, 2)


# ── Main fetch → cache ─────────────────────────────────────────────────────────

def fetch(app):
    try:
        log.info("Clio: fetching data...")
        active_matters = _fetch_active_matters()
        revenue        = _fetch_recent_revenue(days=30)
        new_contacts   = _fetch_new_contacts(days=30)

        with app.app_context():
            existing_ids = {
                b.clio_id for b in db.session.query(ClioBooking).filter(
                    ClioBooking.clio_id.isnot(None)
                ).all()
            }

            added = 0
            for c in new_contacts:
                if c["clio_id"] in existing_ids:
                    continue
                try:
                    bdate = date.fromisoformat(c["created_at"][:10])
                except (ValueError, TypeError):
                    bdate = date.today()
                db.session.add(ClioBooking(
                    clio_id=c["clio_id"],
                    booking_date=bdate,
                    location="",
                    source="clio_grow",
                    campaign="",
                    notes=c["name"],
                ))
                added += 1

            db.session.commit()

            meta = CacheMetadata.get("clio")
            meta.mark_ok()
            meta.error_msg = json.dumps({
                "active_matters":  active_matters,
                "revenue_30d":     revenue,
                "consults_total":  len(new_contacts),
            })
            db.session.commit()

            log.info(f"Clio: {added} new contacts | {active_matters} open matters | ${revenue} revenue (30d)")

    except FileNotFoundError as e:
        log.warning(str(e))
        with app.app_context():
            CacheMetadata.get("clio").mark_error(str(e))
    except Exception as e:
        log.error(f"Clio fetch failed: {e}")
        with app.app_context():
            CacheMetadata.get("clio").mark_error(str(e))


def get_cached():
    """Return summary dict from cached metadata."""
    meta = CacheMetadata.get("clio")
    stats = {}
    if meta.error_msg and meta.status == "ok":
        try:
            stats = json.loads(meta.error_msg)
        except (json.JSONDecodeError, TypeError):
            pass

    bookings_this_month = db.session.query(ClioBooking).filter(
        ClioBooking.booking_date >= date.today().replace(day=1),
        ClioBooking.source == "clio_grow",
    ).count()

    return {
        "active_matters":    stats.get("active_matters", 0),
        "revenue_30d":       stats.get("revenue_30d", 0),
        "consults_total":    stats.get("consults_total", 0),
        "bookings_this_month": bookings_this_month,
        "last_refreshed":    meta.last_refreshed,
        "status":            meta.status,
        "error":             meta.error_msg if meta.status == "error" else None,
    }
