"""Campaign blog drafts — the old seo-content-engine, rebuilt around the 30-day roadmap.

Aspen publishes the live blog, so nothing here touches Webflow: each draft is
written from its micro-campaign's research (target keyword, pain point, harvested
search terms), stored in the dashboard for review, and handed to Aspen to publish.
"""

import logging
import re
import threading
from datetime import datetime

import roadmap_plan as plan
from engines import claude_client
from models import db, BlogDraft, WebflowPost

log = logging.getLogger(__name__)


def statutory_fee(value):
    """One party's ordinary fee under Probate Code §10800/§10810 (executor and attorney each get this)."""
    fee, rest = 0.0, value
    for size, rate in ((100_000, .04), (100_000, .03), (800_000, .02), (9_000_000, .01), (15_000_000, .005)):
        take = min(rest, size)
        fee, rest = fee + take * rate, rest - take
        if rest <= 0:
            break
    return round(fee)


FEE_EXAMPLES = [(v, statutory_fee(v)) for v in (250_000, 350_000, 450_000, 500_000, 650_000, 750_000, 900_000, 1_000_000)]
FEE_TABLE = "\n".join(f"- ${v:,} gross estate: ${f:,} each, ${2 * f:,} executor + attorney combined" for v, f in FEE_EXAMPLES)

# Every dollar figure a draft may state without a human checking it first.
KNOWN_AMOUNTS = {208_850, 184_500, 100_000, 200_000, 800_000, 9_000_000, 15_000_000, 25_000_000, 4_000, 3_000}
for _v, _f in FEE_EXAMPLES:
    KNOWN_AMOUNTS |= {_v, _f, 2 * _f, _v - 200_000, round((_v - 200_000) * .02)}


FEE_FOR = {v: f for v, f in FEE_EXAMPLES}


def unverified_amounts(html):
    """Dollar figures a human should check: unknown amounts, plus fees that don't match
    the estate value they're quoted next to (e.g. "$46,000 on a $900,000 estate")."""
    text = re.sub(r"<[^>]+>", " ", html)
    flagged = set()
    for sentence in re.split(r"(?<=[.!?])\s+|\n", text):
        amounts = [int(m.replace(",", "")) for m in re.findall(r"\$([\d,]{4,})", sentence)]
        flagged |= {a for a in amounts if a not in KNOWN_AMOUNTS}
        estates = {a for a in amounts if a in FEE_FOR and re.search(
            rf"\${a:,}(?:\s+gross)?\s+(?:estate|home|house|property)|(?:estate|home|house|property|worth)[^$]{{0,40}}\${a:,}", sentence, re.I)}
        if len(estates) == 1:
            v = estates.pop()
            ok = {FEE_FOR[v], 2 * FEE_FOR[v], v - 200_000, round((v - 200_000) * .02), 4_000, 3_000, 100_000, 800_000}
            flagged |= {a for a in amounts if a not in FEE_FOR and a not in ok and a < 200_000}
    return sorted(flagged)


SYSTEM_PROMPT = """You are the SEO content writer for Archangel Trust, an estate planning firm in Apple Valley, \
California (High Desert and Inland Empire) with 20+ years of experience. Attorney: Victoria P. Martin. \
4.8 stars on Google.

Write ONE blog post that feeds a specific Google Ads micro-campaign. The post must:
- Answer the target search query directly in the first 2-3 sentences (featured-snippet style).
- Use the target keyword in the title, the first paragraph and at least 2 H2s; work the supporting \
search terms in naturally where they fit.
- Be 1,200-1,800 words, authoritative yet approachable, written for California homeowners and families.
- Use 4-6 H2 sections (h3 for subsections), bullet/numbered lists where useful, and cite California \
Probate Code sections where it's accurate to do so. Never invent statistics, case results or quotes.
- Treat probate as the problem and estate planning (living trusts, wills) as the solution.
- Include a mid-post callout and a closing section that both point to the campaign's free guide and landing \
page, then to booking a consultation.
- NEVER say "free consultation" or imply consultations are free. Use "Book Your Consultation" or \
"Schedule a Consultation". (The guide download is free; say so.)
- Link 2-3 related existing posts using relative /blog/<slug> URLs from the list provided. Link the landing \
page with its relative path.

CURRENT CALIFORNIA FIGURES (use these exactly; don't quote any other dollar threshold):
- Small-estate limit (Probate Code §13100): $208,850 for deaths on or after April 1, 2025 \
(it was $184,500 before then; it adjusts every 3 years).
- Statutory probate fees (§10800 executor, §10810 attorney), each: 4% of the first $100K, 3% of the next \
$100K, 2% of the next $800K, 1% of the next $9M, 0.5% of the next $15M. Calculated on gross estate value. \
Executor + attorney together = double. Don't do fee arithmetic yourself: only use examples from this table:
{fee_table}
- Don't state what Archangel charges for a trust; say fees are discussed at the consultation.

HTML: only h2, h3, p, ul, ol, li, strong, em, a. No h1, no wrapper tags.

Respond in EXACTLY this format, nothing before or after:
TITLE: <50-65 chars, contains the target keyword>
SLUG: <url-slug>
META: <150-160 char meta description containing the keyword>
===BODY===
<the HTML body>"""


