"""Optional bearer token authentication middleware.

If MCP_AUTH_TOKEN is set in the environment, all incoming HTTP requests
must include a matching Authorization: Bearer <token> header. If the
env var is not set, all requests are allowed (backwards compatible).

Uses a pure ASGI middleware instead of BaseHTTPMiddleware to avoid
assertion errors with the long-lived streaming responses that both
Streamable HTTP (the current MCP transport) and SSE (the deprecated one)
emit. Pure ASGI middleware is transport-agnostic.
"""

import logging
import os

logger = logging.getLogger(__name__)


class BearerAuthMiddleware:
    """Pure ASGI middleware for bearer token auth.

    Unlike BaseHTTPMiddleware, this does not wrap the response stream
    and is fully compatible with long-lived streaming connections
    (Streamable HTTP and the deprecated HTTP+SSE).
    """

    def __init__(self, app, token: str):
        self.app = app
        self.token = token

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = dict(scope.get("headers", []))
            auth_value = headers.get(b"authorization", b"").decode()
            if auth_value != f"Bearer {self.token}":
                logger.warning("Rejected request: invalid or missing auth token")
                await send(
                    {
                        "type": "http.response.start",
                        "status": 401,
                        "headers": [
                            [b"content-type", b"application/json"],
                        ],
                    }
                )
                await send(
                    {
                        "type": "http.response.body",
                        "body": b'{"error": "Unauthorized"}',
                    }
                )
                return
        await self.app(scope, receive, send)


def maybe_add_auth(app):
    """Wrap the ASGI app with bearer auth if MCP_AUTH_TOKEN is set.

    Returns the (possibly wrapped) app.
    """
    token = os.getenv("MCP_AUTH_TOKEN")
    if not token:
        logger.info("MCP_AUTH_TOKEN not set; endpoint authentication disabled")
        return app
    logger.info("MCP endpoint authentication enabled")
    return BearerAuthMiddleware(app, token=token)


class HealthCheckMiddleware:
    """Pure ASGI middleware that responds 200 to GET /health.

    Sits outside the auth layer so Railway's network healthcheck
    succeeds without a bearer token.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope.get("path") == "/health" and scope.get("method") == "GET":
            await send({"type": "http.response.start", "status": 200, "headers": [[b"content-type", b"application/json"]]})
            await send({"type": "http.response.body", "body": b'{"status":"ok"}'})
            return
        await self.app(scope, receive, send)


def add_health_check(app):
    return HealthCheckMiddleware(app)
