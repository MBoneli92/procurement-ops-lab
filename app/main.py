import os
from fastapi import FastAPI

from app.auth import CurrentUser
from app.routers import purchase_orders, suppliers

app = FastAPI(title="procurement-ops-lab", version="0.1.0")
app.include_router(suppliers.router)
app.include_router(purchase_orders.router)


@app.get("/health", tags=["ops"])
def health():
    return {"status": "UP", "version": app.version}


@app.get("/me", tags=["ops"])
def me(user: CurrentUser):
    """Quem e o usuario do token e quais scopes ele tem. Primeiro lugar a olhar num 403."""
    return {"name": user.name, "scopes": sorted(user.scopes), "grant_type": user.grant_type}
