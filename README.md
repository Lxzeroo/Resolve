# ResolveAI · Support ticket triage with human review

An executable portfolio MVP for customer-support classification, verified order lookup, draft generation, manual approvals, and audit events. Includes a responsive warm-white and deep-teal operations dashboard.

> **Status: Phase 4 + 5 implementation on top of Phase 2 + 3.** Gmail read-only ingestion, Google Sheets order import, Slack escalation worker, structured optional LLM triage and offline evaluation are now implemented. No outbound customer emails. Not production-hardened; avoid real customer data until security review. See [DEPLOYMENT.md](DEPLOYMENT.md) and [PHASE_2_3.md](PHASE_2_3.md) for setup.

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

## Authentication and role-based access

When `DEMO_MODE=true` and `ADMIN_TOKEN` is empty, authentication is **disabled**. Do not expose this configuration on any public network. For protected API access, set `DEMO_MODE=false` and `BOOTSTRAP_ADMIN_EMAIL` / `BOOTSTRAP_ADMIN_PASSWORD`. Sign in through the profile button. The scrypt-hashed staff credentials create short-lived hashed bearer sessions, with distinct admin and agent permissions. A high-entropy `ADMIN_TOKEN` is also supported as a legacy integration token. See `DEPLOYMENT.md`.

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

## Future hardening before real customer deployment

1. Replace in-process login throttling with a distributed rate limiter and add account recovery.
2. Add migrations, tenant isolation, field-level privacy and retention tooling.
3. Add Gmail Pub/Sub watch renewal, message threading, and stronger input validation.
4. Add worker leasing and dead-letter retry controls for multiple workers.
5. Expand labeled evaluation data, model calibration and output-safety benchmarks.
6. Configure a public TLS staging host and external monitoring after hosting credentials are available.

## Tests

`pytest -q`

All project data in the demonstration should be synthetic. MIT license can be added after choosing a licensing policy.

## Phase 2 + 3 additions

- Optional structured LLM classification and safe rules fallback; all replies need human approval
- Read-only Gmail sync and Google Sheets service-account order import
- Durable single-worker Slack escalation queue with retries and visible job status
- Synthetic labeled dataset and `python -m app.evaluate`

See [Phase 2 + 3 setup](PHASE_2_3.md).

## Phase 4 + 5 implementation

- Redesigned warm-white / deep-teal responsive dashboard (no gradients, purple or emoji), consistent rounded controls.
- Staff sign-in / logout, secure password hashing, session expiration, RBAC and throttling tests.
- Analytics and escalation queue views, security headers, Python CI with secret guards.
- Containerized PostgreSQL, API and separate worker stack in `docker-compose.yml`.
- See [Deployment and security guide](DEPLOYMENT.md) for production limitations and setup.
