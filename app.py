"""Archangel Command Center — main Flask application."""

import os
from datetime import datetime, date
from flask import Flask, render_template, request, jsonify, flash
from models import db, CacheMetadata, ClioBooking, ActionItem, AdRecommendation
import config

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(config.DATA_DIR, 'dashboard.db')}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = config.SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

db.init_app(app)

with app.app_context():
    db.create_all()

# Start background scheduler and immediately kick off a full data refresh
from engines import cache_manager
cache_manager.start(app)
cache_manager.trigger_now(app)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _month_start():
    return date.today().replace(day=1)


def _current_target():
    month = date.today().strftime("%B").lower()
    return config.MONTHLY_TARGETS.get(month, config.MONTHLY_TARGETS["default"])


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def overview():
    from connectors import webflow_connector, gmb_connector, gsc_connector, google_ads_connector, ga4_connector, clio_connector
    from engines import action_items as ai

    if not db.session.query(ActionItem).filter_by(is_dismissed=False).first():
        ai.run_all()

    wf_data = webflow_connector.get_cached(month_start=_month_start())
    gmb_data = gmb_connector.get_cached()
    gsc_data = gsc_connector.get_cached()
    ads_data = google_ads_connector.get_cached()
    ga4_data  = ga4_connector.get_cached()
    clio_data = clio_connector.get_cached()

    target = _current_target()
    bookings_count = (
        db.session.query(ClioBooking)
        .filter(ClioBooking.booking_date >= _month_start())
        .count()
    )

    latest_snap = ads_data["snapshots"][-1] if ads_data["snapshots"] else None
    sd_gmb = gmb_data.get("SD")
    top_items = ai.get_all()[:5]
    sources = {k: CacheMetadata.get(k) for k in ("webflow", "gmb", "gsc", "google_ads", "ga4", "clio")}

    return render_template(
        "overview.html",
        target=target,
        bookings_count=bookings_count,
        posts_this_month=wf_data["published_this_month"],
        latest_snap=latest_snap,
        sd_gmb=sd_gmb,
        gsc_summary=gsc_data["summary"],
        ga4=ga4_data,
        clio=clio_data,
        action_items=top_items,
        sources=sources,
        today=date.today(),
        month_name=date.today().strftime("%B"),
        is_stub=config.STUBS,
    )


@app.route("/paid-ads")
def paid_ads():
    from connectors import google_ads_connector
    data = google_ads_connector.get_cached()
    meta = CacheMetadata.get("google_ads")
    return render_template("paid_ads.html", **data, meta=meta)


@app.route("/gmb")
def gmb():
    from connectors import gmb_connector
    data = gmb_connector.get_cached()
    meta = CacheMetadata.get("gmb")
    return render_template("gmb.html", sd=data.get("SD"), av=data.get("AV"),
                           meta=meta, is_stub=config.STUBS["gmb"], today=date.today())


@app.route("/seo")
def seo():
    from connectors import gsc_connector, webflow_connector
    gsc_data = gsc_connector.get_cached()
    wf_data = webflow_connector.get_cached()
    meta = CacheMetadata.get("gsc")
    return render_template("seo_rankings.html",
                           queries=gsc_data["queries"],
                           summary=gsc_data["summary"],
                           blog_count=wf_data["published_count"],
                           meta=meta,
                           is_stub=config.STUBS["gsc"])


@app.route("/content-pipeline")
def content_pipeline():
    from connectors import webflow_connector, keywords_connector
    wf_data = webflow_connector.get_cached(month_start=_month_start())
    kw_data = keywords_connector.fetch()
    meta = CacheMetadata.get("webflow")
    return render_template("content_pipeline.html",
                           published=wf_data["published"],
                           drafts=wf_data["drafts"],
                           kw_data=kw_data,
                           meta=meta)


@app.route("/competitor-intel")
def competitor_intel():
    from connectors import seo_db_connector, competitor_reports_connector
    seo_data = seo_db_connector.fetch()
    report_data = competitor_reports_connector.fetch()
    return render_template("competitor_intel.html",
                           seo_data=seo_data,
                           report_data=report_data)


@app.route("/bookings")
def bookings():
    all_bookings = (
        db.session.query(ClioBooking)
        .order_by(ClioBooking.booking_date.desc())
        .all()
    )
    target = _current_target()
    count = (
        db.session.query(ClioBooking)
        .filter(ClioBooking.booking_date >= _month_start())
        .count()
    )
    from connectors import clio_connector
    clio_data = clio_connector.get_cached()
    return render_template("bookings.html", bookings=all_bookings,
                           count=count, target=target, today=date.today().isoformat(),
                           clio=clio_data)


