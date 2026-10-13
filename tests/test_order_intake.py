"""The integration's technical client (scope OrderIntake) may create orders and nothing else."""

import pytest

from app.auth import User, get_current_user
from app.main import app

INTEGRATION = User(
    name="sb-procurement-ops-lab", scopes=frozenset({"Viewer", "OrderIntake"}), grant_type="test"
)
ITEMS = [{"material": "MAT-001", "quantity": "10", "unit_price": "15.00"}]


@pytest.fixture
def integration_client(client):
    app.dependency_overrides[get_current_user] = lambda: INTEGRATION
    return client


@pytest.fixture
def supplier_id(client):
    return client.post("/suppliers", json={"name": "Acme", "country": "BR"}).json()["id"]


def test_integration_can_create_order(supplier_id, integration_client):
    r = integration_client.post(
        "/purchase-orders", json={"supplier_id": supplier_id, "items": ITEMS}
    )
    assert r.status_code == 201
    assert r.json()["status"] == "DRAFT"


def test_integration_cannot_approve(supplier_id, integration_client):
    po = integration_client.post(
        "/purchase-orders", json={"supplier_id": supplier_id, "items": ITEMS}
    ).json()
    r = integration_client.post(f"/purchase-orders/{po['id']}/submit")
    assert r.status_code == 403
    assert r.json()["detail"] == "Missing scope: Admin"


def test_integration_cannot_create_suppliers(integration_client):
    r = integration_client.post("/suppliers", json={"name": "Evil", "country": "BR"})
    assert r.status_code == 403


def test_viewer_cannot_create_order(supplier_id, viewer_client):
    r = viewer_client.post("/purchase-orders", json={"supplier_id": supplier_id, "items": ITEMS})
    assert r.status_code == 403
    assert "OrderIntake" in r.json()["detail"]


def test_order_creation_is_logged_with_ids(supplier_id, integration_client, caplog):
    with caplog.at_level("INFO", logger="app.routers.purchase_orders"):
        integration_client.post(
            "/purchase-orders", json={"supplier_id": supplier_id, "items": ITEMS}
        )
    record = next(r for r in caplog.records if r.getMessage() == "purchase order created")
    assert (record.supplier_id, record.user) == (supplier_id, "sb-procurement-ops-lab")
