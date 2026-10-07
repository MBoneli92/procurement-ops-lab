from app import auth


def test_health_is_public(anon_client):
    assert anon_client.get("/health").status_code == 200


def test_no_token_returns_401(anon_client):
    r = anon_client.get("/suppliers")
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"


def test_token_without_xsuaa_binding_returns_503(anon_client, monkeypatch):
    monkeypatch.delenv("VCAP_SERVICES", raising=False)
    auth.get_uaa_credentials.cache_clear()
    r = anon_client.get("/suppliers", headers={"Authorization": "Bearer abc"})
    assert r.status_code == 503


def test_invalid_token_returns_401(anon_client, monkeypatch):
    fake = '{"xsuaa": [{"credentials": {"xsappname": "x", "clientid": "c", "url": "https://u"}}]}'
    monkeypatch.setenv("VCAP_SERVICES", fake)
    auth.get_uaa_credentials.cache_clear()
    r = anon_client.get("/suppliers", headers={"Authorization": "Bearer not-a-jwt"})
    assert r.status_code == 401
    auth.get_uaa_credentials.cache_clear()


def test_viewer_can_read(viewer_client):
    assert viewer_client.get("/suppliers").status_code == 200


def test_viewer_cannot_write_returns_403(viewer_client):
    r = viewer_client.post("/suppliers", json={"name": "Acme", "country": "BR"})
    assert r.status_code == 403
    assert r.json()["detail"] == "Missing scope: Admin"


def test_me_shows_scopes(viewer_client):
    assert viewer_client.get("/me").json()["scopes"] == ["Viewer"]


def test_local_mode_gives_admin(anon_client, monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "local")
    assert anon_client.get("/me").json()["scopes"] == ["Admin", "Viewer"]
