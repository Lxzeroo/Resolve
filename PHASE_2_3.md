# ResolveAI Phase 2 + 3 — integration setup

Implemented: structured LLM classification (strict Pydantic schema, rule-based safety override), grounded drafts using verified order data, local evaluation CSV, Gmail read-only ingestion, Google Sheets order sync, Slack high-risk escalation outbox with retries, dashboard sync buttons. **No customer email sends.**

## 1. Install and run (PowerShell)

```powershell
cd C:\Users\AFFAN\OneDrive\Desktop\Resolve
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

Copy the new keys from `.env.example` into your existing `.env` rather than overwriting credentials.

## 2. Gmail (read-only)

1. In Google Cloud Console, create/select a project, enable Gmail API, configure OAuth consent, and register an OAuth **Desktop app** client.
2. Set `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in `.env`.
3. Run `python scripts/gmail_oauth.py` locally. Approve `gmail.readonly` for a **dedicated test/support inbox**. Copy the printed `GOOGLE_REFRESH_TOKEN` into `.env`; **do not commit or share it**.
4. Limit `GMAIL_QUERY` to a specific test label, e.g. `label:resolveai-test newer_than:7d` to avoid importing personal email.
5. Click **Sync Gmail** in the dashboard or POST `/api/integrations/gmail/sync` with the admin token.

Each Gmail message is assigned a deterministic `gmail:<message-id>` ID; re-sync does not create duplicates. Gmail attachments are ignored. Only the first 20 matching messages are read per sync; production pagination, forwarding policies and data retention are future work.

**Important:** Gmail read-only access is a restricted OAuth scope; publishing a public multi-user integration may require Google verification and security review. For now, use test users and a test account.

## 3. Google Sheets (service account)

1. Enable Google Sheets API and create a service account in Google Cloud.
2. Download the JSON key to a location **outside** your repository, set its full path as `GOOGLE_SERVICE_ACCOUNT_FILE`.
3. Share the target spreadsheet with the service account email as **Viewer**.
4. Set `GOOGLE_SHEET_ID` from its URL and `GOOGLE_SHEET_RANGE=Orders!A:D`.
5. Provide columns on row 1: `id`, `customer_email`, `status`, `eta`; rows: `ORD-1042`, `customer@example.com`, `shipped`, `2026-11-27`.
6. Click **Sync Google Sheets**. Each row is validated and upserted into local order data. Invalid rows are counted and skipped.

## 4. Slack escalations

1. Create a Slack app and enable Incoming Webhooks for a test channel.
2. Put the webhook in `.env` as `SLACK_WEBHOOK_URL`.
3. Run a **second terminal** with `python -m app.worker`.
4. Submit a refund, complaint or urgent ticket. Inspect `/api/jobs` for queued/done/failed and ticket audit history.

The worker retries up to 5 times with backoff and honours Slack 429 `Retry-After`. It is a **single-worker prototype** and should not be run in multiple instances concurrently. Queued items are stored in the database and survive process restart. A final failed item stays visible in `/api/jobs` for manual intervention. Slack alerts include only ticket number, category, priority and short subject; do not include private message body.

## 5. AI setup and evaluation

The existing `LLM_API_URL`, `LLM_API_KEY` and `LLM_MODEL` enable optional structured triage + drafting. `LLM_API_URL` must use HTTPS and point to a **trusted OpenAI-compatible** API endpoint. Without these keys, categorization and drafts fall back to the deterministic rules engine. Generated drafts always require human approval. No calibrated probability is claimed; confidence values are raw scores.

```powershell
python -m app.evaluate
python -m pytest -q
```

The checked-in `tests/data/triage_labels.csv` is a tiny **synthetic smoke-test** set, not an independent benchmark. Build a larger, separately labeled set before reporting performance on your resume.

## Production warnings

This release is intended for local development. `DEMO_MODE=true` disables API authentication. Before deployment, implement real user auth/roles, audit access, migrations, rate limiting, secret management, safer tenant isolation, bounded retention, and stronger prompt-injection/PII controls. Do not make it public while `DEMO_MODE=true` or use it with real customer PII. The Slack worker is single-instance; use proper job claiming/locking before scaling it.
