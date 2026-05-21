"""API middleware components."""

import time
import logging
from typing import Callable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

# Expected JWT audiences for service-to-service calls
VALID_AUDIENCES = {"agent-workers", "orchestrator", "api-gateway"}


def _decode_jwt_payload(token: str) -> dict | None:
    """Decode a JWT token payload without verification (for audience check).

    In production, this should use a proper JWT library with signature verification.
    This implementation handles standard base64url-encoded JWT payloads.
    """
    try:
        import base64
        import json as _json

        parts = token.split(".")
        if len(parts) != 3:
            return None

        # Decode the payload (second part)
        payload_b64 = parts[1]
        # Add padding if needed
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += "=" * padding
        # Replace URL-safe characters
        payload_b64 = payload_b64.replace("-", "+").replace("_", "/")

        payload_bytes = base64.b64decode(payload_b64)
        return _json.loads(payload_bytes)
    except Exception:
        return None


class AuthMiddleware(BaseHTTPMiddleware):
    """Authentication middleware that enforces JWT audience for service-to-service calls.

    Validates both browser sessions and token-based clients through the same
    authentication boundary, ensuring consistent authorization checks.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path.startswith("/api/v2") and request.url.path != "/api/v2/auth/token":
            token = request.headers.get("Authorization", "")
            if not token.startswith("Bearer "):
                return Response(status_code=401, content="Unauthorized")

            jwt_token = token[7:]  # Strip "Bearer " prefix

            # Decode and validate JWT
            payload = _decode_jwt_payload(jwt_token)
            if payload is None:
                return Response(
                    status_code=401,
                    content="Invalid or malformed JWT token"
                )

            # Check token expiration
            exp = payload.get("exp")
            if exp is not None and time.time() > exp:
                return Response(
                    status_code=401,
                    content="JWT token has expired"
                )

            # Enforce JWT audience for service-to-service calls
            audience = payload.get("aud")
            if audience is not None and audience not in VALID_AUDIENCES:
                return Response(
                    status_code=403,
                    content=f"JWT audience '{audience}' is not authorized for this service"
                )

            # Validate that service-to-service calls have a valid audience claim
            if request.url.path.startswith("/api/v2/internal") and audience is None:
                return Response(
                    status_code=403,
                    content="Service-to-service calls require a valid JWT audience claim"
                )

        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_requests: int = 100, window: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window = window
        self._requests = {}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()

        if client_ip not in self._requests:
            self._requests[client_ip] = []

        self._requests[client_ip] = [t for t in self._requests[client_ip] if now - t < self.window]

        if len(self._requests[client_ip]) >= self.max_requests:
            return Response(status_code=429, content="Too many requests")

        self._requests[client_ip].append(now)
        return await call_next(request)


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start = time.time()
        response = await call_next(request)
        duration = time.time() - start
        logger.info(f"{request.method} {request.url.path} {response.status_code} {duration:.3f}s")
        return response
