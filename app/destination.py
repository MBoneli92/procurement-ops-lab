"""Leitura de destinations do SAP Destination service.

Fluxo:
1. O binding com o Destination service injeta as credenciais em VCAP_SERVICES.
2. Com elas, o app pede um token OAuth (client credentials) ao XSUAA do servico.
3. Com o token, consulta /destination-configuration/v1/destinations/{nome}.
4. A resposta traz a URL e o tipo de autenticacao configurados no cockpit.

Assim, a URL do sistema externo nao fica no codigo: muda no cockpit, sem novo deploy.
"""

import json
import logging
import os
from dataclasses import dataclass
from functools import lru_cache

import httpx

log = logging.getLogger(__name__)


class DestinationError(Exception):
    """Falha ao obter ou usar uma destination. status_code vira o codigo HTTP da resposta."""

    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class Destination:
    name: str
    url: str
    authentication: str


@lru_cache
def get_destination_credentials() -> dict | None:
    """Credenciais do Destination service lidas de VCAP_SERVICES. None se nao houver binding."""
    raw = os.environ.get("VCAP_SERVICES")
    if not raw:
        return None
    instances = json.loads(raw).get("destination", [])
    return instances[0]["credentials"] if instances else None


def _service_token(client: httpx.Client, creds: dict) -> str:
    try:
        response = client.post(
            f"{creds['url']}/oauth/token",
            data={"grant_type": "client_credentials"},
            auth=(creds["clientid"], creds["clientsecret"]),
        )
    except httpx.HTTPError as exc:
        raise DestinationError(
            f"Destination service auth unreachable: {type(exc).__name__}"
        ) from exc
    if response.status_code != 200:
        raise DestinationError(f"Destination service auth failed: HTTP {response.status_code}")
    return response.json()["access_token"]


def get_destination(client: httpx.Client, name: str) -> Destination:
    creds = get_destination_credentials()
    if creds is None:
        log.error("No destination binding found in VCAP_SERVICES")
        raise DestinationError("Destination service not bound", status_code=503)

    token = _service_token(client, creds)
    try:
        response = client.get(
            f"{creds['uri']}/destination-configuration/v1/destinations/{name}",
            headers={"Authorization": f"Bearer {token}"},
        )
    except httpx.HTTPError as exc:
        raise DestinationError(f"Destination service unreachable: {type(exc).__name__}") from exc

    if response.status_code == 404:
        raise DestinationError(f"Destination '{name}' not found in the subaccount")
    if response.status_code != 200:
        raise DestinationError(f"Destination service returned HTTP {response.status_code}")

    config = response.json()["destinationConfiguration"]
    return Destination(
        name=config["Name"],
        url=config["URL"].rstrip("/"),
        authentication=config.get("Authentication", "NoAuthentication"),
    )
