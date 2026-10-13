"""Send a custom event to SAP Alert Notification service (producer API, basic auth).

    python -m ops.alert --event-type HealthCheckFailed --resource procurement-api-dev \
        --severity ERROR --subject "procurement-api-dev is down" --body "GET /health -> 503"

Credentials come from the environment (never from arguments, so they do not land in shell history):
ALERT_URL, ALERT_CLIENT_ID, ALERT_CLIENT_SECRET. They are the url, client_id and client_secret
fields of a BASIC service key with the ALERT_WRITE permission.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request

PRODUCER_PATH = "/cf/producer/v1/resource-events"
SEVERITIES = ("INFO", "NOTICE", "WARNING", "ERROR", "FATAL")
REQUIRED_ENV = ("ALERT_URL", "ALERT_CLIENT_ID", "ALERT_CLIENT_SECRET")


class AlertConfigError(RuntimeError):
    """Raised when the Alert Notification credentials are missing."""


def build_event(
    event_type: str,
    resource_name: str,
    severity: str,
    subject: str,
    body: str,
    tags: dict[str, str] | None = None,
) -> dict:
    """Build the JSON body the producer API expects.

    ERROR and FATAL go out as category ALERT; everything else is a NOTIFICATION.
    The condition in Alert Notification matches on eventType, so the category is informative only.
    """
    if severity not in SEVERITIES:
        raise ValueError(f"severity must be one of {SEVERITIES}, got {severity!r}")
    return {
        "eventType": event_type,
        "resource": {"resourceName": resource_name, "resourceType": "app"},
        "severity": severity,
        "category": "ALERT" if severity in ("ERROR", "FATAL") else "NOTIFICATION",
        "subject": subject,
        "body": body,
        "tags": {key: str(value) for key, value in (tags or {}).items()},
    }


def send_event(event: dict, timeout: float = 10) -> int:
    """POST the event and return the HTTP status (202 means accepted)."""
    missing = [name for name in REQUIRED_ENV if not os.environ.get(name)]
    if missing:
        raise AlertConfigError(f"missing environment variables: {', '.join(missing)}")

    url = os.environ["ALERT_URL"].rstrip("/") + PRODUCER_PATH
    user_pass = f"{os.environ['ALERT_CLIENT_ID']}:{os.environ['ALERT_CLIENT_SECRET']}"
    request = urllib.request.Request(
        url,
        data=json.dumps(event).encode(),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Basic " + base64.b64encode(user_pass.encode()).decode(),
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--event-type", required=True)
    parser.add_argument("--resource", required=True)
    parser.add_argument("--severity", default="INFO", choices=SEVERITIES)
    parser.add_argument("--subject", required=True)
    parser.add_argument("--body", default="")
    args = parser.parse_args(argv)

    event = build_event(args.event_type, args.resource, args.severity, args.subject, args.body)
    try:
        status = send_event(event)
    except AlertConfigError as error:
        print(f"alert not sent: {error}", file=sys.stderr)
        return 2
    print(json.dumps({"alert": args.event_type, "resource": args.resource, "http_status": status}))
    return 0 if status == 202 else 1


if __name__ == "__main__":
    sys.exit(main())
