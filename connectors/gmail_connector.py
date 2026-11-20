"""Send email through Gmail with the dashboard's shared Google OAuth token (gmail.send scope).

Mail goes out from the account that authorized token.json (Turboboomproduction@gmail.com).
"""

import base64
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import config


def send(to, subject, html, text):
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    creds = Credentials.from_authorized_user_file(config.GOOGLE_TOKEN_PATH)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())

    msg = MIMEMultipart("alternative")
    msg["To"] = ", ".join(to) if isinstance(to, (list, tuple)) else to
    msg["Subject"] = subject
    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    build("gmail", "v1", credentials=creds, cache_discovery=False).users().messages().send(
        userId="me", body={"raw": raw}).execute()
