ITEMS = [{"material": "MAT-001", "quantity": "2", "unit_price": "10.50"}]


def test_create_order_computes_total(client, supplier):
    r = client.post("/purchase-orders", json={"supplier_id": supplier["id"], "items": ITEMS})
    assert r.status_code == 201
    assert r.json()["status"] == "DRAFT"
    assert r.json()["total"] == "21.00"


def test_order_for_missing_supplier_returns_422(client):
    r = client.post("/purchase-orders", json={"supplier_id": 999, "items": ITEMS})
    assert r.status_code == 422


def test_order_for_blocked_supplier_returns_422(client):
    s = client.post("/suppliers", json={"name": "Bad", "country": "BR", "blocked": True}).json()
    r = client.post("/purchase-orders", json={"supplier_id": s["id"], "items": ITEMS})
    assert r.status_code == 422
    assert "blocked" in r.json()["detail"]


def test_order_without_items_returns_422(client, supplier):
    r = client.post("/purchase-orders", json={"supplier_id": supplier["id"], "items": []})
    assert r.status_code == 422


def test_full_approval_flow(client, supplier):
    po = client.post("/purchase-orders", json={"supplier_id": supplier["id"], "items": ITEMS})
    po_id = po.json()["id"]
    assert client.post(f"/purchase-orders/{po_id}/submit").json()["status"] == "SUBMITTED"
    assert client.post(f"/purchase-orders/{po_id}/approve").json()["status"] == "APPROVED"


def test_cannot_approve_draft(client, supplier):
    po = client.post("/purchase-orders", json={"supplier_id": supplier["id"], "items": ITEMS})
    r = client.post(f"/purchase-orders/{po.json()['id']}/approve")
    assert r.status_code == 409
