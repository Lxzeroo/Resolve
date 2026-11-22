import os
import tempfile
from pathlib import Path

# Keep tests isolated from user database.
TEST_DB = Path(tempfile.mkdtemp()) / "test.db"
os.environ['DATABASE_URL'] = f'sqlite:///{TEST_DB.as_posix()}'
os.environ['DEMO_MODE'] = 'true'
os.environ.pop('ADMIN_TOKEN', None)
os.environ.pop('LLM_API_KEY', None)

import pytest
from fastapi.testclient import TestClient
from app.main import Base, app, engine


@pytest.fixture
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with TestClient(app) as c:
        yield c


def test_health(client):
    assert client.get('/health').json()['status'] == 'ok'


def test_ticket_workflow(client):
    client.post('/api/demo/seed')
    r = client.post('/api/tickets', json={'sender':'maya@example.com','subject':'Tracking','body':'Where is ORD-1042?'})
    assert r.status_code == 201
    ticket = r.json()
    assert ticket['category'] == 'order_status'
    assert 'shipped' in ticket['draft']
    assert ticket['status'] == 'pending_review'
    r = client.post(f"/api/tickets/{ticket['id']}/review", json={'action':'approve', 'draft':'Approved reply'})
    assert r.status_code == 200 and r.json()['status'] == 'approved'
    assert r.json()['draft'] == 'Approved reply'
    assert client.post(f"/api/tickets/{ticket['id']}/review", json={'action':'approve'}).status_code == 409
    events = client.get(f"/api/tickets/{ticket['id']}/audit").json()
    assert [e['event'] for e in events] == ['ticket_created', 'approved']


def test_wrong_customer_cannot_see_order(client):
    client.post('/api/demo/seed')
    ticket = client.post('/api/tickets', json={'sender':'stranger@example.com','subject':'Order','body':'ORD-1042'}).json()
    assert 'shipped' not in ticket['draft']
    assert 'could not verify' in ticket['draft']


def test_duplicate_external_id(client):
    payload={'sender':'test@example.com','subject':'Help','body':'Something failed','external_id':'gmail-message-001','source':'email'}
    first=client.post('/api/tickets',json=payload).json()
    second=client.post('/api/tickets',json=payload).json()
    assert first['id']==second['id']
    assert len(client.get('/api/tickets').json())==1


def test_urgent_escalation(client):
    ticket=client.post('/api/tickets',json={'sender':'test@example.com','subject':'Complaint','body':'I have a lawyer and may file a lawsuit.'}).json()
    assert ticket['priority']=='urgent' and ticket['confidence']<50


def test_validation(client):
    assert client.post('/api/tickets',json={'sender':'a','subject':'','body':''}).status_code==422
    assert client.get('/api/tickets/999/audit').status_code==404
