"""Armazenamento em memoria. Fica atras desta interface para trocar por SQLite depois."""

from datetime import UTC, datetime
from itertools import count
from typing import Annotated

from fastapi import Depends

from app.models import PurchaseOrder, PurchaseOrderCreate, Supplier, SupplierCreate


class Store:
    def __init__(self) -> None:
        self.suppliers: dict[int, Supplier] = {}
        self.orders: dict[int, PurchaseOrder] = {}
        self._supplier_ids = count(1)
        self._order_ids = count(1)

    def add_supplier(self, data: SupplierCreate) -> Supplier:
        supplier = Supplier(id=next(self._supplier_ids), **data.model_dump())
        self.suppliers[supplier.id] = supplier
        return supplier

    def add_order(self, data: PurchaseOrderCreate) -> PurchaseOrder:
        order = PurchaseOrder(
            id=next(self._order_ids), created_at=datetime.now(UTC), **data.model_dump()
        )
        self.orders[order.id] = order
        return order


store = Store()


def get_store() -> Store:
    return store


StoreDep = Annotated[Store, Depends(get_store)]
