import json
import logging

import pytest

from app.logging_config import JsonFormatter
from ops import alert, healthcheck

# --- JSON logging -------------------------------------------------------------------------------


def test_json_formatter_keeps_only_allowed_extra_fields():
    record = logging.LogRecord("procurement.access", logging.INFO, __file__, 1, "request", (), None)
    record.request_id = "abc"
    record.status = 200
    record.authorization = "Bearer secret"  # not in EXTRA_FIELDS, must never be logged
    entry = json.loads(JsonFormatter().format(record))
    assert entry["message"] == "request"
    assert entry["request_id"] == "abc"
    assert entry["status"] == 200
    assert "authorization" not in entry


def test_request_id_is_reused_from_cf_router(client):
    response = client.get("/health", headers={"X-Vcap-Request-Id": "router-123"})
    assert response.headers["X-Request-ID"] == "router-123"


def test_request_id_is_generated_when_missing(client):
    assert len(client.get("/health").headers["X-Request-ID"]) == 36


def test_access_log_line_has_request_fields(client, caplog):
    with caplog.at_level(logging.INFO, logger="procurement.access"):
        client.get("/health", headers={"X-Request-ID": "req-1"})
    record = next(r for r in caplog.records if r.name == "procurement.access")
    assert (record.request_id, record.method, record.path, record.status) == (
        "req-1",
        "GET",
        "/health",
        200,
    )


# --- Alert Notification event -------------------------------------------------------------------


def test_error_severity_becomes_alert_category():
    event = alert.build_event("HealthCheckFailed", "procurement-api-dev", "ERROR", "down", "503")
    assert event["category"] == "ALERT"
    assert event["resource"] == {"resourceName": "procurement-api-dev", "resourceType": "app"}


def test_info_severity_is_a_notification():
    event = alert.build_event("Deployed", "procurement-api-dev", "INFO", "ok", "", tags={"v": 5})
    assert event["category"] == "NOTIFICATION"
    assert event["tags"] == {"v": "5"}


def test_unknown_severity_is_rejected():
    with pytest.raises(ValueError):
        alert.build_event("X", "r", "CRITICAL", "s", "b")


def test_send_event_without_credentials_fails_fast(monkeypatch):
    for name in alert.REQUIRED_ENV:
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(alert.AlertConfigError, match="ALERT_URL"):
        alert.send_event({})


def test_send_event_posts_with_basic_auth(monkeypatch):
    monkeypatch.setenv("ALERT_URL", "https://alert.example/")
    monkeypatch.setenv("ALERT_CLIENT_ID", "id")
    monkeypatch.setenv("ALERT_CLIENT_SECRET", "secret")
    seen = {}

    class FakeResponse:
        status = 202

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def fake_urlopen(request, timeout):
        seen["url"] = request.full_url
        seen["auth"] = request.get_header("Authorization")
        return FakeResponse()

    monkeypatch.setattr(alert.urllib.request, "urlopen", fake_urlopen)
    assert alert.send_event({"eventType": "X"}) == 202
    assert seen["url"] == "https://alert.example/cf/producer/v1/resource-events"
    assert seen["auth"] == "Basic aWQ6c2VjcmV0"


# --- Health check -------------------------------------------------------------------------------


def test_parse_targets():
    raw = "procurement-api-dev=https://dev.example/ , procurement-api-prod=https://prod.example"
    assert healthcheck.parse_targets(raw) == {
        "procurement-api-dev": "https://dev.example",
        "procurement-api-prod": "https://prod.example",
    }


@pytest.mark.parametrize("raw", ["", "dev", "dev=http://insecure.example", "=https://x.example"])
def test_parse_targets_rejects_bad_input(raw):
    with pytest.raises(ValueError):
        healthcheck.parse_targets(raw)


def test_check_healthy(monkeypatch):
    body = '{"status":"UP","version":"0.5.0"}'
    monkeypatch.setattr(healthcheck, "fetch", lambda url: (200, body))
    result = healthcheck.check("dev", "https://dev.example", wait=0)
    assert result.healthy
    assert "0.5.0" in result.detail


def test_check_retries_then_reports_down(monkeypatch):
    calls = []
    monkeypatch.setattr(healthcheck, "fetch", lambda url: calls.append(url) or (503, "unavailable"))
    result = healthcheck.check("dev", "https://dev.example", wait=0)
    assert not result.healthy
    assert len(calls) == healthcheck.RETRIES
    assert "HTTP 503" in result.detail


def test_check_recovers_on_second_attempt(monkeypatch):
    answers = iter([(0, "timed out"), (200, '{"status":"UP"}')])
    monkeypatch.setattr(healthcheck, "fetch", lambda url: next(answers))
    assert healthcheck.check("dev", "https://dev.example", wait=0).healthy


def test_main_alerts_only_failed_targets(monkeypatch, tmp_path):
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    monkeypatch.setenv("HEALTH_TARGETS", "dev=https://dev.example,prod=https://prod.example")
    monkeypatch.setattr(healthcheck, "RETRY_WAIT_SECONDS", 0)
    monkeypatch.setattr(
        healthcheck,
        "fetch",
        lambda url: (200, '{"status":"UP"}') if "prod" in url else (503, ""),
    )
    sent = []
    monkeypatch.setattr(healthcheck, "send_event", lambda event: sent.append(event) or 202)
    assert healthcheck.main() == 1
    assert [e["resource"]["resourceName"] for e in sent] == ["dev"]
    assert "| dev | DOWN |" in summary.read_text()