@app.route("/guide")
def guide():
    return render_template("guide.html")


@app.route("/ad-strategy")
def ad_strategy():
    today    = date.today()
    pending     = db.session.query(AdRecommendation).filter_by(status="pending").order_by(AdRecommendation.created_at.desc()).all()
    awaiting    = db.session.query(AdRecommendation).filter_by(status="approved").order_by(AdRecommendation.reviewed_at.desc()).all()
    implemented = db.session.query(AdRecommendation).filter_by(status="implemented").order_by(AdRecommendation.implemented_at.desc()).all()
    return render_template("ad_strategy.html", pending=pending, awaiting=awaiting,
                           implemented=implemented, today=today)


# ── API endpoints ─────────────────────────────────────────────────────────────

@app.route("/api/ads/upload", methods=["POST"])
def upload_ads():
    f = request.files.get("report_file")
    if not f or not f.filename:
        return jsonify({"error": "No file provided"}), 400

    from connectors import google_ads_connector
    snap, err = google_ads_connector.save_upload(f.read(), f.filename)
    if err:
        return jsonify({"error": err}), 422

    from engines import action_items as ai
    ai.run_all()
    return jsonify({
        "ok": True,
        "snapshot_date": snap.snapshot_date.isoformat(),
        "period_start": snap.period_start.isoformat() if snap.period_start else None,
        "period_end": snap.period_end.isoformat() if snap.period_end else None,
        "spend": snap.total_spend,
        "cpa": snap.cpa,
    })


@app.route("/api/refresh/<source>", methods=["POST"])
def refresh_source(source):
    from connectors import webflow_connector, gmb_connector, gsc_connector
    from engines import action_items as ai, cache_manager as cm

    if source == "all":
        cm.trigger_now(app)
        return jsonify({"ok": True, "message": "Full refresh started in background"})
    elif source == "webflow":
        webflow_connector.fetch(app)
    elif source == "gmb":
        gmb_connector.fetch(app)
    elif source == "gsc":
        gsc_connector.fetch(app)
    elif source == "ga4":
        from connectors import ga4_connector
        ga4_connector.fetch(app)
    elif source == "clio":
        from connectors import clio_connector
        clio_connector.fetch(app)
    else:
        return jsonify({"error": f"Unknown source: {source}"}), 400

    ai.run_all()
    return jsonify({"ok": True})


@app.route("/api/bookings/add", methods=["POST"])
def add_booking():
    data = request.get_json() or request.form
    try:
        booking_date = date.fromisoformat(data.get("booking_date", date.today().isoformat()))
    except ValueError:
        return jsonify({"error": "Invalid date"}), 400

    booking = ClioBooking(
        booking_date=booking_date,
        location=data.get("location", ""),
        source=data.get("source", ""),
        campaign=data.get("campaign", ""),
        notes=data.get("notes", ""),
    )
    db.session.add(booking)
    db.session.commit()

    from engines import action_items as ai
    ai.run_all()
    return jsonify({"ok": True, "id": booking.id})


@app.route("/api/action-items/dismiss/<int:item_id>", methods=["POST"])
def dismiss_action_item(item_id):
    item = db.session.get(ActionItem, item_id)
    if not item:
        return jsonify({"error": "Not found"}), 404
    item.is_dismissed = True
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/api/action-items/refresh", methods=["POST"])
def refresh_action_items():
    from engines import action_items as ai
    count = ai.run_all()
    return jsonify({"ok": True, "count": count})


@app.route("/api/recommendations", methods=["GET"])
def list_recommendations():
    recs = db.session.query(AdRecommendation).order_by(AdRecommendation.created_at.desc()).all()
    return jsonify([{
        "id": r.id,
        "created_at": r.created_at.isoformat(),
        "category": r.category,
        "priority": r.priority,
        "title": r.title,
        "recommendation": r.recommendation,
        "rationale": r.rationale,
        "status": r.status,
        "reviewed_at": r.reviewed_at.isoformat() if r.reviewed_at else None,
        "implemented_at": r.implemented_at.isoformat() if r.implemented_at else None,
        "implementation_notes": r.implementation_notes,
        "follow_up_date": r.follow_up_date.isoformat() if r.follow_up_date else None,
        "follow_up_notes": r.follow_up_notes,
        "instructions": r.instructions,
        "agent_version": r.agent_version,
    } for r in recs])


