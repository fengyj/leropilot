"""Idempotency middleware for FastAPI.

This middleware caches responses for POST/PUT/DELETE requests based on
the Idempotency-Key header. This prevents duplicate operations when clients
retry requests (e.g., due to network issues or React Strict Mode).

Usage:
    app.add_middleware(IdempotencyMiddleware, ttl_hours=24)
"""

import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from typing import Any

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """Middleware to handle idempotent requests using Idempotency-Key header.

    Caches successful responses (200-299 status codes) for POST/PUT/DELETE requests.
    Subsequent requests with the same idempotency key return the cached response.

    Args:
        app: The ASGI application
        ttl_hours: Time-to-live for cached responses in hours (default: 24)
    """

    def __init__(self, app: ASGIApp, ttl_hours: int = 24) -> None:
        super().__init__(app)
        self.cache: dict[str, tuple[bytes, int, dict[str, Any], datetime]] = {}
        self.ttl = timedelta(hours=ttl_hours)
        logger.info(f"Idempotency middleware initialized with TTL: {ttl_hours}h")

    def cleanup_expired(self) -> None:
        """Remove expired entries from the cache."""
        now = datetime.now()
        expired_keys = [key for key, (_, _, _, timestamp) in self.cache.items() if now - timestamp > self.ttl]

        for key in expired_keys:
            del self.cache[key]

        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired idempotency keys")

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        """Process the request and handle idempotency.

        Args:
            request: The incoming request
            call_next: The next middleware/handler in the chain

        Returns:
            Response from cache or from the actual handler
        """
        # Only handle POST/PUT/DELETE requests
        if request.method not in ["POST", "PUT", "DELETE"]:
            return await call_next(request)

        # Get idempotency key from header
        idempotency_key = request.headers.get("Idempotency-Key")
        if not idempotency_key:
            # No idempotency key provided, process normally
            return await call_next(request)

        # Cleanup expired entries periodically
        self.cleanup_expired()

        # Create cache key: method + path + idempotency_key
        cache_key = f"{request.method}:{request.url.path}:{idempotency_key}"

        # Check if we have a cached response
        if cache_key in self.cache:
            body, status_code, headers, timestamp = self.cache[cache_key]
            logger.info(f"Idempotency cache HIT: {request.method} {request.url.path} (key: {idempotency_key[:8]}...)")

            # Add cache hit header
            response_headers = dict(headers)
            response_headers["X-Idempotency-Cache"] = "HIT"
            response_headers["X-Idempotency-Cached-At"] = timestamp.isoformat()

            return Response(
                content=body,
                status_code=status_code,
                headers=response_headers,
            )

        # Process the request
        response = await call_next(request)

        # Only cache successful responses (2xx status codes)
        if 200 <= response.status_code < 300:
            # Read response body
            body = b""
            if hasattr(response, "body_iterator"):
                async for chunk in response.body_iterator:
                    body += bytes(chunk) if isinstance(chunk, memoryview) else chunk
            else:
                # For regular Response objects, read the body directly
                body_value = response.body
                body = bytes(body_value) if isinstance(body_value, memoryview) else body_value

            # Cache the response
            self.cache[cache_key] = (
                body,
                response.status_code,
                dict(response.headers),
                datetime.now(),
            )

            logger.info(
                f"Idempotency cache MISS: {request.method} {request.url.path} "
                f"(key: {idempotency_key[:8]}...) - Cached response"
            )

            # Return response with original body
            return Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
            )

        # Don't cache error responses
        logger.debug(
            f"Idempotency: Not caching error response {response.status_code} for {request.method} {request.url.path}"
        )
        return response

    def get_cache_stats(self) -> dict[str, int | float]:
        """Get statistics about the cache.

        Returns:
            Dictionary with cache statistics
        """
        now = datetime.now()
        expired_count = sum(1 for _, _, _, timestamp in self.cache.values() if now - timestamp > self.ttl)

        return {
            "total_entries": len(self.cache),
            "expired_entries": expired_count,
            "active_entries": len(self.cache) - expired_count,
            "ttl_hours": self.ttl.total_seconds() / 3600,
        }

    def clear_cache(self) -> int:
        """Clear all cached entries.

        Returns:
            Number of entries cleared
        """
        count = len(self.cache)
        self.cache.clear()
        logger.info(f"Cleared {count} idempotency cache entries")
        return count
