# ResolveAI · Support ticket triage with human review

An executable portfolio MVP for customer-support classification, verified order lookup, draft generation, manual approvals, and audit events. Dark-mode dashboard included.

> **Status: initial prototype.** No real inbox ingestion, email sending, webhook delivery, Slack alerts, calibrated LLM evaluation, or production-grade authentication yet. Never connect this prototype to real customer data without security review.

## Local quickstart (Python 3.12+)

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env  # Windows PowerShell: Copy-Item .env.example .env
# Use DEMO_MODE=true for LOCAL DEVELOPMENT ONLY
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000. API docs: http://127.0.0.1:8000/docs.

For a local sample order:

```bash
curl -X POST http://127.0.0.1:8000/api/demo/seed
```

Then select **Use sample** in the UI. Seed only works with `DEMO_MODE=true`.

### Docker

Copy `.env.example` to `.env`, then run `docker compose up --build`. Open http://127.0.0.1:8000. Docker Compose binds to localhost.

## Authentication warning

When `DEMO_MODE=true` and `ADMIN_TOKEN` is empty, authentication is **disabled**. Do not expose this configuration on any public network. For protected API access, set `DEMO_MODE=false` and a high-entropy `ADMIN_TOKEN` and submit it in the dashboard access-token prompt. This is a prototype-level shared token, not production user authentication.

## Optional LLM

Configure `LLM_API_URL`, `LLM_API_KEY`, and `LLM_MODEL` to call a trusted OpenAI-compatible HTTPS chat completions endpoint. Failures fall back to deterministic rules. Output must still be human-reviewed. The external model receives ticket content, so **use synthetic data** until consent, retention and privacy controls are implemented. The heuristic score is not a calibrated LLM probability.

## Core API

- `GET /health` health and mode
- `GET /api/tickets` list tickets
- `POST /api/tickets` create and triage, optional `external_id` to deduplicate
- `POST /api/tickets/{id}/review` approve or reject draft (never sends)
- `GET /api/tickets/{id}/audit` ticket event history
- `GET /api/orders`, `POST /api/orders` manage demo order facts
- `POST /api/demo/seed` add sample orders (demo mode only)

Use `X-Admin-Token` for API requests when demo mode is disabled.

## Security decisions

- All ticket replies start in `pending_review` and **no route sends an email**.
- Customer email must match order's customer email before private shipping facts are included.
- LLM messages treat ticket content as untrusted.
- API token required outside explicitly enabled demo mode.
- Only `https://` LLM endpoints allowed; use a trusted URL.
- No API keys committed; `.env` ignored.
- Event history records manual review (not yet cryptographically tamper-evident).

## Remaining milestones

1. Gmail OAuth, read-only ingestion, watch renewal, deduplication and message threading.
2. Replace shared admin token with real user authentication, authorization, tenant isolation, rate limits and migrations.
3. PostgreSQL and background queue with idempotent retries / dead-letter handling.
4. Slack escalation, Google Sheets order sync, signed webhooks.
5. Labeled dataset, precision/recall, calibration, and structured-output evaluation.
6. CI/CD staging deployment, Playwright E2E, security tests and observability.

## Tests

`pytest -q`

All project data in the demonstration should be synthetic. MIT license can be added after choosing a licensing policy.
