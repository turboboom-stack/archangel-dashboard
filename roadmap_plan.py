"""30-day micro-campaign roadmap (Nov 23 - Dec 20, 2026).

Each weekly campaign = one blog + one landing page + one Google Ads ad group +
one lead magnet + one Aspen email sequence, all built on the same pain point
and the same creative. Topics come from 12 months of GA4 blog traffic and 16
months of Search Console queries (pulled 2026-11-20).

Spend stays in Apple Valley / High Desert (SD budget paused). Content follows
the 90/10 rule: probate traffic is used as the hook, but every offer sells
estate planning (living trusts, wills). No "free consultation" language in
landing pages or emails.
"""

BOOKING_URL = "https://calendly.com/archangel-trust-cmartin/consultation"
GEO = "Apple Valley, Victorville, Hesperia, Barstow (+15 mi) — SD paused"

DATA_AS_OF = "2026-11-20"

FINDINGS = [
    {
        "severity": "danger",
        "title": "GA4 stopped recording traffic on Oct 14",
        "detail": "GA4 sessions fell from ~40/day to ~3/day on Oct 14, but Search Console shows Google clicks "
                  "steady at 40-55/week through November. Traffic didn't collapse; tracking did. Every "
                  "dashboard number since Oct 14 is undercounted, and ads can't optimize without it.",
    },
    {
        "severity": "danger",
        "title": "No Google Ads conversion tag on the site",
        "detail": "Home, /contact, /request-a-consultation and the top blog only load gtag G-X5TNYWXNXM - no AW- "
                  "conversion tag. Paid search fell from 96 sessions (Sep) to ~0 (Nov). Fix before any new spend.",
    },
    {
        "severity": "danger",
        "title": "Booking link changed",
        "detail": "Site CTAs point to calendly.com/cameronwoodbury/archangel-financial-introduction-trust, "
                  "not the attorney consultation link (calendly.com/archangel-trust-cmartin/consultation). Confirm which is correct.",
    },
    {
        "severity": "info",
        "title": "Blog: Aspen publishes, the dashboard drafts",
        "detail": "Aspen runs the live blog. Each campaign's Blog tab writes a draft built on that campaign's keywords "
                  "and landing page; review it here and hand it to Aspen to publish.",
    },
    {
        "severity": "warning",
        "title": "6 near-duplicate probate posts cannibalize each other",
        "detail": "when-probate-is-required / -not-required / -needed / -not-needed / -necessary / is-not-required. "
                  "Consolidate into the winner (/blog/when-probate-is-not-required-california) with 301s.",
    },
    {
        "severity": "info",
        "title": "Blogs are the organic engine",
        "detail": "1,093 of the blog's sessions in 12 months came from Organic Search. 5 posts drive 85% of blog "
                  "traffic, and they rank on page 1 (avg. position 6.6-7.8).",
    },
]

# 12-month GA4 pageviews + 16-month GSC clicks / impressions / avg position
TOP_BLOGS = [
    {"slug": "when-probate-is-not-required-california", "views": 551, "clicks": 179, "impr": 11892, "pos": 6.8, "campaign": "avoid-probate"},
    {"slug": "are-probate-records-public-california", "views": 248, "clicks": 168, "impr": 17309, "pos": 6.6, "campaign": "privacy"},
    {"slug": "when-probate-is-required-california", "views": 200, "clicks": 94, "impr": 17088, "pos": 8.9, "campaign": "avoid-probate"},
    {"slug": "who-pays-probate-attorney-fees-california", "views": 115, "clicks": 89, "impr": 11371, "pos": 7.8, "campaign": "avoid-probate"},
    {"slug": "what-is-the-best-trust-to-avoid-probate", "views": 79, "clicks": 62, "impr": 10433, "pos": 6.9, "campaign": "living-trust"},
    {"slug": "are-probate-sales-cash-only", "views": 38, "clicks": 33, "impr": 3677, "pos": 4.0, "campaign": None},
    {"slug": "when-to-start-estate-planning", "views": 13, "clicks": 7, "impr": 3518, "pos": 13.3, "campaign": "new-year"},
    {"slug": "how-to-set-up-a-living-trust-in-san-diego-california", "views": 16, "clicks": 7, "impr": 744, "pos": 10.1, "campaign": "living-trust"},
]

