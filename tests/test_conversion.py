import json

import httpx
import pytest

from app import destination
from app.http_client import get_http_client
from app.main import app

ITEMS = [{"material": "MAT-001", "quantity": "2", "unit_price": "10.50"}]  # total 21.00 USD

DEST_CREDS = {
    "clientid": "dest-client",
    "clientsecret": "dest-secret",
    "url": "https://auth.example",
    "uri": "https://destination.example",
}
FX_URL = "https://fx.example"


@pytest.fixture
def bound(monkeypatch):
    """Simula o binding com o Destination service."""
    monkeypatch.setenv("VCAP_SERVICES", json.dumps({"destination": [{"credentials": DEST_CREDS}]}))
    destination.get_destination_credentials.cache_clear()
    yield
    destination.get_destination_credentials.cache_clear()


def use_transport(handler):
    """Troca o cliente HTTP real por um mock: nenhuma chamada sai da maquina."""
    app.dependency_overrides[get_http_client] = lambda: httpx.Client(
        transport=httpx.MockTransport(handler)
    )


def fake_btp(fx_response=None, dest_status=200, fx_error=None, fx_url=FX_URL):
    """Responde como o XSUAA, o Destination service e a API de cambio."""

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == "https://auth.example/oauth/token":
            return httpx.Response(200, json={"access_token": "t0k3n"})
        if url.startswith("https://destination.example/destination-configuration/v1/destinations/"):
            assert request.headers["Authorization"] == "Bearer t0k3n"
            if dest_status != 200:
                return httpx.Response(dest_status, json={"ErrorMessage": "not found"})
            config = {"Name": "fx-rates", "URL": fx_url, "Authentication": "NoAuthentication"}
            return httpx.Response(200, json={"destinationConfiguration": config})
        if url.startswith(fx_url):
            if fx_error:
                raise fx_error
            return fx_response
        raise AssertionError(f"unexpected call: {url}")

    return handler


@pytest.fixture
def order(client):
    s = client.post("/suppliers", json={"name": "Acme", "country": "US"}).json()
    return client.post("/purchase-orders", json={"supplier_id": s["id"], "items": ITEMS}).json()


def test_converts_total_using_destination(client, order, bound):
    rate = {"date": "2026-10-10", "base": "USD", "quote": "BRL", "rate": 5.0111}
    use_transport(fake_btp(fx_response=httpx.Response(200, json=rate)))
    r = client.get(f"/purchase-orders/{order['id']}/converted", params={"currency": "BRL"})
    assert r.status_code == 200
    body = r.json()
    assert body["converted_total"] == "105.23"
    assert body["rate_date"] == "2026-10-10"
    assert body["source"] == "destination:fx-rates"


def test_same_currency_makes_no_external_call(client, order):
    use_transport(lambda request: pytest.fail("no HTTP call expected"))
    r = client.get(f"/purchase-orders/{order['id']}/converted", params={"currency": "USD"})
    assert r.json()["converted_total"] == "21.00"


def test_viewer_can_convert(viewer_client):
    r = viewer_client.get("/purchase-orders/999/converted", params={"currency": "BRL"})
    assert r.status_code == 404  # passou da autorizacao; pedido nao existe


def test_invalid_currency_format_returns_422(client, order):
    r = client.get(f"/purchase-orders/{order['id']}/converted", params={"currency": "brl"})
    assert r.status_code == 422


def test_without_destination_binding_returns_503(client, order, monkeypatch):
    monkeypatch.delenv("VCAP_SERVICES", raising=False)
    destination.get_destination_credentials.cache_clear()
    r = client.get(f"/purchase-orders/{order['id']}/converted", params={"currency": "BRL"})
    assert r.status_code == 503
    assert r.json()["detail"] == "Destination service not bound"


def test_destination_not_found_returns_502(client, order, bound):
    use_transport(fake_btp(dest_status=404))
    r = client.get(f"/purchase-orders/{order['id']}/converted", params={"currency": "BRL"})
    assert r.status_code == 502
    assert "not found" in r.json()["detail"]


def test_wrong_host_in_destination_returns_502(client, order, bound):
    error = httpx.ConnectError("name resolution failed")
    use_transport(fake_btp(fx_error=error))
    r = client.get(f"/purchase-orders/{order['id']}/converted", params={"currency": "BRL"})
    assert r.status_code == 502
    assert "unreachable" in r.json()["detail"]


def test_wrong_path_in_destination_returns_502(client, order, bound):
    use_transport(fake_btp(fx_response=httpx.Response(404, json={"message": "not found"})))
    r = client.get(f"/purchase-orders/{order['id']}/converted", params={"currency": "BRL"})
    assert r.status_code == 502
    assert "HTTP 404" in r.json()["detail"]


def test_unknown_currency_returns_422(client, order, bound):
    error = httpx.Response(422, json={"status": 422, "message": "invalid currency: XYZ"})
    use_transport(fake_btp(fx_response=error))
    r = client.get(f"/purchase-orders/{order['id']}/converted", params={"currency": "XYZ"})
    assert r.status_code == 422
    assert r.json()["detail"] == "Currency not supported: XYZ"
