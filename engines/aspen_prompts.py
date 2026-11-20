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


def lead_magnet_pdf(c, master=None):
    lm = c["lead_magnet"]
    utm = f"utm_source=guide&utm_medium=pdf&utm_campaign={c['key']}"
    return f"""Please create a downloadable PDF for our "{c['name']}" campaign: {lm['title']}.

FORMAT: {lm['format']}, US Letter, designed to read well on a phone screen and to print cleanly in black and white.
CONTENTS: {lm['contents']}

STRUCTURE
- Cover (for a guide of 1-2 pages, a title band at the top of page 1 instead): the title, a one-line promise ("{c['hook']}"), our logo, and "Prepared by {plan.FIRM_NAME}".
- Body: the contents above, as scannable sections with headings, short paragraphs, tables and checkboxes where they fit.
- Last page: "Ready to put this in place?" with a short paragraph, a "Schedule a Consultation" button linking to \
{plan.BOOKING_URL}?{utm}, our phone number, the Apple Valley office address and archangeltrust.com.
- Footer on every page: {plan.FIRM_NAME} · archangeltrust.com · page number.
- Small print at the end: "This guide is general information about California law, not legal advice for your situation."

DESIGN: Match archangeltrust.com (same logo, Manrope font, colors and button style as /services/living-trusts). Clean, \
plenty of white space, no stock photos of gavels or courtrooms.

RULES
- Every figure, fee, deadline and legal step must come from the approved blog below. Don't add facts that aren't in it.
- Any family example is a clearly labeled hypothetical ("Example: a couple with a $450,000 home..."), never presented \
as a real client.
- Never say "free consultation". Don't quote what we charge.

DELIVERY: Host the PDF on the site at {plan.SITE}/guides/{c['key']}.pdf (not linked from the main navigation). That \
link is used on the {c['landing_page']['slug']} thank-you message and in the Day 0 email of the "{c['name']}" sequence. \
Send me the PDF to review before anything links to it.

{_master_block(master).replace('this page', 'this guide').replace("build this page", "create this guide")}"""


def supporting_materials(c, master=None):
    lm = c["lead_magnet"]
    blog_slug = master.slug if master else c["new_blog"]["slug"]
    return f"""Please create the supporting materials for our "{c['name']}" campaign. Use the same look as \
{lm['title']} (the campaign's guide PDF) and archangeltrust.com, so everything reads as one campaign.

1. EMAIL HEADER: a 600x200 banner for the top of every email in the "{c['name']}" sequence, with the guide title \
and our logo. Light enough to read in dark-mode inboxes.
2. GOOGLE BUSINESS PROFILE POST (Apple Valley profile): a 1200x900 image plus 80-120 words of post copy based on \
the blog's main point, with a "Learn more" button linking to {plan.SITE}/blog/{blog_slug}.
3. SOCIAL POST: a 1080x1080 image and a short caption (under 60 words) for Facebook/Instagram sharing the blog \
link {plan.SITE}/blog/{blog_slug}. Headline idea: "{c['hook']}"
4. OFFICE HANDOUT: a one-page printable flyer for the front desk with the guide's top 3 takeaways and a QR code \
to {plan.SITE}{c['landing_page']['slug']}?utm_source=print&utm_medium=flyer&utm_campaign={c['key']}.

Rules: figures and claims come only from the approved blog below. Never say "free consultation" (the guide itself \
is free; you can say that). Don't quote what we charge. Send me everything to review before it's posted or printed.

{_master_block(master).replace('this page', 'these materials').replace("build this page", "create these materials")}"""


def email_sequence(c, master=None):
    rows = "\n".join(f"- Day {e['day']}: subject \"{e['subject']}\": {e['goal']}" for e in c["sequence"])
    return f"""Please build an automated email sequence for the "{c['name']}" campaign.

Trigger: a contact is created with property campaign = "{c['key']}" (they downloaded {c['lead_magnet']['title']}).
Exit: stop the sequence as soon as they book a consultation.
From: Victoria P. Martin, {plan.FIRM_NAME}. Every email ends with a "Schedule a Consultation" button → \
{plan.BOOKING_URL}?utm_source=aspen&utm_medium=email&utm_campaign={c['key']}

Emails:
{rows}

The Day 0 email delivers the guide as a link to {plan.SITE}/guides/{c['key']}.pdf (the PDF is created separately; \
check that link works before turning the sequence on). Use the campaign's email header banner at the top of each email.

Rules: short (120-200 words), personal, one call to action each. Never say "free consultation". Don't quote what we charge.

{_master_block(master).replace('this page', 'these emails').replace("build this page", "build these emails")}"""