# Topic clusters from 500 GSC queries (16 months)
KEYWORD_CLUSTERS = [
    {"topic": "Living trust (commercial intent)", "impr": 5075, "clicks": 18, "note": "Highest buyer intent, but we rank 11-32. Ads fill the gap.",
     "top": ["living trust attorney (2,717 impr, pos 32)", "living trust near me (842, pos 18)", "california living trust attorney (611, pos 11)", "living trust lawyers near me (172, pos 17)"]},
    {"topic": "Estate planning (general + local)", "impr": 5361, "clicks": 29, "note": "Local + timing questions.",
     "top": ["trust attorney near me (3,167, pos 43)", "when to start estate planning (582, pos 13)", "probate attorney victorville (298, pos 8)", "at what point should someone start estate planning (160, pos 2)"]},
    {"topic": "Avoiding probate / when it's required", "impr": 4425, "clicks": 55, "note": "Our strongest organic cluster. Pain point = cost + delay.",
     "top": ["when is probate required in california (653, pos 11)", "when is probate required (359, pos 9)", "avoiding probate in california (329, pos 35)", "does a trust avoid probate (146, pos 3)"]},
    {"topic": "Probate records / privacy", "impr": 1619, "clicks": 8, "note": "Pain point = family affairs made public.",
     "top": ["are probate records public (591, pos 12)", "are wills public record in california (316, pos 10)", "are estates public record (180, pos 23)", "are trusts public record in california (14, pos 18)"]},
    {"topic": "Probate fees / cost", "impr": 353, "clicks": 2, "note": "Feeds the $ figure in the Avoid Probate creative.",
     "top": ["who pays probate attorney fees in california (147)", "california estate planning attorney fees (65)", "california probate attorney fees (17)"]},
]

