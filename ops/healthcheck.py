"""Check /health of every procurement-api deployment and raise an alert for each one that fails.

    HEALTH_TARGETS="procurement-api-dev=https://...,procurement-api-prod=https://..." \
        python -m ops.healthcheck

A target is healthy when GET <url>/health answers 200 with {"status": "UP"}.
Each target gets RETRIES attempts before it counts as down, so one slow response is not an incident.
Exit code: 0 all healthy, 1 at least one target down (the workflow run turns red).
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

from ops.alert import AlertConfigError, build_event, send_event

RETRIES = 3
RETRY_WAIT_SECONDS = 5
TIMEOUT_SECONDS = 10
EVENT_TYPE = "HealthCheckFailed"


@dataclass
class Result:
    name: str
    url: str
    healthy: bool
    detail: str
    duration_ms: int


def parse_targets(raw: str) -> dict[str, str]:
    """'a=https://x,b=https://y' -> {'a': 'https://x', 'b': 'https://y'}."""
    targets = {}
    for item in filter(None, (part.strip() for part in raw.split(","))):
        name, sep, url = item.partition("=")
        if not sep or not name.strip() or not url.strip().startswith("https://"):
            raise ValueError(f"invalid target {item!r}, expected name=https://host")
        targets[name.strip()] = url.strip().rstrip("/")
    if not targets:
        raise ValueError("HEALTH_TARGETS is empty")
    return targets


def fetch(url: str) -> tuple[int, str]:
    """GET the url and return (status, body). Network errors come back as status 0."""
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT_SECONDS) as response:
            return response.status, response.read().decode()
    except urllib.error.HTTPError as error:
        return error.code, ""
    except (urllib.error.URLError, TimeoutError) as error:
        return 0, str(error)


def check(name: str, base_url: str, wait: float | None = None) -> Result:
    wait = RETRY_WAIT_SECONDS if wait is None else wait
    url = f"{base_url}/health"
    detail = ""
    for attempt in range(1, RETRIES + 1):
        started = time.monotonic()
        status, body = fetch(url)
        duration_ms = int((time.monotonic() - started) * 1000)
        if status == 200:
            try:
                payload = json.loads(body)
            except ValueError:
                payload = {}
            if payload.get("status") == "UP":
                return Result(name, url, True, f"UP version={payload.get('version')}", duration_ms)
            detail = f"HTTP 200 but body={body[:200]!r}"
        else:
            detail = f"HTTP {status} {body[:200]}".strip()
        if attempt < RETRIES:
            time.sleep(wait)
    return Result(name, url, False, f"{detail} (after {RETRIES} attempts)", duration_ms)


def alert(result: Result) -> None:
    event = build_event(
        EVENT_TYPE,
        result.name,
        "ERROR",
        f"{result.name} is down",
        f"GET {result.url} failed: {result.detail}",
        tags={"runbook": "RB-006", "run_url": os.environ.get("RUN_URL", "local")},
    )
    try:
        status = send_event(event)
        print(json.dumps({"alert": EVENT_TYPE, "target": result.name, "http_status": status}))
    except AlertConfigError as error:
        print(f"::warning::alert not sent for {result.name}: {error}")


def write_summary(results: list[Result]) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    lines = ["## Health check", "", "| Target | Result | Detail | ms |", "|---|---|---|---|"]
    for r in results:
        state = "UP" if r.healthy else "DOWN"
        lines.append(f"| {r.name} | {state} | {r.detail} | {r.duration_ms} |")
    with open(path, "a", encoding="utf-8") as summary:
        summary.write("\n".join(lines) + "\n")


def main() -> int:
    targets = parse_targets(os.environ.get("HEALTH_TARGETS", ""))
    results = [check(name, url) for name, url in targets.items()]
    for result in results:
        print(json.dumps(result.__dict__))
        if not result.healthy:
            alert(result)
    write_summary(results)
    return 0 if all(r.healthy for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
