import pytest
from fastapi.testclient import TestClient
from app import main


def make_staff(role='agent', email='agent@example.com'):
    with main.SessionLocal() as db:
        db.add(main.StaffUser(email=email, role=role, password_hash=main.hash_password('VeryStrongPass123!')))
        db.commit()


def test_authentication_required_outside_demo(monkeypatch, client):
    monkeypatch.setattr(main, 'DEMO_MODE', False)
    monkeypatch.setattr(main, 'ADMIN_TOKEN', '')
    assert client.get('/api/tickets').status_code == 401
    assert client.post('/api/integrations/gmail/sync').status_code == 401


def test_agent_rbac_login_logout(monkeypatch, client):
    monkeypatch.setattr(main, 'DEMO_MODE', False)
    monkeypatch.setattr(main, 'ADMIN_TOKEN', '')
    make_staff()
    bad = client.post('/api/auth/login', json={'email': 'agent@example.com', 'password': 'wrong'})
    assert bad.status_code == 401
    r = client.post('/api/auth/login', json={'email': 'agent@example.com', 'password': 'VeryStrongPass123!'})
    assert r.status_code == 200
    token = r.json()['access_token']
    assert token not in str(main.StaffUser.__table__.columns)
    headers = {'Authorization': 'Bearer ' + token}
    assert client.get('/api/tickets', headers=headers).status_code == 200
    assert client.post('/api/integrations/gmail/sync', headers=headers).status_code == 403
    assert client.post('/api/admin/staff', json={'email':'other@example.com', 'password':'StrongPassword123!'}, headers=headers).status_code == 403
    assert client.post('/api/auth/logout', headers=headers).status_code == 200
    assert client.get('/api/tickets', headers=headers).status_code == 401


def test_admin_create_agent_and_duplicate(monkeypatch, client):
    monkeypatch.setattr(main, 'DEMO_MODE', False)
    monkeypatch.setattr(main, 'ADMIN_TOKEN', '')
    make_staff('admin', 'admin@example.com')
    login = client.post('/api/auth/login', json={'email':'admin@example.com','password':'VeryStrongPass123!'})
    assert login.status_code == 200
    headers={'Authorization':'Bearer '+login.json()['access_token']}
    new={'email':'next@example.com','password':'NewStrongPassword123!','role':'agent'}
    assert client.post('/api/admin/staff',json=new,headers=headers).status_code == 201
    assert client.post('/api/admin/staff',json=new,headers=headers).status_code == 409
    assert any(x['email']=='next@example.com' for x in client.get('/api/admin/staff',headers=headers).json())


def test_login_rate_limited(monkeypatch, client):
    monkeypatch.setattr(main, 'DEMO_MODE', False)
    main.LOGIN_ATTEMPTS.clear()
    for _ in range(10):
        assert client.post('/api/auth/login',json={'email':'absent@example.com','password':'incorrect'}).status_code == 401
    assert client.post('/api/auth/login',json={'email':'absent@example.com','password':'incorrect'}).status_code == 429
    main.LOGIN_ATTEMPTS.clear()


def test_security_headers_and_assets(client):
    response=client.get('/')
    assert response.status_code == 200
    assert 'gradient' not in response.text.lower()
    assert "frame-ancestors 'none'" in response.headers['content-security-policy']
    assert response.headers['x-frame-options'] == 'DENY'
    assert client.get('/static/app.css').status_code == 200
    assert client.get('/static/app.js').status_code == 200


def test_metrics_endpoint(client):
    client.post('/api/tickets',json={'sender':'bob@example.com','subject':'Refund please','body':'Can I get a refund?'})
    data=client.get('/api/metrics').json()
    assert data['total']==1 and data['pending']==1
    assert data['by_category']['refund']==1
