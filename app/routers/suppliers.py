from fastapi import APIRouter, HTTPException, status

from app.auth import RequireAdmin, RequireViewer
from app.models import Supplier, SupplierCreate
from app.store import StoreDep

router = APIRouter(prefix="/suppliers", tags=["suppliers"])


@router.get("", response_model=list[Supplier], dependencies=[RequireViewer])
def list_suppliers(store: StoreDep):
    return list(store.suppliers.values())


@router.post(
    "",
    response_model=Supplier,
    status_code=status.HTTP_201_CREATED,
    dependencies=[RequireAdmin],
)
def create_supplier(data: SupplierCreate, store: StoreDep):
    if any(s.name.lower() == data.name.lower() for s in store.suppliers.values()):
        raise HTTPException(status.HTTP_409_CONFLICT, "Supplier with this name already exists")
    return store.add_supplier(data)


@router.get("/{supplier_id}", response_model=Supplier, dependencies=[RequireViewer])
def get_supplier(supplier_id: int, store: StoreDep):
    supplier = store.suppliers.get(supplier_id)
    if not supplier:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Supplier not found")
    return supplier
