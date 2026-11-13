# VPN Control — demo Telegram bot + website

A starter project for a VPN subscription service. The repository currently contains a **demo only**:

- Telegram bot with subscription, devices, locations and help screens.
- Responsive static dashboard in `docs/` for GitHub Pages.
- FastAPI API that shares a SQLite database with the bot and verifies Telegram Mini App initData.
- Manual GitHub Actions workflow that can run the Telegram bot for 30 minutes.

## Important: demo limitations

- No real payments are accepted. The “activate demo” action writes a test subscription only.
- No real VPN profiles, UUIDs, server credentials or 3X-UI connections are created.
- The five locations are preview cards, not live VPN servers.
- Device entries are labels stored in the database. They do not prove a device is online. Real connection status requires protocol/server telemetry.
- GitHub Actions runners are temporary. SQLite on the Actions runner is temporary too.
- GitHub Pages hosts only the static website. It does not run FastAPI or keep a database alive.

## Security first

A Telegram bot token previously pasted into a chat or source code must be considered compromised. Revoke it using @BotFather and create a new token. **Never put the token into a source file, website config, issue, or commit.** Store it as a repository secret named `BOT_TOKEN`.

## Test the static website

1. In GitHub open **Settings → Pages**.
2. Set **Build and deployment → Source** to **GitHub Actions**.
3. The `Deploy demo website to GitHub Pages` workflow deploys `docs/`.
4. The expected Pages address is `https://kirovo389-creator.github.io/VPN-bot/` once Pages is enabled and deployment succeeds.
5. The website has local demo data when no API is configured.

## Test the Telegram bot for 30 minutes

1. Revoke the exposed token in @BotFather and create a new token.
2. In the repository open **Settings → Secrets and variables → Actions → New repository secret**.
3. Name it `BOT_TOKEN`; paste the new token as its value.
4. Open **Actions → Run Telegram demo bot for 30 minutes → Run workflow**.
5. The runner starts polling for 30 minutes and then stops. It is not permanent hosting.

The bot can open the website as a Telegram Mini App using `WEB_APP_URL`. Set `BOT_USERNAME` only if you want the website's “Open Telegram” link to point to the bot.

## Run locally

Python 3.12 is recommended.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export BOT_TOKEN="YOUR_NEW_BOT_TOKEN"
export WEB_APP_URL="https://kirovo389-creator.github.io/VPN-bot/"
python bot.py
```

Run the API in another terminal after setting the **same** `BOT_TOKEN` and a shared `DB_PATH`:

```bash
uvicorn api:app --host 0.0.0.0 --port 8000
```

To connect the static website to the API, set `apiBase` in `docs/config.js` to the public HTTPS API URL and set `ALLOWED_ORIGINS` on the API host to the GitHub Pages origin. Open the site through the bot's WebApp button so Telegram initData is available.

## Before production

Use PostgreSQL (not a temporary runner SQLite file), HTTPS, backups, rate limits, audit logs, monitoring and a persistent host for both the API and bot. Implement and verify payment webhooks before activating paid plans. Connect the 3X-UI/Xray APIs using server-side secrets only; never expose panel credentials or VPN client keys in frontend JavaScript. Keep each device's client ID server-side and report online status only when supported by real server telemetry.
