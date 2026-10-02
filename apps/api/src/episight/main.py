import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from episight.api.errors import error_response, install_error_handlers
from episight.api.routers import cases, evidence, health
from episight.config import get_settings
from episight.contracts.api import CONTRACT_VERSION
from episight.contracts.enums import ErrorCode
from episight.log import configure_logging, request_id_var

API_PREFIX = "/api/v1"
log = logging.getLogger("episight.request")


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="EPISIGHT API",
        version=f"contract-{CONTRACT_VERSION}",
        description="Evidence-first investigation copilot for Episode Integrity (prototype, synthetic data only).",
        openapi_url=f"{API_PREFIX}/openapi.json",
        docs_url=f"{API_PREFIX}/docs",
        redoc_url=None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Contract-Version"],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            log.exception("unhandled error")
            response = error_response(500, ErrorCode.INTERNAL_ERROR, "Internal error")
        finally:
            request_id_var.reset(token)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Contract-Version"] = CONTRACT_VERSION
        log.info(
            "request",
            extra={
                "fields": {
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                }
            },
        )
        return response

    install_error_handlers(app)
    app.include_router(health.router, prefix=API_PREFIX)
    app.include_router(cases.router, prefix=API_PREFIX)
    app.include_router(evidence.router, prefix=API_PREFIX)
    return app


app = create_app()
