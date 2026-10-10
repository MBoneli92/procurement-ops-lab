"""Cotacao de moedas via destination 'fx-rates' (API publica Frankfurter, taxas do BCE)."""

import logging
from dataclasses import dataclass
from decimal import Decimal

import httpx

from app.destination import DestinationError, get_destination

log = logging.getLogger(__name__)

FX_DESTINATION = "fx-rates"


@dataclass(frozen=True)
class FxRate:
    rate: Decimal
    date: str
    source: str


def get_rate(client: httpx.Client, base: str, quote: str) -> FxRate:
    destination = get_destination(client, FX_DESTINATION)
    url = f"{destination.url}/v2/rate/{base}/{quote}"
    log.info("Calling destination %s: GET %s", destination.name, url)

    try:
        response = client.get(url)
    except httpx.HTTPError as exc:
        log.warning("Destination %s unreachable at %s: %r", destination.name, destination.url, exc)
        reason = type(exc).__name__
        raise DestinationError(
            f"Destination '{destination.name}' unreachable ({destination.url}): {reason}"
        ) from exc

    if response.status_code == 422:
        raise DestinationError(f"Currency not supported: {quote}", status_code=422)
    if response.status_code != 200:
        log.warning(
            "Destination %s returned HTTP %s for %s", destination.name, response.status_code, url
        )
        raise DestinationError(
            f"Destination '{destination.name}' returned HTTP {response.status_code} for {url}"
        )

    data = response.json()
    return FxRate(rate=Decimal(str(data["rate"])), date=data["date"], source=destination.name)
