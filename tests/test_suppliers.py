def test_health(client):
    assert client.get("/health").json()["status"] == "UP"


def test_create_and_get_supplier(client):
    r = client.post("/suppliers", json={"name": "Acme", "country": "BR"})
    assert r.status_code == 201
    assert client.get(f"/suppliers/{r.json()['id']}").json()["name"] == "Acme"


def test_duplicate_supplier_returns_409(client, supplier):
    r = client.post("/suppliers", json={"name": "acme", "country": "US"})
    assert r.status_code == 409


def test_invalid_country_returns_422(client):
    assert client.post("/suppliers", json={"name": "Acme", "country": "BRA"}).status_code == 422


def test_unknown_supplier_returns_404(client):
    assert client.get("/suppliers/999").status_code == 404
