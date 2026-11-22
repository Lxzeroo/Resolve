import base64
import pytest
from unittest.mock import AsyncMock
from app.integrations import gmail_message_fields
from app.triage import Classification, enforce_safety
from app.evaluate import evaluate
from app import main


def test_gmail_mime_text_and_unique_id():
    encoded = base64.urlsafe_b64encode(b'Where is ORD-1042?').decode()
    message = {'id': 'abc123', 'payload': {'headers': [
        {'name': 'From', 'value': 'Maya <maya@example.com>'},
        {'name': 'Subject', 'value': 'Tracking'}], 'mimeType': 'text/plain', 'body': {'data': encoded}}}
    parsed = gmail_message_fields(message)
    assert parsed['sender'] == 'maya@example.com'
    assert parsed['external_id'] == 'gmail:abc123'
    assert 'ORD-1042' in parsed['body']


def test_llm_cannot_invent_order_or_override_urgent():
    prediction = Classification(category='general', priority='normal', confidence=99, order_id='ORD-9999')
    result = enforce_safety(prediction, 'Need help', 'My lawyer will contact you about ORD-1042', 'ORD-1042')
    assert (result.category, result.priority, result.order_id) == ('complaint', 'urgent', 'ORD-1042')
    assert result.confidence <= 35


def test_evaluation_fixture():
    result = evaluate('tests/data/triage_labels.csv')
    assert result['examples'] == 10
    assert 0 <= result['accuracy'] <= 1
    assert 'refund' in result['by_category']


def test_integrations_require_admin(monkeypatch):
    from fastapi.testclient import TestClient
    monkeypatch.setattr(main, 'DEMO_MODE', False)
    monkeypatch.setattr(main, 'ADMIN_TOKEN', 'test-secret')
    with TestClient(main.app) as client:
        assert client.post('/api/integrations/gmail/sync').status_code == 401
        assert client.post('/api/integrations/sheets/sync').status_code == 401


def test_gmail_sync_is_idempotent(monkeypatch, client):
    messages = [{'sender': 'maya@example.com', 'subject': 'Where is my order?',
                 'body': 'Please track ORD-1042', 'source': 'email', 'external_id': 'gmail:xyz'}]
    monkeypatch.setattr(main, 'gmail_fetch', AsyncMock(return_value=messages))
    client.post('/api/demo/seed')
    one = client.post('/api/integrations/gmail/sync').json()
    two = client.post('/api/integrations/gmail/sync').json()
    assert one['imported'] == 1
    assert two['duplicates'] == 1
    assert len(client.get('/api/tickets').json()) == 1


def test_sheets_sync(monkeypatch, client):
    monkeypatch.setattr(main, 'sheets_fetch', AsyncMock(return_value=[
        {'id': 'ORD-5022', 'customer_email': 'test@example.com', 'status': 'shipped', 'eta': 'Friday'},
        {'id': 'bad', 'customer_email': 'a@b.com', 'status': 'shipped', 'eta': 'Friday'}]))
    result = client.post('/api/integrations/sheets/sync').json()
    assert result == {'imported': 1, 'invalid': 1}
    assert any(row['id'] == 'ORD-5022' for row in client.get('/api/orders').json())


def test_slack_queue_for_high_priority(client):
    r = client.post('/api/tickets', json={'sender':'customer@example.com','subject':'Refund',
                                          'body':'I want a refund for my item'}).json()
    jobs = client.get('/api/jobs').json()
    assert len(jobs) == 1 and jobs[0]['ticket_id'] == r['id']
    assert jobs[0]['status'] == 'pending'
