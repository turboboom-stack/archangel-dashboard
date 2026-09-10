"""
Ads Strategy Analyzer — thin dispatcher over the engines.ads_skills registry.
Runs each skill, persists results as AdRecommendation rows tagged with which skill
produced them (agent_version = "skill:<id>-<date>"), so /ad-strategy can show provenance.
"""

import logging
import threading
from datetime import date

import config
from engines import ads_skills

logger = logging.getLogger(__name__)


def run_analysis(app):
    """Run all ads_skills in the given Flask app context. Returns (count, error_msg)."""
    if not config.ANTHROPIC_API_KEY:
        return 0, "ANTHROPIC_API_KEY not configured"

    with app.app_context():
        from models import db, AdRecommendation

        today = date.today().isoformat()
        count = 0
        errors = []
        for skill_id, module in ads_skills.SKILLS.items():
            try:
                recs = module.run()
            except Exception as e:
                logger.error(f"Skill {skill_id} failed: {e}")
                errors.append(f"{skill_id}: {e}")
                continue

            version = f"skill:{skill_id}-{today}"
            for r in recs:
                db.session.add(AdRecommendation(
                    category=r.get("category", "general"),
                    priority=r.get("priority", "medium"),
                    title=r.get("title", ""),
                    recommendation=r.get("recommendation", ""),
                    rationale=r.get("rationale", ""),
                    agent_version=version,
                ))
                count += 1

        db.session.commit()
        logger.info(f"ads_skills: {count} recommendations added across {len(ads_skills.SKILLS)} skills.")
        return count, ("; ".join(errors) if errors and count == 0 else None)


_analysis_lock = threading.Lock()
_analysis_running = False


def run_analysis_background(app):
    """Spawn a background thread to run analysis. Returns False if already running."""
    global _analysis_running
    if not _analysis_lock.acquire(blocking=False):
        return False
    _analysis_running = True

    def _worker():
        global _analysis_running
        try:
            run_analysis(app)
        finally:
            _analysis_running = False
            _analysis_lock.release()

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    return True


def is_running():
    return _analysis_running
