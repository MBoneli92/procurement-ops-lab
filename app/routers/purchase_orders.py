from fastapi import APIRouter, HTTPException, status

from app.auth import RequireAdmin, RequireViewer
from app.models import POStatus, PurchaseOrder, PurchaseOrderCreate
from app.store import Store, StoreDep

router = APIRouter(prefix="/purchase-orders", tags=["purchase-orders"])

# Transicoes permitidas: estado atual -> estados de destino
TRANSITIONS: dict[POStatus, set[POStatus]] = {
    POStatus.DRAFT: {POStatus.SUBMITTED},
    POStatus.SUBMITTED: {POStatus.APPROVED, POStatus.REJECTED},
    POStatus.APPROVED: set(),
    POStatus.REJECTED: set(),
}
ACTIONS = {"submit": POStatus.SUBMITTED, "approve": POStatus.APPROVED, "reject": POStatus.REJECTED}


def _get_order(order_id: int, store: Store) -> PurchaseOrder:
    order = store.orders.get(order_id)
    if not order:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Purchase order not found")
    return order


@router.get("", response_model=list[PurchaseOrder], dependencies=[RequireViewer])
def list_orders(store: StoreDep):
    return list(store.orders.values())


@router.post(
    "",
    response_model=PurchaseOrder,
    status_code=status.HTTP_201_CREATED,
    dependencies=[RequireAdmin],
)
def create_order(data: PurchaseOrderCreate, store: StoreDep):
    supplier = store.suppliers.get(data.supplier_id)
    if not supplier:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Supplier does not exist")
    if supplier.blocked:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Supplier is blocked")
    return store.add_order(data)


@router.get("/{order_id}", response_model=PurchaseOrder, dependencies=[RequireViewer])
def get_order(order_id: int, store: StoreDep):
    return _get_order(order_id, store)


@router.post("/{order_id}/{action}", response_model=PurchaseOrder, dependencies=[RequireAdmin])
def change_status(order_id: int, action: str, store: StoreDep):
    target = ACTIONS.get(action)
    if not target:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown action")
    order = _get_order(order_id, store)
    if target not in TRANSITIONS[order.status]:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Cannot {action} a PO in status {order.status.value}"
        )
    order.status = target
    return order