CLUSTER_FOR = {"avoid-probate": "Avoiding probate", "living-trust": "Living trust",
               "privacy": "Probate records", "new-year": "Estate planning"}


def _user_prompt(c, existing_slugs):
    prefix = CLUSTER_FOR.get(c["key"], "")
    cluster = next((k for k in plan.KEYWORD_CLUSTERS if prefix and k["topic"].startswith(prefix)), None)
    terms = cluster["top"] if cluster else []
    return f"""Campaign: {c['name']} (week {c['week']}, {c['dates']})
Working title: {c['new_blog']['title']}
Suggested slug: {c['new_blog']['slug']}
Target keyword: {c['new_blog']['target_kw']}
Angle: {c['new_blog']['angle']}

Reader's pain point: {c['pain']}
Campaign promise: {c['hook']}
Supporting search terms people use to find us: {'; '.join(terms + c['ads']['keywords'])}

Free guide to promote: "{c['lead_magnet']['title']}" ({c['lead_magnet']['format']}): {c['lead_magnet']['contents']}
Landing page (link it): {c['landing_page']['slug']}
Booking: "Book Your Consultation" -> {c['landing_page']['slug']}

Our existing posts you can link to: {', '.join('/blog/' + s for s in existing_slugs)}"""


def _parse(text):
    head, sep, body = text.partition("===BODY===")
    if not sep:
        raise ValueError("response missing ===BODY=== marker")
    fields = dict(re.findall(r"^(TITLE|SLUG|META):\s*(.+)$", head, re.M))
    if "TITLE" not in fields:
        raise ValueError("response missing TITLE")
    return fields["TITLE"].strip(), fields.get("SLUG", "").strip(), fields.get("META", "").strip(), body.strip()


def _write(app, draft_id):
    with app.app_context():
        draft = db.session.get(BlogDraft, draft_id)
        c = next(x for x in plan.CAMPAIGNS if x["key"] == draft.campaign_key)
        try:
            slugs = [p.slug for p in WebflowPost.query.filter_by(is_draft=False).all() if p.slug]
            text = claude_client.call(SYSTEM_PROMPT.replace("{fee_table}", FEE_TABLE), _user_prompt(c, slugs), max_tokens=8000)
            title, slug, meta, body = _parse(text)
            if re.search(r"free consult", body, re.I):
                raise ValueError('draft used "free consultation" language — regenerate')
            draft.title, draft.slug, draft.meta_description, draft.body_html = title, slug or c["new_blog"]["slug"], meta, body
            draft.word_count = len(re.sub(r"<[^>]+>", " ", body).split())
            draft.status = "draft"
            odd = unverified_amounts(body)
            draft.error = ("Check these figures before sending to Aspen: " + ", ".join(f"${a:,}" for a in odd)) if odd else None
        except Exception as e:
            log.exception("blog draft %s failed", draft_id)
            draft.status, draft.error = "failed", str(e)[:500]
        draft.updated_at = datetime.utcnow()
        db.session.commit()


def start(app, campaign_key):
    """Queue a new draft for the campaign and write it in the background. Returns the draft."""
    c = next(x for x in plan.CAMPAIGNS if x["key"] == campaign_key)
    draft = BlogDraft(campaign_key=campaign_key, target_kw=c["new_blog"]["target_kw"],
                      title=c["new_blog"]["title"], status="generating")
    db.session.add(draft)
    db.session.commit()
    threading.Thread(target=_write, args=(app, draft.id), daemon=True).start()
    return draft
