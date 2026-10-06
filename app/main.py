from fastapi import FastAPI

from app.routers import purchase_orders, suppliers

app = FastAPI(title="procurement-ops-lab", version="0.1.0")
app.include_router(suppliers.router)
app.include_router(purchase_orders.router)


@app.get("/health", tags=["ops"])
def health():
    return {"status": "UP", "version": app.version}
