import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.store import Store, get_store


@pytest.fixture
def client():
    fresh = Store()  # cada teste comeca com dados limpos
    app.dependency_overrides[get_store] = lambda: fresh
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def supplier(client):
    return client.post("/suppliers", json={"name": "Acme", "country": "BR"}).json()
