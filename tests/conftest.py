import os
import tempfile
from pathlib import Path
os.environ["DATABASE_URL"] = f"sqlite:///{(Path(tempfile.mkdtemp()) / 'phase23.db').as_posix()}"
os.environ["DEMO_MODE"] = "true"
os.environ.pop("ADMIN_TOKEN", None)
os.environ.pop("LLM_API_KEY", None)
import pytest
from fastapi.testclient import TestClient
from app.main import Base, engine, app

@pytest.fixture
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with TestClient(app) as c:
        yield c
