"""Forwards newly-created Clio contacts to Aspen's lead-ingest endpoint (Supabase edge function)."""

import json
import logging
import urllib.request
import urllib.error

import config

log = logging.getLogger(__name__)


def send_contact_created(email, first_name="", last_name="", properties=None, occurred_at=None):
    """POST a contact_created event to Aspen. Best-effort — logs and returns on failure,
    never raises, so a down/misbehaving Aspen endpoint can't break the Clio sync."""
    if not email:
        log.warning("Aspen: skipping contact_created — no email")
        return
    if not config.ASPEN_INGEST_URL or not config.ASPEN_ADVISOR_ID:
        return

    payload = {"event_type": "contact_created", "email": email}
    if first_name:
        payload["first_name"] = first_name
    if last_name:
        payload["last_name"] = last_name
    if properties:
        payload["properties"] = properties
    if occurred_at:
        payload["occurred_at"] = occurred_at

    url = f"{config.ASPEN_INGEST_URL}?advisor_id={config.ASPEN_ADVISOR_ID}"
    headers = {"Content-Type": "application/json"}
    if config.ASPEN_API_KEY:
        headers["Authorization"] = f"Bearer {config.ASPEN_API_KEY}"

    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            resp.read()
        log.info(f"Aspen: sent contact_created for {email}")
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        log.error(f"Aspen webhook failed ({e.code}): {body[:300]}")
    except Exception as e:
        log.error(f"Aspen webhook failed: {e}")
