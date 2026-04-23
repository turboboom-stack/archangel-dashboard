"""Fetch Webflow CMS blog posts via API v2."""

import json
import os
import urllib.request
import urllib.error
from datetime import datetime
import config
from models import db, WebflowPost, CacheMetadata


def _get_token():
    token = os.environ.get("WEBFLOW_API_TOKEN")
    if token:
        return token
    env_path = config.WEBFLOW_ENV_PATH
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("WEBFLOW_API_TOKEN="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def _api_request(endpoint):
    token = _get_token()
    if not token:
        raise RuntimeError("WEBFLOW_API_TOKEN not found")
    url = f"{config.WEBFLOW_API_BASE}{endpoint}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _fetch_all_items():
    items = []
    offset = 0
    while True:
        resp = _api_request(
            f"/collections/{config.WEBFLOW_COLLECTION_ID}/items?limit=100&offset={offset}"
        )
        batch = resp.get("items", [])
        items.extend(batch)
        if len(batch) < 100:
            break
        offset += 100
    return items


def _parse_date(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def fetch(app):
    meta = CacheMetadata.get("webflow")
    try:
        items = _fetch_all_items()
    except Exception as e:
        meta.mark_error(str(e))
        return {"error": str(e)}

    with app.app_context():
        for item in items:
            fields = item.get("fieldData", {})
            cms_id = item.get("id")
            if not cms_id:
                continue

            pub_date = _parse_date(fields.get("publish-date") or fields.get("publishDate"))
            last_pub = _parse_date(item.get("lastPublished") or item.get("lastUpdated"))

            existing = db.session.query(WebflowPost).filter_by(cms_id=cms_id).first()
            if existing:
                existing.name = fields.get("name", "")
                existing.slug = fields.get("slug", "")
                existing.is_draft = item.get("isDraft", True)
                existing.publish_date = pub_date
                existing.last_published = last_pub
                existing.refreshed_at = datetime.utcnow()
            else:
                db.session.add(WebflowPost(
                    cms_id=cms_id,
                    name=fields.get("name", ""),
                    slug=fields.get("slug", ""),
                    is_draft=item.get("isDraft", True),
                    publish_date=pub_date,
                    last_published=last_pub,
                ))

        db.session.commit()
        meta.mark_ok()

    return {"fetched": len(items)}


def get_cached(month_start=None):
    published = (
        db.session.query(WebflowPost)
        .filter_by(is_draft=False)
        .order_by(WebflowPost.publish_date.desc())
        .all()
    )
    drafts = (
        db.session.query(WebflowPost)
        .filter_by(is_draft=True)
        .order_by(WebflowPost.publish_date.asc())
        .all()
    )

    published_this_month = 0
    if month_start:
        published_this_month = (
            db.session.query(WebflowPost)
            .filter(WebflowPost.is_draft == False, WebflowPost.publish_date >= month_start)
            .count()
        )

    return {
        "published": published,
        "drafts": drafts,
        "published_count": len(published),
        "draft_count": len(drafts),
        "published_this_month": published_this_month,
    }