@app.route("/api/recommendations", methods=["POST"])
def create_recommendation():
    data = request.get_json()
    if not data or not data.get("title"):
        return jsonify({"error": "title is required"}), 400
    rec = AdRecommendation(
        category=data.get("category", "general"),
        priority=data.get("priority", "medium"),
        title=data["title"],
        recommendation=data.get("recommendation", ""),
        rationale=data.get("rationale", ""),
        agent_version=data.get("agent_version"),
    )
    db.session.add(rec)
    db.session.commit()
    return jsonify({"id": rec.id, "status": rec.status}), 201


@app.route("/api/recommendations/<int:rec_id>/approve", methods=["POST"])
def approve_recommendation(rec_id):
    rec = db.session.get(AdRecommendation, rec_id)
    if not rec:
        return jsonify({"error": "Not found"}), 404
    rec.status = "approved"
    rec.reviewed_at = datetime.utcnow()

    # Generate step-by-step Google Ads UI instructions via Claude
    try:
        import json as _json
        import urllib.request as _urllib
        payload = {
            "model": "claude-sonnet-4-6",
            "max_tokens": 400,
            "system": (
                "You generate exact, numbered step-by-step instructions for making a specific "
                "change in the Google Ads web interface at ads.google.com. Be precise about "
                "menu names, button labels, and field values. Assume the user is already logged "
                "in. Return only the numbered steps, no preamble or closing remarks."
            ),
            "messages": [{"role": "user", "content": (
                f"Generate step-by-step instructions to implement this Google Ads change:\n\n"
                f"Category: {rec.category}\n"
                f"Change: {rec.recommendation}\n"
                f"Rationale: {rec.rationale}\n\n"
                f"The account manages estate planning / probate campaigns in San Diego and Apple Valley, CA."
            )}],
        }
        req = _urllib.Request(
            "https://api.anthropic.com/v1/messages",
            data=_json.dumps(payload).encode(),
            headers={
                "x-api-key": config.ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with _urllib.urlopen(req, timeout=60) as resp:
            data = _json.loads(resp.read())
        rec.instructions = data["content"][0]["text"].strip()
    except Exception as e:
        rec.instructions = f"(Could not generate instructions: {e})"

    db.session.commit()
    return jsonify({"ok": True, "id": rec.id, "status": rec.status, "instructions": rec.instructions})


@app.route("/api/recommendations/<int:rec_id>/reject", methods=["POST"])
def reject_recommendation(rec_id):
    rec = db.session.get(AdRecommendation, rec_id)
    if not rec:
        return jsonify({"error": "Not found"}), 404
    rec.status = "rejected"
    rec.reviewed_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"ok": True, "id": rec.id, "status": rec.status})


@app.route("/api/recommendations/<int:rec_id>/implement", methods=["POST"])
def implement_recommendation(rec_id):
    rec = db.session.get(AdRecommendation, rec_id)
    if not rec:
        return jsonify({"error": "Not found"}), 404
    data = request.get_json() or {}
    rec.status = "implemented"
    rec.implemented_at = datetime.utcnow()
    rec.implementation_notes = data.get("implementation_notes", "")
    follow_up = data.get("follow_up_date")
    if follow_up:
        try:
            rec.follow_up_date = date.fromisoformat(follow_up)
        except ValueError:
            return jsonify({"error": "Invalid follow_up_date — use YYYY-MM-DD"}), 400
    db.session.commit()
    return jsonify({"ok": True, "id": rec.id, "status": rec.status})


@app.route("/api/recommendations/<int:rec_id>/follow-up", methods=["POST"])
def log_follow_up(rec_id):
    rec = db.session.get(AdRecommendation, rec_id)
    if not rec:
        return jsonify({"error": "Not found"}), 404
    data = request.get_json() or {}
    rec.follow_up_notes = data.get("notes", "")
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/api/recommendations/analyze", methods=["POST"])
def trigger_analysis():
    from engines import ads_analyzer
    if ads_analyzer.is_running():
        return jsonify({"ok": False, "message": "Analysis already running"}), 409
    started = ads_analyzer.run_analysis_background(app)
    if not started:
        return jsonify({"ok": False, "message": "Analysis already running"}), 409
    return jsonify({"ok": True, "message": "Analysis started"})


@app.route("/api/summary/generate", methods=["POST"])
def generate_summary():
    from engines import weekly_summary
    text, err = weekly_summary.generate(app)
    if err:
        return jsonify({"error": err}), 500
    return jsonify({"ok": True, "summary": text})


@app.route("/api/debug/gsc")
def debug_gsc():
    try:
        from connectors.gsc_connector import _fetch_live
        queries, summary = _fetch_live()
        return jsonify({"ok": True, "queries": len(queries), "summary": summary})
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5001)
