"""Background cache refresh manager using APScheduler."""

import logging
import threading
from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)
_scheduler = None


def _refresh_all(app):
    """Run all connectors and action items engine. Runs in a background thread."""
    import connectors.webflow_connector as wf
    import connectors.gmb_connector as gmb
    import connectors.gsc_connector as gsc
    import connectors.ga4_connector as ga4
    import connectors.clio_connector as clio
    import engines.action_items as ai

    logger.info("Cache refresh started")
    try:
        wf.fetch(app)
        logger.info("Webflow: refreshed")
    except Exception as e:
        logger.error("Webflow refresh error: %s", e)

    try:
        gmb.fetch(app)
        logger.info("GMB: refreshed")
    except Exception as e:
        logger.error("GMB refresh error: %s", e)

    try:
        gsc.fetch(app)
        logger.info("GSC: refreshed")
    except Exception as e:
        logger.error("GSC refresh error: %s", e)

    try:
        ga4.fetch(app)
        logger.info("GA4: refreshed")
    except Exception as e:
        logger.error("GA4 refresh error: %s", e)

    try:
        clio.fetch(app)
        logger.info("Clio: refreshed")
    except Exception as e:
        logger.error("Clio refresh error: %s", e)

    try:
        with app.app_context():
            count = ai.run_all()
        logger.info("Action items: %d generated", count)
    except Exception as e:
        logger.error("Action items error: %s", e)

    logger.info("Cache refresh complete")


def start(app):
    """Start the background scheduler for daily refresh at 6am."""
    global _scheduler
    if _scheduler and _scheduler.running:
        return

    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(
        func=lambda: _refresh_all(app),
        trigger="cron",
        hour=6,
        minute=0,
        id="daily_refresh",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("Background scheduler started (daily refresh at 06:00)")


def trigger_now(app):
    """Run a full refresh immediately in a background thread."""
    t = threading.Thread(target=_refresh_all, args=(app,), daemon=True)
    t.start()
