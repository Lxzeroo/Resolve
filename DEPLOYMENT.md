# ResolveAI v0.4 — Setup and deployment

## What is implemented

- Apple-inspired responsive light dashboard, deep-teal accent, soft green backgrounds, warm amber and coral statuses, rounded buttons; no gradients, purple or emoji icons.
- Ticket triage, optional structured LLM classification, verified order data, human-only draft approval and audit history.
- Read-only Gmail OAuth imports, Google Sheets order sync, Slack escalation outbox and a single dedicated retry worker.
- Staff authentication with scrypt password hashes, hashed short-lived bearer sessions, logout and admin / agent role separation. Legacy admin token remains available.
- Minimal security response headers, login throttling, locked-down demo bypass, and CI tests.
- PostgreSQL production-style Docker Compose configuration with API, database and worker.

## Start locally (Windows PowerShell)

```powershell
cd "C:\Users\AFFAN\OneDrive\Desktop\Resolve"
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
Copy-Item .env.example .env
# Keep DEMO_MODE=true for localhost tests only
python -m pytest -q
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000. To add example orders, use `Invoke-RestMethod -Method POST http://127.0.0.1:8000/api/demo/seed` in another terminal. Use the **New ticket** button on the Inbox page.

## Local secure mode

Change `.env`:

```dotenv
DEMO_MODE=false
BOOTSTRAP_ADMIN_EMAIL=admin@yourdomain.example
BOOTSTRAP_ADMIN_PASSWORD=replace-with-a-strong-unique-16-plus-character-password
```

Restart the API. Click the profile card in the sidebar and sign in. The admin account is created **once** on first startup; updating the bootstrap password later does not reset an existing account. Remove bootstrap secrets after the account has been created. For development, API docs may be enabled with `ENABLE_API_DOCS=true`. To create staff, authenticated admins can POST to `/api/admin/staff` with `{ "email": "...", "password": "at-least-12-characters", "role": "agent" }`.

The legacy `ADMIN_TOKEN` can be used to authenticate clients with the `X-Admin-Token` header; it has full administrative privileges. Use staff sessions instead for everyday access.

## Container deployment

Set at least these values in `.env` before running Compose:

```dotenv
DEMO_MODE=false
POSTGRES_PASSWORD=unique-strong-random-database-password
BOOTSTRAP_ADMIN_EMAIL=admin@yourdomain.example
BOOTSTRAP_ADMIN_PASSWORD=unique-strong-password-at-least-12-characters
```

Run `docker compose up --build -d` and visit http://127.0.0.1:8000. Docker binds the API to localhost only. The database is not externally published. `docker compose logs -f api worker` shows startup and worker processing. The first run initializes a **new** PostgreSQL database; it does not import your existing SQLite data.

For public deployment, use a TLS reverse proxy, configure DNS and HTTPS, and use a managed PostgreSQL host or a secured database volume with backups. The API and `python -m app.worker` must run as separate long-lived processes. A Vercel-only frontend deployment does **not** run this worker. Configure environment secrets in your deployment platform, not in GitHub commits. Render, Fly.io or a VPS are candidate platforms; verify current pricing and worker support before selecting one.

## Gmail / Sheets / Slack integration

Follow `PHASE_2_3.md` for Google OAuth and Slack webhook configuration. Run one worker (`python -m app.worker`) for Slack escalations; it retries temporary failures. **Do not run two worker replicas** because the current outbox has no distributed row lease. For container deployment, provide the Google service-account JSON via a read-only secret-file mount and set `GOOGLE_SERVICE_ACCOUNT_FILE` to the in-container path. Never commit OAuth refresh tokens, client secrets or Slack webhook URLs.

## Security and deployment limitations

- **Not production certified.** This is a demonstrable engineering portfolio project. Before onboarding real customers, add tenant isolation, privacy policy/retention, consent, validated outbound email, account recovery, secret rotation, and an external security review.
- The current `create_all()` initialization is suitable for new databases; it does not migrate existing schema revisions. Introduce Alembic before changing existing tables in production.
- Login throttling is in-process and resets on restart; production should use a shared distributed rate limiter.
- Slack worker supports only a single process and can duplicate a notification if Slack accepts it but the worker crashes before database commit. Exactly-once external delivery is not guaranteed.
- Gmail is read-only, not a push webhook pipeline. It requires manual sync; Pub/Sub and watch renewal are future work.
- Admin token bypass is retained for local/integration compatibility. Protect or disable it if not needed.
- Generated replies require human review; the system does **not** send customer email.
- There is no automated data deletion or field-level encryption for customer tickets.

## Tests and code quality

```powershell
python -m pytest -q
python -m compileall -q app scripts
```

GitHub Actions runs both commands on push and pull request, as well as a tracked-secret-file guard. To deploy, create a separate production or staging service that pulls from the GitHub repository after tests pass. This release does not auto-deploy because no hosting credentials were supplied.
