from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.auth import RequireViewer
from app.destination import DestinationError
from app.fx import get_rate
from app.http_client import HttpClientDep
from app.routers.purchase_orders import _get_order
from app.store import StoreDep

router = APIRouter(prefix="/purchase-orders", tags=["purchase-orders"])


@router.get("/{order_id}/converted", dependencies=[RequireViewer])
def converted_total(
    order_id: int,
    store: StoreDep,
    http: HttpClientDep,
    currency: Annotated[str, Query(pattern="^[A-Z]{3}$", description="ISO 4217, ex.: BRL")],
):
    """Total do pedido convertido para outra moeda, com cotacao vinda da destination fx-rates."""
    order = _get_order(order_id, store)

    if currency == order.currency:
        rate, rate_date, source = Decimal("1"), None, "same-currency"
    else:
        try:
            fx = get_rate(http, order.currency, currency)
        except DestinationError as exc:
            raise HTTPException(exc.status_code, str(exc)) from exc
        rate, rate_date, source = fx.rate, fx.date, f"destination:{fx.source}"

    return {
        "order_id": order.id,
        "original_currency": order.currency,
        "original_total": str(order.total),
        "currency": currency,
        "rate": str(rate),
        "rate_date": rate_date,
        "converted_total": str((order.total * rate).quantize(Decimal("0.01"))),
        "source": source,
    }
