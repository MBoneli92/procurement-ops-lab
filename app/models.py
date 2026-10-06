from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field, computed_field


class SupplierCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    country: str = Field(min_length=2, max_length=2, description="ISO 3166-1 alpha-2")
    blocked: bool = False


class Supplier(SupplierCreate):
    id: int


class POStatus(str, Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class POItem(BaseModel):
    material: str = Field(min_length=1, max_length=40)
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal = Field(ge=0)


class PurchaseOrderCreate(BaseModel):
    supplier_id: int
    currency: str = Field(default="USD", min_length=3, max_length=3)
    items: list[POItem] = Field(min_length=1)


class PurchaseOrder(PurchaseOrderCreate):
    id: int
    status: POStatus = POStatus.DRAFT
    created_at: datetime

    @computed_field
    @property
    def total(self) -> Decimal:
        return sum((i.quantity * i.unit_price for i in self.items), Decimal("0"))
