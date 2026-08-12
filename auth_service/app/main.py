"""
Application entrypoint.

Uses the application-factory pattern (`create_app`) so tests can spin up
isolated app instances (e.g. with dependency overrides) without importing
a single, side-effect-laden module-level app.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.exceptions.handlers import register_exception_handlers
from app.middleware.logging import RequestLoggingMiddleware
from app.middleware.rate_limit import limiter
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.utils.logging_config import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    yield
    # Place graceful-shutdown cleanup here (e.g. closing external clients).


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        description="Reusable authentication & identity management service.",
        version="1.0.0",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
    )

    # --- Rate limiting -------------------------------------------------
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
    app.add_middleware(SlowAPIMiddleware)

    # --- CORS ------------------------------------------------------------
    if settings.BACKEND_CORS_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[str(o) for o in settings.BACKEND_CORS_ORIGINS],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # --- Custom middleware (order matters: outermost added last runs first) ---
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestLoggingMiddleware)

    # --- Exception handlers -----------------------------------------------
    register_exception_handlers(app)

    # --- Routers -----------------------------------------------------
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    @app.get("/health", tags=["Health"], summary="Liveness/readiness probe")
    async def health_check() -> dict:
        return {"status": "ok", "environment": settings.ENVIRONMENT}

    return app


def _rate_limit_handler(request, exc):
    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=429,
        content={
            "error": {
                "code": "RATE_LIMITED",
                "message": "Too many requests. Please try again later.",
            }
        },
    )


app = create_app()