# CA Probate Code §10800/§10810 statutory fees on a $450K High Desert home:
# 4% of first $100K + 3% of next $100K + 2% of next $250K = $12,000 attorney + $12,000 executor = $24,000.
CAMPAIGNS = [
    {
        "key": "avoid-probate",
        "week": 1,
        "dates": "Nov 23 - 29",
        "name": "Avoid Probate",
        "pain": "California probate takes 12-18 months, is public, and statutory fees on a $450K High Desert home add up to ~$24,000, paid out of what your family inherits.",
        "hook": "A living trust keeps your home out of probate court.",
        "source_blogs": ["when-probate-is-not-required-california", "when-probate-is-required-california", "who-pays-probate-attorney-fees-california"],
        "new_blog": {"title": "How Much Does Probate Cost in California? (2026 Fee Breakdown)", "slug": "how-much-does-probate-cost-california",
                     "target_kw": "california probate fees", "angle": "Walk through §10810 statutory fees with 3 home-value examples ($350K / $450K / $650K), then show the living-trust alternative. CTA to the guide."},
        "landing_page": {"slug": "/avoid-probate", "headline": "Keep Your Home Out of Probate Court",
                         "sub": "California probate can cost your family $24,000+ and take over a year. A living trust avoids it. Here's how.",
                         "sections": ["The real cost of probate (fee table with $350K/$450K/$650K examples)",
                                      "3 steps to avoid probate: 1) inventory assets 2) create and fund a living trust 3) name successors",
                                      "What happens without a plan (12-18 months, court filings, public record)",
                                      "Why Archangel: 20+ years, 4.8 stars on Google, Apple Valley office",
                                      "Lead magnet form + Book a Consultation button"]},
        "lead_magnet": {"title": "The California Probate-Avoidance Guide", "format": "6-page PDF",
                        "contents": "Probate fee table, 5 assets that skip probate, living-trust funding checklist, 3 family case studies."},
        "ads": {
            "ad_group": "AV | Avoid Probate",
            "keywords": ["[how to avoid probate in california]", "\"avoid probate california\"", "\"living trust to avoid probate\"",
                         "\"does a trust avoid probate\"", "\"when is probate required in california\"", "[probate attorney victorville]",
                         "\"avoid probate apple valley\""],
            "negatives": ["-cash", "-buy", "-house for sale", "-forms", "-diy", "-free", "-jobs", "-court records search"],
            "headlines": ["Avoid Probate in California", "Probate Could Cost $24,000+", "Keep Your Home Out of Court",
                          "Avoid Probate in 3 Steps", "Living Trust Attorney", "Apple Valley Estate Planning",
                          "Get the Free Probate Guide", "20+ Years | 4.8 Stars", "Protect What You Leave Behind",
                          "Book Your Consultation", "Skip 12-18 Months of Probate", "High Desert Trust Attorneys"],
            "descriptions": ["Probate can take 12-18 months and cost $24K+ on a typical home. A living trust avoids it.",
                             "Download our California Probate-Avoidance Guide. Fees, steps, and a funding checklist.",
                             "20+ years helping High Desert families avoid probate. 4.8 stars on Google.",
                             "Talk to an estate planning attorney in Apple Valley. Book your consultation today."],
            "budget_day": 10,
        },
        "sequence": [
            {"day": 0, "subject": "Your California Probate-Avoidance Guide", "goal": "Deliver PDF + 1-line intro to Victoria"},
            {"day": 2, "subject": "What probate actually costs a High Desert family", "goal": "Fee math on a $450K home; why it comes out of the inheritance"},
            {"day": 5, "subject": "\"We thought a will was enough\"", "goal": "Story: will still goes through probate; trust doesn't"},
            {"day": 8, "subject": "The 3 questions to answer before you build a trust", "goal": "Objection handling: cost, time, complexity"},
            {"day": 11, "subject": "Should we look at your situation together?", "goal": "Direct consult CTA + 4.8-star reviews"},
            {"day": 14, "subject": "Last note on probate (for now)", "goal": "Soft close; move to monthly newsletter"},
        ],
    },
    {
        "key": "living-trust",
        "week": 2,
        "dates": "Nov 30 - Dec 6",
        "name": "Living Trust",
        "pain": "People searching \"living trust attorney\" are ready to buy, but we rank 11-32 for these terms. They don't know what a trust costs or whether they need one instead of a will.",
        "hook": "Know exactly what a living trust costs, what's in it, and whether you need one, before you call.",
        "source_blogs": ["what-is-the-best-trust-to-avoid-probate", "do-i-need-a-living-trust-or-a-will-in-california", "how-to-set-up-a-living-trust-in-san-diego-california"],
        "new_blog": {"title": "Living Trust vs. Will in California: Which Do You Actually Need?", "slug": "living-trust-vs-will-california",
                     "target_kw": "living trust vs will california", "angle": "Side-by-side table (cost, probate, privacy, incapacity). Decision checklist. CTA to the checklist download."},
        "landing_page": {"slug": "/living-trust", "headline": "Your Living Trust, Done Right",
                         "sub": "Avoid probate, protect your family, and keep your affairs private, with an attorney who has done this for 20+ years.",
                         "sections": ["Trust vs will comparison table", "What's included: trust, pour-over will, POA, healthcare directive",
                                      "The process in 3 steps (consult, draft and sign, fund)", "FAQs: cost, timing, \"do I have enough assets?\"",
                                      "Reviews + Book a Consultation"]},
        "lead_magnet": {"title": "Living Trust vs. Will: The 10-Minute Checklist", "format": "2-page PDF",
                        "contents": "10 yes/no questions that tell you if you need a trust, plus a document checklist to bring to your consult."},
        "ads": {
            "ad_group": "AV | Living Trust",
            "keywords": ["[living trust attorney]", "\"living trust attorney near me\"", "\"living trust lawyer\"", "[living trust near me]",
                         "\"california living trust attorney\"", "\"living trust victorville\"", "\"living trust apple valley\""],
            "negatives": ["-diy", "-template", "-free", "-online", "-legalzoom", "-forms", "-pdf", "-jobs"],
            "headlines": ["Living Trust Attorney", "Avoid Probate With a Trust", "Trust or Will? Find Out Fast",
                          "Apple Valley Trust Attorney", "Get the 10-Minute Checklist", "20+ Years | 4.8 Stars",
                          "Protect Your Family's Home", "Book Your Consultation", "Trusts, Wills & POAs",
                          "Local High Desert Attorney", "Keep Your Estate Private", "Your Trust, Done Right"],
            "descriptions": ["A living trust avoids probate, protects your family, and keeps your affairs private.",
                             "Not sure if you need a trust or a will? Take our 10-minute checklist and find out.",
                             "Trust, pour-over will, power of attorney and healthcare directive. One plan.",
                             "Apple Valley estate planning attorney with 20+ years experience. Book today."],
            "budget_day": 10,
        },
        "sequence": [
            {"day": 0, "subject": "Your Living Trust vs. Will checklist", "goal": "Deliver PDF + how to score it"},
            {"day": 2, "subject": "What actually goes into a living trust", "goal": "Explain the 4-document package"},
            {"day": 5, "subject": "The step most trusts skip (and why it matters)", "goal": "Funding the trust; DIY failure mode"},
            {"day": 8, "subject": "What does a living trust cost?", "goal": "Cost framing vs probate cost (link to Avoid Probate LP)"},
            {"day": 11, "subject": "Ready to get yours started?", "goal": "Consult CTA + what to bring"},
            {"day": 14, "subject": "Quick question", "goal": "Reply-to-engage: \"What's holding you back?\""},
        ],
    },
    {
        "key": "privacy",
        "week": 3,
        "dates": "Dec 7 - 13",
        "name": "Keep It Private",
        "pain": "Probate files are public. Anyone can look up what you owned, what you owed, and who inherited. Scammers and \"we buy houses\" investors do.",
        "hook": "A trust keeps your family's business out of public court records.",
        "source_blogs": ["are-probate-records-public-california"],
        "new_blog": {"title": "Are Trusts Public Record in California? (And Why It Matters)", "slug": "are-trusts-public-record-california",
                     "target_kw": "are trusts public record in california", "angle": "Contrast probate's public file with a private trust. Real examples of what's visible. CTA to the privacy checklist."},
        "landing_page": {"slug": "/keep-it-private", "headline": "Keep Your Family's Affairs Out of Public Record",
                         "sub": "Probate files are public: assets, debts, heirs. A living trust keeps it private.",
                         "sections": ["What a probate file reveals (example redacted docket)", "Who reads them: investors, scammers, estranged relatives",
                                      "How a trust keeps it private", "Checklist download + Book a Consultation"]},
        "lead_magnet": {"title": "The Estate Privacy Checklist", "format": "1-page PDF",
                        "contents": "8 things that become public in probate and the document that keeps each private."},
        "ads": {
            "ad_group": "AV | Privacy",
            "keywords": ["\"are probate records public\"", "\"are wills public record\"", "\"keep estate private\"",
                         "\"are trusts public record\"", "\"private estate planning\""],
            "negatives": ["-search", "-lookup", "-find", "-court records", "-genealogy", "-free"],
            "headlines": ["Probate Records Are Public", "Keep Your Estate Private", "A Trust Stays Private",
                          "Protect Your Family's Privacy", "Get the Privacy Checklist", "Apple Valley Trust Attorney",
                          "20+ Years | 4.8 Stars", "Book Your Consultation", "Avoid Public Probate Court"],
            "descriptions": ["Probate files show your assets, debts and heirs to anyone who looks. A trust doesn't.",
                             "Download the Estate Privacy Checklist: 8 things that go public in probate.",
                             "High Desert estate planning attorney. Living trusts that keep your affairs private."],
            "budget_day": 5,
        },
        "sequence": [
            {"day": 0, "subject": "Your Estate Privacy Checklist", "goal": "Deliver PDF"},
            {"day": 3, "subject": "What a stranger can learn from a probate file", "goal": "Concrete, redacted example"},
            {"day": 7, "subject": "Wills are public. Trusts aren't.", "goal": "Explain the difference simply"},
            {"day": 10, "subject": "Protecting your family's privacy", "goal": "Consult CTA"},
        ],
    },
    {
        "key": "new-year",
        "week": 4,
        "dates": "Dec 14 - 20",
        "name": "Plan Before 2027",
        "pain": "\"When should I start estate planning?\" is a top question (800+ impressions). The holidays bring families together and these conversations come up. Most people put it off.",
        "hook": "Start 2027 with your estate plan done.",
        "source_blogs": ["when-to-start-estate-planning", "estate-planning-checklist", "what-are-common-estate-planning-mistakes"],
        "new_blog": {"title": "5 Estate Planning Moves to Make Before the New Year", "slug": "estate-planning-before-new-year",
                     "target_kw": "when to start estate planning", "angle": "Year-end checklist: beneficiaries, trust funding, guardians, POA, family talk over the holidays. CTA to the 2027 checklist."},
        "landing_page": {"slug": "/plan-for-2027", "headline": "Start 2027 With Your Estate Plan Done",
                         "sub": "Book in December and we'll have your plan drafted in the new year.",
                         "sections": ["Why now: family time, tax year, health changes", "The 2027 checklist preview",
                                      "What's in a complete plan", "Limited January signing slots + Book a Consultation"]},
        "lead_magnet": {"title": "The 2027 Estate Planning Checklist", "format": "2-page PDF",
                        "contents": "12-item checklist + a holiday family-conversation guide."},
        "ads": {
            "ad_group": "AV | Plan Before 2027",
            "keywords": ["\"when to start estate planning\"", "\"estate planning checklist\"", "\"estate planning attorney near me\"",
                         "\"estate planning apple valley\"", "\"will and trust attorney\""],
            "negatives": ["-free", "-template", "-diy", "-jobs", "-course"],
            "headlines": ["Start 2027 With a Plan", "Estate Planning Checklist", "Plan Before the New Year",
                          "Apple Valley Estate Planning", "Wills, Trusts & POAs", "20+ Years | 4.8 Stars",
                          "Book Your Consultation", "January Signing Slots Open", "Protect Your Family in 2027"],
            "descriptions": ["Get the 2027 Estate Planning Checklist: 12 steps to protect your family this year.",
                             "Book in December, sign in January. Apple Valley estate planning attorney, 20+ years.",
                             "Wills, living trusts, POAs and healthcare directives, done right the first time."],
            "budget_day": 5,
        },
        "sequence": [
            {"day": 0, "subject": "Your 2027 Estate Planning Checklist", "goal": "Deliver PDF"},
            {"day": 2, "subject": "A holiday conversation worth having", "goal": "Family conversation guide"},
            {"day": 6, "subject": "The 3 most common estate planning mistakes", "goal": "Link to blog; build urgency"},
            {"day": 10, "subject": "January signing slots", "goal": "Scarcity + consult CTA"},
            {"day": 14, "subject": "Happy New Year from Archangel", "goal": "Soft close"},
        ],
    },
]

