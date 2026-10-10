"""Cliente HTTP compartilhado. Fica atras de uma dependencia para os testes trocarem por um mock."""

from collections.abc import Iterator
from typing import Annotated

import httpx
from fastapi import Depends

TIMEOUT_SECONDS = 10.0


def get_http_client() -> Iterator[httpx.Client]:
    with httpx.Client(timeout=TIMEOUT_SECONDS) as client:
        yield client


HttpClientDep = Annotated[httpx.Client, Depends(get_http_client)]
