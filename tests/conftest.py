import pytest
from fastapi.testclient import TestClient

from app.auth import User, get_current_user
from app.main import app
from app.store import Store, get_store

ADMIN = User(name="test-admin", scopes=frozenset({"Viewer", "Admin"}), grant_type="test")
VIEWER = User(name="test-viewer", scopes=frozenset({"Viewer"}), grant_type="test")


def _client_as(user: User | None):
    fresh = Store()  # cada teste comeca com dados limpos
    app.dependency_overrides[get_store] = lambda: fresh
    if user is not None:
        app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


@pytest.fixture
def client():
    """Cliente autenticado como Admin (troca o XSUAA por um usuario fake)."""
    yield _client_as(ADMIN)
    app.dependency_overrides.clear()


@pytest.fixture
def viewer_client():
    yield _client_as(VIEWER)
    app.dependency_overrides.clear()


@pytest.fixture
def anon_client(monkeypatch):
    """Sem override de usuario: passa pela validacao real do app.auth."""
    monkeypatch.delenv("AUTH_MODE", raising=False)
    yield _client_as(None)
    app.dependency_overrides.clear()


@pytest.fixture
def supplier(client):
    return client.post("/suppliers", json={"name": "Acme", "country": "BR"}).json()
