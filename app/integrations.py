"""Real provider adapters. Credentials are read from env; no outbound sends to customers."""
import base64
import os
import re
from email.headerregistry import Address
from email.utils import parseaddr
from html import unescape
from urllib.parse import quote

import httpx

GMAIL_SCOPE = 'https://www.googleapis.com/auth/gmail.readonly'
SHEETS_SCOPE = 'https://www.googleapis.com/auth/spreadsheets.readonly'


class IntegrationError(Exception):
    pass


def _google_credentials(scope: str):
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google.oauth2.service_account import Credentials as ServiceCredentials
    except ImportError as exc:
        raise IntegrationError('Install requirements.txt to enable Google integration') from exc
    if scope == GMAIL_SCOPE:
        values = {k: os.getenv(k, '') for k in ('GOOGLE_CLIENT_ID', 'GOOGLE_CLIENT_SECRET', 'GOOGLE_REFRESH_TOKEN')}
        if not all(values.values()):
            raise IntegrationError('Gmail OAuth credentials are not configured')
        credentials = Credentials(token=None, refresh_token=values['GOOGLE_REFRESH_TOKEN'],
                                  token_uri='https://oauth2.googleapis.com/token',
                                  client_id=values['GOOGLE_CLIENT_ID'],
                                  client_secret=values['GOOGLE_CLIENT_SECRET'], scopes=[scope])
    else:
        path = os.getenv('GOOGLE_SERVICE_ACCOUNT_FILE', '')
        if not path:
            raise IntegrationError('GOOGLE_SERVICE_ACCOUNT_FILE is not configured')
        credentials = ServiceCredentials.from_service_account_file(path, scopes=[scope])
    try:
        credentials.refresh(Request())
    except Exception as exc:
        raise IntegrationError('Google authentication failed; check credentials') from exc
    return credentials.token


def _decode(data: str) -> str:
    try:
        return base64.urlsafe_b64decode(data + '=' * (-len(data) % 4)).decode('utf-8', errors='replace')
    except (ValueError, TypeError):
        return ''


def gmail_message_fields(msg: dict) -> dict | None:
    """Parse Gmail full-format MIME message; prefer plain text, safe HTML fallback."""
    headers = {x.get('name', '').lower(): x.get('value', '') for x in msg.get('payload', {}).get('headers', [])}
    sender = parseaddr(headers.get('from', ''))[1].lower()
    if not sender or '@' not in sender:
        return None
    parts = []

    def collect(part):
        mime = part.get('mimeType', '')
        data = part.get('body', {}).get('data', '')
        if data and mime in ('text/plain', 'text/html') and not part.get('filename'):
            parts.append((mime, _decode(data)))
        for p in part.get('parts', []):
            collect(p)
    collect(msg.get('payload', {}))
    plain = [x for typ, x in parts if typ == 'text/plain']
    html = [x for typ, x in parts if typ == 'text/html']
    body = '\n'.join(plain).strip() if plain else ''
    if not body and html:
        body = re.sub(r'<[^>]+>', ' ', ' '.join(html))
        body = unescape(re.sub(r'\s+', ' ', body)).strip()
    if not body:
        body = msg.get('snippet', '')
    return {'sender': sender[:255], 'subject': headers.get('subject', '(no subject)')[:250],
            'body': body[:10000] or '(empty message)', 'source': 'email',
            'external_id': f"gmail:{msg['id']}"}


async def gmail_fetch(query: str | None = None, limit: int = 20) -> list[dict]:
    token = _google_credentials(GMAIL_SCOPE)
    query = query if query is not None else os.getenv('GMAIL_QUERY', 'in:inbox newer_than:7d')
    async with httpx.AsyncClient(timeout=20, follow_redirects=False,
                                 headers={'Authorization': f'Bearer {token}'}) as client:
        r = await client.get('https://gmail.googleapis.com/gmail/v1/users/me/messages',
                             params={'q': query, 'maxResults': max(1, min(limit, 100))})
        r.raise_for_status()
        results = []
        for entry in r.json().get('messages', []):
            response = await client.get(f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{quote(entry['id'], safe='')}",
                                        params={'format': 'full'})
            response.raise_for_status()
            parsed = gmail_message_fields(response.json())
            if parsed:
                results.append(parsed)
        return results


async def sheets_fetch() -> list[dict]:
    sheet_id, sheet_range = os.getenv('GOOGLE_SHEET_ID', ''), os.getenv('GOOGLE_SHEET_RANGE', 'Orders!A:D')
    if not sheet_id or not re.fullmatch(r'[\w-]+', sheet_id):
        raise IntegrationError('GOOGLE_SHEET_ID missing or invalid')
    token = _google_credentials(SHEETS_SCOPE)
    url = f'https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values/{quote(sheet_range, safe="")}'
    async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
        response = await client.get(url, headers={'Authorization': f'Bearer {token}'})
        response.raise_for_status()
    rows = response.json().get('values', [])
    if not rows:
        return []
    headers = [str(v).strip().lower().replace(' ', '_') for v in rows[0]]
    required = {'id', 'customer_email', 'status', 'eta'}
    if not required.issubset(set(headers)):
        raise IntegrationError('Sheets header must include id, customer_email, status, eta')
    return [dict(zip(headers, row)) for row in rows[1:] if len(row) >= 4]


async def slack_send(ticket_id: int, priority: str, category: str, subject: str) -> float | None:
    """Return retry delay on 429, otherwise None on success. Never send message contents."""
    webhook = os.getenv('SLACK_WEBHOOK_URL', '')
    if not webhook.startswith('https://hooks.slack.com/services/'):
        raise IntegrationError('SLACK_WEBHOOK_URL is not configured or invalid')
    # Slack text is escaped to prevent unintended mentions and link expansions.
    clean_subject = subject.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')[:120]
    content = f'ResolveAI escalation: ticket #{ticket_id} | {priority} | {category}\n{clean_subject}\nPlease review in the admin dashboard.'
    async with httpx.AsyncClient(timeout=12, follow_redirects=False) as client:
        response = await client.post(webhook, json={'text': content, 'link_names': False})
    if response.status_code == 429:
        try:
            return max(1.0, min(float(response.headers.get('Retry-After', '60')), 3600.0))
        except ValueError:
            return 60.0
    response.raise_for_status()
    if response.text.strip() != 'ok':
        raise IntegrationError('Slack rejected the webhook payload')
    return None
