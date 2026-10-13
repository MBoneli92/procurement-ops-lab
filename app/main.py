import logging
import time
import uuid

from fastapi import FastAPI, Request

from app.auth import CurrentUser
from app.logging_config import setup_logging
from app.routers import conversion, purchase_orders, suppliers

setup_logging()
access_log = logging.getLogger("procurement.access")

app = FastAPI(title="procurement-ops-lab", version="0.5.0")
app.include_router(suppliers.router)
app.include_router(purchase_orders.router)
app.include_router(conversion.router)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """One JSON line per request, tagged with a request id.

    The Cloud Foundry router already sends X-Vcap-Request-Id; reusing it links our log line to the
    router's RTR line in `cf logs`. Locally there is no router, so we generate one.
    """
    request_id = (
        request.headers.get("x-request-id")
        or request.headers.get("x-vcap-request-id")
        or str(uuid.uuid4())
    )
    started = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    status = response.status_code
    access_log.log(
        logging.WARNING if status >= 500 else logging.INFO,
        "request",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status": status,
            "duration_ms": round((time.perf_counter() - started) * 1000, 1),
        },
    )
    return response


@app.get("/health", tags=["ops"])
def health():
    return {"status": "UP", "version": app.version}


@app.get("/me", tags=["ops"])
def me(user: CurrentUser):
    """Quem e o usuario do token e quais scopes ele tem. Primeiro lugar a olhar num 403."""
    return {"name": user.name, "scopes": sorted(user.scopes), "grant_type": user.grant_type}
