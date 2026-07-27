"""
API Middleware

Custom middleware for the FastAPI application:
- Request ID injection
- Request/Response logging
- Rate limiting (in-memory token bucket)
- Security headers
- API key authentication (optional)
"""

import logging
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Callable, Dict, Optional, Tuple

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


# =========================================================================
# Request ID Middleware
# =========================================================================


class RequestIdMiddleware(BaseHTTPMiddleware):
    """
    Inject a unique X-Request-ID header into every request/response.
    If the caller already provides one, re-use it.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


# =========================================================================
# Logging Middleware
# =========================================================================


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Log every HTTP request with method, path, status code, and latency.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start = time.perf_counter()
        request_id = getattr(request.state, "request_id", "unknown")

        # Log request
        logger.info(
            "→ %s %s [%s] client=%s",
            request.method,
            request.url.path,
            request_id,
            request.client.host if request.client else "unknown",
        )

        try:
            response = await call_next(request)
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            logger.error(
                "✗ %s %s [%s] error=%s %.1fms",
                request.method,
                request.url.path,
                request_id,
                str(exc),
                elapsed,
            )
            raise

        elapsed = (time.perf_counter() - start) * 1000
        logger.info(
            "← %s %s [%s] status=%d %.1fms",
            request.method,
            request.url.path,
            request_id,
            response.status_code,
            elapsed,
        )

        response.headers["X-Response-Time"] = f"{elapsed:.1f}ms"
        return response


# =========================================================================
# Rate Limiting Middleware (Token Bucket)
# =========================================================================


class _TokenBucket:
    """Simple in-memory token bucket for a single client."""

    def __init__(self, rate: float, capacity: int):
        self.rate = rate  # tokens per second
        self.capacity = capacity
        self.tokens = float(capacity)
        self.last_refill = time.monotonic()

    def consume(self) -> bool:
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last_refill = now
        if self.tokens >= 1:
            self.tokens -= 1
            return True
        return False


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Per-client-IP rate limiting using an in-memory token bucket.

    Defaults to 60 requests per minute per client.
    Exempt paths: /health, /health/ready, /health/live, /docs, /openapi.json
    """

    EXEMPT_PATHS = {"/health", "/health/ready", "/health/live", "/docs", "/openapi.json", "/redoc"}

    def __init__(self, app, rate: float = 1.0, capacity: int = 60):
        """
        Args:
            rate: Tokens replenished per second.
            capacity: Maximum burst capacity.
        """
        super().__init__(app)
        self.rate = rate
        self.capacity = capacity
        self._buckets: Dict[str, _TokenBucket] = defaultdict(
            lambda: _TokenBucket(self.rate, self.capacity)
        )

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)

        client_ip = request.client.host if request.client else "0.0.0.0"
        bucket = self._buckets[client_ip]

        if not bucket.consume():
            logger.warning("Rate limit exceeded for %s on %s", client_ip, request.url.path)
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded. Please try again later.",
                    "retry_after_seconds": int(1 / self.rate),
                },
                headers={"Retry-After": str(int(1 / self.rate))},
            )

        response = await call_next(request)
        remaining = max(int(bucket.tokens), 0)
        response.headers["X-RateLimit-Limit"] = str(self.capacity)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response


# =========================================================================
# Security Headers Middleware
# =========================================================================


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Inject common security headers into all responses.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"

        # Strict Transport Security (only relevant behind HTTPS)
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response


# =========================================================================
# API Key Authentication Middleware (Optional)
# =========================================================================


class ApiKeyMiddleware(BaseHTTPMiddleware):
    """
    Optional API-key authentication middleware.

    If ``api_keys`` is empty the middleware is a no-op (passes everything).
    Otherwise it checks for a valid key in ``X-API-Key`` header or
    ``api_key`` query parameter.

    Exempt paths (health checks, docs) are always allowed.
    """

    EXEMPT_PATHS = {"/health", "/health/ready", "/health/live", "/docs", "/openapi.json", "/redoc"}

    def __init__(self, app, api_keys: Optional[Dict[str, str]] = None):
        """
        Args:
            api_keys: Mapping of API key → description/owner.
                      If None or empty, authentication is disabled.
        """
        super().__init__(app)
        self.api_keys = api_keys or {}
        self.enabled = bool(self.api_keys)
        if self.enabled:
            logger.info("API key authentication enabled (%d keys configured)", len(self.api_keys))
        else:
            logger.info("API key authentication disabled (no keys configured)")

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not self.enabled:
            return await call_next(request)

        if request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)

        # Check header first, then query param
        api_key = request.headers.get("X-API-Key") or request.query_params.get("api_key")

        if not api_key or api_key not in self.api_keys:
            logger.warning(
                "Unauthorised request to %s from %s",
                request.url.path,
                request.client.host if request.client else "unknown",
            )
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key."},
            )

        # Attach key owner to request state
        request.state.api_key_owner = self.api_keys[api_key]
        return await call_next(request)


# =========================================================================
# Helper: register all middleware on an app instance
# =========================================================================


def register_middleware(
    app,
    enable_rate_limit: bool = True,
    rate_limit_rate: float = 1.0,
    rate_limit_capacity: int = 60,
    enable_api_keys: bool = False,
    api_keys: Optional[Dict[str, str]] = None,
) -> None:
    """
    Register all custom middleware on the FastAPI application.

    Call this in the app factory / lifespan. Middleware executes in
    reverse registration order (last registered = outermost).
    """
    # Outermost → innermost: Security → Logging → RequestId → RateLimit → ApiKey
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(RequestIdMiddleware)

    if enable_rate_limit:
        app.add_middleware(RateLimitMiddleware, rate=rate_limit_rate, capacity=rate_limit_capacity)

    if enable_api_keys:
        app.add_middleware(ApiKeyMiddleware, api_keys=api_keys)

    logger.info("Custom middleware registered (rate_limit=%s, api_keys=%s)", enable_rate_limit, enable_api_keys)