WEEK0_TASKS = [
    ("w0-ga4", "Verify gtag G-X5TNYWXNXM belongs to GA4 property 390363293; fix the tag in Webflow site settings and republish"),
    ("w0-ads-tag", "Install the Google Ads conversion tag (or import GA4 key events form_submit + calendly_booked into Ads)"),
    ("w0-calendly", "Confirm the correct booking link (site uses cameronwoodbury/archangel-financial-introduction-trust)"),
    ("w0-scheduler", "Agree the blog hand-off with Aspen: the dashboard drafts one campaign post per week, Aspen publishes it"),
    ("w0-dedupe", "301 the 5 duplicate 'when probate is required/needed' posts to /blog/when-probate-is-not-required-california"),
    ("w0-clio", "Re-auth Clio (bookings last synced Sep 24) so campaign bookings show here"),
    ("w0-webhook", "Point every landing-page form's Webflow webhook to /webhook/lead-magnet (sends lead + campaign to Aspen)"),
    ("w0-aspen", "In Aspen: create one sequence per campaign, triggered by the contact property campaign=<key>"),
]

CAMPAIGN_TASK_TEMPLATE = [
    ("blog", "Generate the blog draft (Blog tab), review it, send it to Aspen to publish, and add a guide CTA to the source blogs"),
    ("magnet", "Design the lead-magnet PDF and upload it to Webflow assets"),
    ("lp", "Build the landing page in Webflow (copy above), noindex until launch"),
    ("form", "Add the guide form (name, email, phone); hidden field campaign=<key>; webhook to /webhook/lead-magnet"),
    ("aspen", "Build the Aspen email sequence and test with a seed email"),
    ("ads", "Create the Google Ads ad group: keywords, negatives, RSA, sitelinks to LP + blog"),
    ("utm", "Final URL utm_source=google&utm_medium=cpc&utm_campaign=<key>; Calendly link carries utm_campaign"),
    ("qa", "QA: submit a test lead and confirm it shows in Aspen + here, and that conversions fire"),
    ("launch", "Launch the ad group and publish the landing page"),
    ("review", "Day-7 review: search terms, negatives, CTR, landing page conversion rate; log metrics below"),
]


def campaign_tasks(key):
    return [(f"{key}-{tid}", text.replace("<key>", key)) for tid, text in CAMPAIGN_TASK_TEMPLATE]


def all_task_keys():
    keys = [k for k, _ in WEEK0_TASKS]
    for c in CAMPAIGNS:
        keys += [k for k, _ in campaign_tasks(c["key"])]
    return keys


CAMPAIGN_KEYS = {c["key"] for c in CAMPAIGNS}

TARGETS = {"lp_cvr": 0.10, "lead_to_booking": 0.15, "monthly_bookings": 40}
