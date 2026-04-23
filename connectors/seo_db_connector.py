"""Read-only queries against the estate_planning_seo_analyzer SQLite database."""

import sqlite3
import config


def _connect():
    """Open a read-only connection to the SEO analyzer DB."""
    uri = f"file:{config.SEO_DB_PATH}?mode=ro"
    return sqlite3.connect(uri, uri=True)


def fetch():
    """Return top competitor keywords and business summary."""
    try:
        conn = _connect()
        cur = conn.cursor()
    except Exception as e:
        return {"error": str(e), "keywords": [], "businesses": [], "stats": {}}

    try:
        # Top keywords across all businesses
        cur.execute("""
            SELECT k.keyword, k.frequency, k.category, b.name, b.location
            FROM keyword k
            JOIN business b ON k.business_id = b.id
            WHERE b.status = 'completed'
            ORDER BY k.frequency DESC, k.relevance_score DESC
            LIMIT 60
        """)
        rows = cur.fetchall()
        keywords = [
            {"keyword": r[0], "frequency": r[1], "category": r[2],
             "business": r[3], "location": r[4]}
            for r in rows
        ]

        # Aggregate: unique keywords with business count
        cur.execute("""
            SELECT k.keyword, COUNT(DISTINCT k.business_id) as biz_count,
                   k.category, SUM(k.frequency) as total_freq
            FROM keyword k
            JOIN business b ON k.business_id = b.id
            WHERE b.status = 'completed'
            GROUP BY LOWER(k.keyword)
            ORDER BY biz_count DESC, total_freq DESC
            LIMIT 50
        """)
        rows = cur.fetchall()
        aggregated = [
            {"keyword": r[0], "businesses": r[1], "category": r[2], "total_freq": r[3]}
            for r in rows
        ]

        # Business list
        cur.execute("""
            SELECT name, website, location, status, last_analyzed
            FROM business ORDER BY name
        """)
        biz_rows = cur.fetchall()
        businesses = [
            {"name": r[0], "website": r[1], "location": r[2],
             "status": r[3], "last_analyzed": r[4]}
            for r in biz_rows
        ]

        # Stats
        cur.execute("SELECT COUNT(*) FROM business WHERE status='completed'")
        completed = cur.fetchone()[0]
        cur.execute("SELECT COUNT(DISTINCT LOWER(keyword)) FROM keyword")
        unique_kws = cur.fetchone()[0]

    except Exception as e:
        conn.close()
        return {"error": str(e), "keywords": [], "businesses": [], "aggregated": [], "stats": {}}
    finally:
        conn.close()

    return {
        "keywords": keywords,
        "aggregated": aggregated,
        "businesses": businesses,
        "stats": {
            "completed_businesses": completed,
            "unique_keywords": unique_kws,
            "total_businesses": len(businesses),
        },
    }
