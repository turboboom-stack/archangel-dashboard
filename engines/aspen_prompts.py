"""Copy-ready prompts for the Aspen agent, which builds and edits archangeltrust.com.

Once a campaign's blog is approved by the owners it is the master document: every
prompt that builds campaign assets embeds it and tells Aspen to take figures,
process steps and consequences from it and nowhere else.
"""

import re

import roadmap_plan as plan


def _plain(html):
    text = re.sub(r"</(p|li|h2|h3)>", "\n", html or "")
    text = re.sub(r"<h2[^>]*>", "\n## ", text)
    text = re.sub(r"<h3[^>]*>", "\n### ", text)
    text = re.sub(r"<li[^>]*>", "- ", text)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _master_block(master):
    if not master:
        return ("SOURCE OF TRUTH: not approved yet. Don't build this page until the blog below is approved by "
                "the owners; this prompt will be regenerated with the approved text.")
    return (f"SOURCE OF TRUTH: the blog below was approved by the owners. It is the master document. "
            f"Every figure, fee, timeline, legal step and consequence on this page must match it exactly. "
            f"If the page outline below conflicts with the approved blog, the blog wins. Don't add facts that "
            f"aren't in it.\n\n=== APPROVED BLOG: {master.title} ===\n{_plain(master.body_html)}\n=== END APPROVED BLOG ===")


def landing_page(c, master=None):
    lp, lm = c["landing_page"], c["lead_magnet"]
    utm = f"utm_source=google&utm_medium=cpc&utm_campaign={c['key']}"
    sections = "\n".join(f"{i}. {s}" for i, s in enumerate(lp["sections"], 1))
    headlines = ", ".join(f'"{h}"' for h in c["ads"]["headlines"][:4])
    return f"""Please build a new landing page on archangeltrust.com for our "{c['name']}" Google Ads campaign.

URL: {plan.SITE}{lp['slug']}
Status: set to noindex and leave it out of the main navigation until I confirm launch ({c['launch']}).

DESIGN: Match our existing service pages exactly, using /services/living-trusts as the template: same header, footer, \
Manrope font, colors, button style, spacing and mobile layout. Remove the main navigation menu from this page (keep the \
logo and phone number) so visitors stay focused on the offer. Must load fast and look right on a phone first.

MESSAGE MATCH: People arrive from ads saying things like {headlines}. The headline must repeat that promise.

HERO
- H1: {lp['headline']}
- Subhead: {lp['sub']}
- Primary button: "Get {lm['title']}" (scrolls to the form)
- Secondary button: "Schedule a Consultation" → {plan.BOOKING_URL}?{utm}
- Trust line under the buttons: "20+ years · 4.8 stars on Google · Apple Valley office"

PAGE SECTIONS (top to bottom)
{sections}

LEAD FORM (place in the hero on desktop, directly under it on mobile, and repeat at the bottom)
- Heading: "Get {lm['title']}" - {lm['format']}: {lm['contents']}
- Fields: Name, Email, Phone (Phone optional)
- Hidden field: campaign = {c['key']} (also capture gclid and utm_* from the URL into hidden fields)
- On submit: POST the form to our dashboard webhook {plan.DASHBOARD_URL}/webhook/lead-magnet (JSON, fields as named above) \
so the lead goes to Aspen tagged campaign={c['key']}, then show a thank-you message with the PDF download link and a \
"Schedule a Consultation" button.
- Fire GA4 event form_submit (form_name="{c['key']}") and the Google Ads conversion on success.

COPY RULES
- Firm name: {plan.FIRM_NAME}. Attorney: Victoria P. Martin.
- Never say "free consultation". Use "Schedule a Consultation" or "Book Your Consultation". (The guide is free; you can say that.)
- Don't quote what we charge for a trust.
- Plain, warm language for California homeowners and families. Short paragraphs, scannable.

SEO / TRACKING
- Title tag: {lp['headline']} | {plan.FIRM_NAME}
- Meta description: {lp['sub'][:155]}
- GA4 + Google Ads tags must be on this page.
- Link to the supporting blog post once it's live: /blog/{(master.slug if master else c['new_blog']['slug'])}

{_master_block(master)}

When it's built, send me the preview link and a screenshot of the mobile view."""


def publish_blog(c, draft):
    return f"""Please publish this approved blog post on archangeltrust.com/blog. It was approved by the owners, \
so publish the text exactly as written (fix formatting only, no wording changes).

- URL: /blog/{draft.slug}
- Title (H1): {draft.title}
- Meta description: {draft.meta_description}
- Author: {plan.FIRM_NAME}
- Category: {'Estate Planning' if c['key'] != 'avoid-probate' else 'Probate & Estate Planning'}
- Keep every internal link as written. The links to {c['landing_page']['slug']} go to a campaign landing page.
- Add a callout box after the 2nd section and at the end: "Get {c['lead_magnet']['title']}" → {c['landing_page']['slug']}
- Also add that same callout to these existing posts: {', '.join('/blog/' + s for s in c['source_blogs'])}

=== POST BODY (HTML) ===
{draft.body_html}
=== END ==="""


def email_sequence(c, master=None):
    rows = "\n".join(f"- Day {e['day']}: subject \"{e['subject']}\": {e['goal']}" for e in c["sequence"])
    return f"""Please build an automated email sequence for the "{c['name']}" campaign.

Trigger: a contact is created with property campaign = "{c['key']}" (they downloaded {c['lead_magnet']['title']}).
Exit: stop the sequence as soon as they book a consultation.
From: Victoria P. Martin, {plan.FIRM_NAME}. Every email ends with a "Schedule a Consultation" button → \
{plan.BOOKING_URL}?utm_source=aspen&utm_medium=email&utm_campaign={c['key']}

Emails:
{rows}

Rules: short (120-200 words), personal, one call to action each. Never say "free consultation". Don't quote what we charge.

{_master_block(master).replace('this page', 'these emails').replace("build this page", "build these emails")}"""
