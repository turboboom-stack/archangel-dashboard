# Archangel Marketing Dashboard — Claude Code Context

## Deployment
**This project is deployed on Railway. All changes must be committed and pushed to GitHub to take effect on the live site. Do NOT test against localhost — always push.**

- GitHub repo: https://github.com/turboboom-stack/archangel-dashboard
- Branch: `main` (Railway auto-deploys on push)
- Live site: served via Railway

### Workflow for every change
1. Edit files locally
2. `git add <files>`
3. `git commit -m "..."`
4. `git push origin main`
5. Railway deploys in ~1-2 minutes — done

## Stack
- Python / Flask
- SQLite (`dashboard.db`) — persistent via Railway volume
- Google OAuth token stored as `GOOGLE_TOKEN_JSON` env var on Railway

## Data Sources & Connectors
| Source | Connector | Notes |
|---|---|---|
| GA4 | `connectors/ga4_connector.py` | 14-day window (`14daysAgo to today`) |
| Google Search Console | `connectors/gsc_connector.py` | 28-day window |
| Google My Business | `connectors/gmb_connector.py` | 28-day window |
| Google Ads | `connectors/google_ads_connector.py` | Manual CSV upload |
| Webflow CMS | `connectors/webflow_connector.py` | Blog post counts |
| Clio | `connectors/clio_connector.py` | Bookings + contacts |

## Refresh
- Cache auto-refreshes daily at 06:00
- Manual refresh via **Refresh All** button on dashboard (calls `/api/refresh/all`)
- Per-source refresh: POST `/api/refresh/<source>`

## Google Auth
- OAuth token path: `automations/google-auth-setup/token.json` (local)
- On Railway: set `GOOGLE_TOKEN_JSON` env var to the full contents of `token.json`
- Required scopes: `business.manage`, `analytics.readonly`, `webmasters.readonly`, `spreadsheets`, `gmail.send`
- To re-auth: delete `token.json`, run `python3 automations/google-auth-setup/setup_auth.py`, update Railway env var

## Key Config
- `config.py` — all site IDs, targets, API paths
- Monthly booking targets: `config.MONTHLY_TARGETS`
- GA4 property ID: `390363293`
- Webflow site ID: `63ac55346093abd87bb7c94b`
