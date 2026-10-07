"""Autenticacao e autorizacao com XSUAA.

No Cloud Foundry, o binding com o servico XSUAA injeta as credenciais em VCAP_SERVICES.
O app recebe o token JWT no header Authorization, valida com sap-xssec e checa os scopes.
"""

import json
import logging
import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

log = logging.getLogger(__name__)

KNOWN_SCOPES = ("Viewer", "Admin")


@dataclass(frozen=True)
class User:
    name: str
    scopes: frozenset[str] = field(default_factory=frozenset)
    grant_type: str = "unknown"


@lru_cache
def get_uaa_credentials() -> dict | None:
    """Le as credenciais do XSUAA de VCAP_SERVICES. None se nao houver binding."""
    raw = os.environ.get("VCAP_SERVICES")
    if not raw:
        return None
    services = json.loads(raw)
    instances = services.get("xsuaa", [])
    return instances[0]["credentials"] if instances else None


def get_current_user(authorization: Annotated[str | None, Header()] = None) -> User:
    # Modo local: sem BTP, usuario fake com todos os scopes. Nunca ligar no Cloud Foundry.
    if os.environ.get("AUTH_MODE") == "local":
        return User(name="local-dev", scopes=frozenset(KNOWN_SCOPES), grant_type="local")

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    credentials = get_uaa_credentials()
    if credentials is None:
        log.error("No xsuaa binding found in VCAP_SERVICES")
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Auth service not bound")

    from sap import xssec  # import tardio: a lib so e necessaria quando ha token de verdade

    token = authorization.split(" ", 1)[1]
    try:
        ctx = xssec.create_security_context(token, credentials)
    except (ValueError, RuntimeError) as exc:
        log.warning("Token validation failed: %s", exc)
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    scopes = frozenset(s for s in KNOWN_SCOPES if ctx.check_local_scope(s))
    name = ctx.get_logon_name() or ctx.get_clientid()
    return User(name=name, scopes=scopes, grant_type=ctx.get_grant_type())


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_scope(scope: str):
    def checker(user: CurrentUser) -> User:
        if scope not in user.scopes:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Missing scope: {scope}")
        return user

    return Depends(checker)


RequireViewer = require_scope("Viewer")
RequireAdmin = require_scope("Admin")
