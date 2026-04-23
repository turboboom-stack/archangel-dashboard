#!/usr/bin/env python3
"""
Clio OAuth Setup
================
Run once to authorize dashboard access to Clio Grow + Manage.
Saves token to clio_token.json for use by clio_connector.py.

Usage:
    cd /Users/jordan/Claude/Archangel/marketing-dashboard
    source venv/bin/activate
    python3 clio_auth_setup.py
"""

import http.server
import json
import os
import threading
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

SCRIPT_DIR   = Path(__file__).parent
TOKEN_FILE   = SCRIPT_DIR / "clio_token.json"
REDIRECT_URI = "http://127.0.0.1:8765/callback"
AUTH_URL     = "https://app.clio.com/oauth/authorize"
TOKEN_URL    = "https://app.clio.com/oauth/token"

# Clio grants permissions at the app level in the developer portal.
# Pass no scope param to get the full access the app was configured for.
SCOPE = None


def load_credentials():
    env_path = SCRIPT_DIR / ".env"
    config = {}
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                config[k.strip()] = v.strip()
    client_id     = config.get("CLIO_CLIENT_ID", "").strip()
    client_secret = config.get("CLIO_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        print("\nClio credentials not found in .env")
        print("Add these lines to marketing-dashboard/.env:")
        print("  CLIO_CLIENT_ID=your_client_id")
        print("  CLIO_CLIENT_SECRET=your_client_secret\n")
        client_id     = input("Paste Client ID:     ").strip()
        client_secret = input("Paste Client Secret: ").strip()
        # Append to .env
        with open(env_path, "a") as f:
            f.write(f"\nCLIO_CLIENT_ID={client_id}\n")
            f.write(f"CLIO_CLIENT_SECRET={client_secret}\n")
        print("Saved to .env\n")
    return client_id, client_secret


def get_auth_code(client_id):
    """Open browser, start local server, wait for redirect."""
    auth_code = {}

    auth_params = {
        "response_type": "code",
        "client_id":     client_id,
        "redirect_uri":  REDIRECT_URI,
    }
    if SCOPE:
        auth_params["scope"] = SCOPE
    params = urllib.parse.urlencode(auth_params)
    auth_link = f"{AUTH_URL}?{params}"

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            qs = urllib.parse.parse_qs(parsed.query)
            if "code" in qs:
                auth_code["value"] = qs["code"][0]
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b"<h2>Authorized! You can close this tab.</h2>")
            else:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"<h2>Error: no code received.</h2>")

        def log_message(self, *args):
            pass  # suppress server logs

    server = http.server.HTTPServer(("localhost", 8765), Handler)
    thread = threading.Thread(target=server.handle_request)
    thread.start()

    print(f"Opening browser for Clio authorization...")
    webbrowser.open(auth_link)
    print(f"Waiting for redirect to {REDIRECT_URI} ...")
    thread.join(timeout=120)

    if not auth_code.get("value"):
        raise RuntimeError("No authorization code received after 120 seconds.")

    return auth_code["value"]


def exchange_code(client_id, client_secret, code):
    """Exchange auth code for access + refresh tokens."""
    payload = urllib.parse.urlencode({
        "grant_type":    "authorization_code",
        "code":          code,
        "redirect_uri":  REDIRECT_URI,
        "client_id":     client_id,
        "client_secret": client_secret,
    }).encode()

    req = urllib.request.Request(
        TOKEN_URL,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def main():
    print("=" * 50)
    print("Clio OAuth Setup — Archangel Dashboard")
    print("=" * 50)

    client_id, client_secret = load_credentials()
    code = get_auth_code(client_id)
    print(f"Auth code received. Exchanging for tokens...")

    token_data = exchange_code(client_id, client_secret, code)

    # Store client credentials alongside token for refresh
    token_data["client_id"]     = client_id
    token_data["client_secret"] = client_secret

    TOKEN_FILE.write_text(json.dumps(token_data, indent=2))
    print(f"\nToken saved to {TOKEN_FILE}")

    # Verify by hitting /api/v4/matters (who_am_i returns 403 on this plan)
    access_token = token_data.get("access_token")
    req = urllib.request.Request(
        "https://app.clio.com/api/v4/matters.json?limit=1",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())
    record_count = result.get("meta", {}).get("records", "?")
    print(f"Token verified — {record_count} matters accessible in Clio.")
    print("\nSetup complete. Run the dashboard and Clio data will populate on next refresh.")


if __name__ == "__main__":
    main()
