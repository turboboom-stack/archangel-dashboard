"""Google Business Profile reviews: weekly sync, Claude-drafted replies, and posting a reply
once Jordan approves it in the dashboard (My Business API v4, shared OAuth business.manage scope)."""

import json
import logging
import re
import urllib.error
import urllib.request
from datetime import datetime
from html import escape

import config
from models import db, GmbReview

logger = logging.getLogger(__name__)

API = "https://mybusiness.googleapis.com/v4"
STARS = {"ONE": 1, "TWO": 2, "THREE": 3, "FOUR": 4, "FIVE": 5}
LOCATIONS = {"AV": config.GMB_LOCATION_AV, "SD": config.GMB_LOCATION_SD}
LOCATION_NAMES = {"AV": "Apple Valley", "SD": "San Diego"}

SYSTEM_PROMPT = """You write replies to Google reviews for ArchAngel Trust and Probate Services, APC, a California \
estate planning and probate law firm (attorney Victoria P. Martin; offices in Apple Valley and San Diego).

Rules:
- Warm, genuine, specific to what the reviewer praised. 25-50 words for positive reviews. No generic filler, no emojis.
- Greet them by first name if the display name looks like a real name; otherwise just "Thank you".
- Talk only about their experience with the team (clear, kind, quick, helpful) and any staff member they named. \
Refer to staff by name only, never "he" or "she".
- CONFIDENTIALITY (attorney ethics rules apply to public replies): never mention or allude to their legal matter, \
even if they described it themselves: no trusts, wills, documents, estates, family members, "your planning", \
"your case" or outcomes. Never confirm that someone is or was a client. Never give legal advice.
  Banned words in the reply: family, parents, mom, dad, wife, husband, brother, sister, children, kids, trust \
(as a document), will, estate, probate, documents, invoice, bill, case. ("Thank you for trusting us" is fine.)
- Star-only reviews (no text): a short, warm thank-you, 10-20 words.
- Negative or mixed reviews: calm and courteous, 25-45 words. Don't restate, confirm or dispute anything they said \
(don't mention billing, invoices, services or people). Say we take every concern seriously and ask them to call our \
office so we can talk directly.
- Never say "free consultation". No prices. No links or phone numbers.
- Sign off on its own line: "— The ArchAngel Team"

Return only the reply text."""


def _token():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    creds = Credentials.from_authorized_user_file(config.GOOGLE_TOKEN_PATH)
    if not creds.valid:
        creds.refresh(Request())
    return creds.token


def _api(method, path, body=None):
    req = urllib.request.Request(f"{API}/{path}", method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"Bearer {_token()}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Google {e.code}: {e.read().decode()[:300]}") from e


def _fetch(loc_id):
    reviews, token = [], None
    while True:
        q = f"accounts/{config.GMB_ACCOUNT_ID}/locations/{loc_id}/reviews?pageSize=50"
        d = _api("GET", q + (f"&pageToken={token}" if token else ""))
        reviews += d.get("reviews", [])
        token = d.get("nextPageToken")
        if not token:
            return reviews


SENSITIVE = re.compile(r"\b(famil(y|ies)|parents?|mom|dad|mother|father|wife|husband|spouse|brother|sister|sons?|"
                       r"daughters?|children|kids|wills|estates?|probate|documents?|invoices?|bill(ing)?|case|"
                       r"a trust|your trust|the trust|trusts)\b", re.I)


def check(text):
    """Words that could reveal something about the reviewer's legal matter; shown as a warning, not blocked."""
    found = sorted({m.group(0).lower() for m in SENSITIVE.finditer(text or "")})
    return f"Check before posting, mentions: {', '.join(found)}" if found else None


def draft_reply(review, guidance=None):
    prompt = (f"Location: {LOCATION_NAMES.get(review.location, '')}\nReviewer: {review.reviewer}\n"
              f"Stars: {review.stars}/5\nReview: {review.comment or '(no text, star rating only)'}")
    if guidance:
        prompt += f"\n\nJordan's guidance for this reply: {guidance}"
    from engines import claude_client
    text = claude_client.call(SYSTEM_PROMPT, prompt, max_tokens=400).strip()
    if check(text):
        text = claude_client.call(SYSTEM_PROMPT, prompt + f"\n\nYour first draft broke the confidentiality rule "
                                  f"({check(text)}). Rewrite it without those words:\n{text}", max_tokens=400).strip()
    return text


def sync(app, notify=False):
    """Pull every review, record replies made elsewhere, and draft replies for new unanswered ones."""
    from models import CacheMetadata
    with app.app_context():
        try:
            return _sync(notify)
        except Exception as e:
            logger.error("Review sync failed: %s", e)
            db.session.rollback()
            CacheMetadata.get("gmb_reviews").mark_error(str(e))
            return 0


def _sync(notify):
    from models import CacheMetadata
    new = []
    for loc, loc_id in LOCATIONS.items():
        for r in _fetch(loc_id):
            row = GmbReview.query.filter_by(name=r["name"]).first()
            if not row:
                row = GmbReview(name=r["name"], location=loc, status="needs_reply")
                db.session.add(row)
                if "reviewReply" not in r:
                    new.append(row)
            row.reviewer = r.get("reviewer", {}).get("displayName")
            row.stars = STARS.get(r.get("starRating"))
            row.comment = r.get("comment")
            row.review_time = datetime.fromisoformat(r["createTime"][:19])
            row.google_reply = r.get("reviewReply", {}).get("comment")
            if row.google_reply and row.status == "needs_reply":
                row.status = "replied"
    db.session.commit()

    for row in GmbReview.query.filter_by(status="needs_reply").filter(GmbReview.reply_draft.is_(None)).all():
        try:
            row.reply_draft = draft_reply(row)
            row.error = check(row.reply_draft)
        except Exception as e:
            row.error = f"Draft failed: {e}"
        db.session.commit()

    CacheMetadata.get("gmb_reviews").mark_ok()
    if notify and new:
        _notify(new)
    return len(new)


def post_reply(row, text):
    _api("PUT", f"{row.name}/reply", {"comment": text})
    row.reply_draft = text
    row.google_reply = text
    row.status = "posted"
    row.posted_at = datetime.utcnow()
    row.error = None


def _notify(rows):
    import roadmap_plan as plan
    from connectors import gmail_connector
    lines = [f"- {r.stars}★ {r.reviewer} ({LOCATION_NAMES.get(r.location)}): {(r.comment or '(no text)')[:120]}" for r in rows]
    url = f"{plan.DASHBOARD_URL}/reviews"
    low = sum(1 for r in rows if (r.stars or 5) <= 3)
    subject = f"{len(rows)} new Google review{'s' if len(rows) > 1 else ''}" + (f" ({low} at 3★ or below)" if low else "")
    text = "Reply drafts are ready to check and post:\n\n" + "\n".join(lines) + f"\n\n{url}"
    html = "<p>Reply drafts are ready to check and post:</p><ul>" + "".join(
        f"<li>{escape(l[2:])}</li>" for l in lines) + f'</ul><p><a href="{url}">Review and post replies</a></p>'
    try:
        gmail_connector.send(plan.NOTIFY_EMAIL, subject, html, text)
    except Exception as e:
        logger.error("Review notification failed: %s", e)
