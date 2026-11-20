"""Owner-approval emails for campaign blogs: the review request, the reminder before
an approval date, and a note to Jordan whenever an owner decides."""

import logging
from datetime import date, datetime, timedelta
from html import escape

import roadmap_plan as plan
from connectors import gmail_connector

logger = logging.getLogger(__name__)


def _campaign(key):
    return next((c for c in plan.CAMPAIGNS if c["key"] == key), None)


def _due(c):
    return date.fromisoformat(c["approval_due"]).strftime("%a %b %-d")


def _link(draft):
    return f"{plan.DASHBOARD_URL}/review/{draft.review_token}"


def _rows(drafts):
    rows = sorted(((_campaign(d.campaign_key), d) for d in drafts), key=lambda x: x[0]["week"])
    html = "".join(
        f'<tr><td style="padding:10px 12px;border-top:1px solid #E5E7EB;">'
        f'<a href="{_link(d)}" style="color:#3B6E5C;font-weight:600;">{escape(d.title)}</a>'
        f'<div style="color:#6B7280;font-size:13px;">{escape(c["name"])} campaign · {d.word_count} words'
        f'{" · revised" if d.revision_of else ""}</div></td>'
        f'<td style="padding:10px 12px;border-top:1px solid #E5E7EB;white-space:nowrap;">{_due(c)}</td></tr>'
        for c, d in rows)
    text = "\n".join(f"- {d.title} (approve by {_due(c)})\n  {_link(d)}" for c, d in rows)
    return html, text


def _wrap(body):
    return (f'<div style="font-family:Arial,sans-serif;color:#1F2937;font-size:15px;line-height:1.55;max-width:620px;">'
            f'{body}<p style="color:#6B7280;font-size:13px;margin-top:24px;">Sent from the {plan.FIRM_NAME} '
            f'marketing dashboard.</p></div>')


def _table(rows_html):
    return ('<table style="border-collapse:collapse;width:100%;margin:12px 0;">'
            '<tr><th align="left" style="padding:6px 12px;color:#6B7280;font-size:13px;">Blog</th>'
            '<th align="left" style="padding:6px 12px;color:#6B7280;font-size:13px;">Approve by</th></tr>'
            f'{rows_html}</table>')


def send_request(drafts):
    """Email Victoria and Chris the review links for one or more drafts."""
    rows_html, rows_text = _rows(drafts)
    n = len(drafts)
    subject = (f"{n} blog posts ready for your approval" if n > 1
               else f"Blog ready for your approval: {drafts[0].title}")
    intro = (f"{'These' if n > 1 else 'This'} {'are the blogs' if n > 1 else 'is the blog'} for the next month's "
             f"marketing campaigns. Each link opens the full post with Approve and Request changes buttons at the bottom.")
    gate = (f"{plan.APPROVER}, your approval is what releases each campaign. Chris, your notes are welcome on any "
            f"of them too. Once a post is approved it becomes the reference for that campaign's landing page, ads "
            f"and follow-up emails, so please check the dollar figures and Probate Code references closely.")
    html = _wrap(f"<p>Hi Victoria and Chris,</p><p>{intro}</p>{_table(rows_html)}<p>{gate}</p>"
                 f"<p>If you'd like changes, add a note describing them and I'll send back a revised version.</p>"
                 f"<p>Thanks,<br>Jordan</p>")
    text = f"Hi Victoria and Chris,\n\n{intro}\n\n{rows_text}\n\n{gate}\n\nThanks,\nJordan"
    gmail_connector.send(list(plan.REVIEWER_EMAILS.values()), subject, html, text)


def send_reminders(app):
    """Daily: remind Victoria about posts she hasn't decided on that are due in REMINDER_DAYS days or less."""
    from models import db, BlogDraft, BlogReview
    with app.app_context():
        pending = []
        for d in BlogDraft.query.filter(BlogDraft.status.in_(("in_review", "changes_requested")),
                                        BlogDraft.review_token.isnot(None),
                                        BlogDraft.reminder_sent_at.is_(None)).all():
            c = _campaign(d.campaign_key)
            decided = BlogReview.query.filter_by(draft_id=d.id, reviewer=plan.APPROVER).first()
            if c and not decided \
                    and date.fromisoformat(c["approval_due"]) - date.today() <= timedelta(days=plan.REMINDER_DAYS):
                pending.append(d)
        if not pending:
            return 0
        rows_html, rows_text = _rows(pending)
        subject = f"Reminder: {len(pending)} blog post{'s' if len(pending) > 1 else ''} waiting for your approval"
        intro = "A quick reminder: these posts are coming up on their approval dates. Each campaign launches once its post is approved."
        html = _wrap(f"<p>Hi Victoria,</p><p>{intro}</p>{_table(rows_html)}<p>Thanks,<br>Jordan</p>")
        text = f"Hi Victoria,\n\n{intro}\n\n{rows_text}\n\nThanks,\nJordan"
        try:
            gmail_connector.send(plan.REVIEWER_EMAILS[plan.APPROVER], subject, html, text)
        except Exception as e:
            logger.error("Approval reminder failed: %s", e)
            return 0
        for d in pending:
            d.reminder_sent_at = datetime.utcnow()
        db.session.commit()
        return len(pending)


def notify_decision(draft, review):
    """Tell Jordan an owner approved or asked for changes."""
    c = _campaign(draft.campaign_key)
    verdict = "approved" if review.decision == "approved" else "requested changes to"
    unlocked = review.decision == "approved" and review.reviewer == plan.APPROVER
    subject = f"{review.reviewer} {verdict} \"{draft.title}\""
    lines = [f"{review.reviewer} {verdict} the {c['name'] if c else ''} blog."]
    if review.note:
        lines.append(f'Note: "{review.note}"')
    if unlocked:
        lines.append("This is the approving decision: the campaign is unlocked. Bring the landing page, ads and emails in line with the post, then build it in Aspen.")
    elif review.decision == "changes_requested":
        lines.append("Open the draft in the dashboard and click \"Revise with owners' notes\".")
    url = f"{plan.DASHBOARD_URL}/roadmap/blog/{draft.id}"
    html = _wrap("".join(f"<p>{escape(l)}</p>" for l in lines) + f'<p><a href="{url}">Open the draft</a></p>')
    text = "\n\n".join(lines) + f"\n\n{url}"
    try:
        gmail_connector.send(plan.NOTIFY_EMAIL, subject, html, text)
    except Exception as e:
        logger.error("Decision notification failed: %s", e)
