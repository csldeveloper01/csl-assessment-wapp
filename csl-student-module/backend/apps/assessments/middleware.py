"""
API Performance & Database Observability Middleware.

Instruments API requests (/api/*) to monitor:
- Resolved route pattern (without sensitive parameters)
- HTTP method & status code
- Total server-side duration (monotonic perf_counter)
- Cumulative database queries executed
- Cumulative database execution time
- Correlation ID (from incoming X-Request-ID / X-Correlation-ID header, or generated)
"""

import logging
import re
import time
import uuid
from django.db import connection

logger = logging.getLogger("api.perf")

# Regex to scrub UUIDs and numeric IDs in unrouted fallback paths
ID_SCRUB_REGEX = re.compile(r"/[0-9a-fA-F-]{8,}(?=/|$)|/\d+(?=/|$)")


class ApiPerformanceMiddleware:
    """
    Lightweight, thread-safe request-duration and database query counter.
    Instruments API requests while ignoring static assets and health checks.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Only instrument API requests; bypass static assets, admin, and health checks
        if not request.path.startswith("/api/"):
            return self.get_response(request)

        headers = getattr(request, "headers", None)
        if headers is not None:
            correlation_id = (
                headers.get("X-Request-ID")
                or headers.get("X-Correlation-ID")
            )
        else:
            meta = getattr(request, "META", {})
            correlation_id = (
                meta.get("HTTP_X_REQUEST_ID")
                or meta.get("HTTP_X_CORRELATION_ID")
            )

        if not correlation_id:
            correlation_id = uuid.uuid4().hex[:8]

        request.correlation_id = correlation_id

        query_count = 0
        db_time_ms = 0.0

        def db_query_logger(execute, sql, params, many, context):
            nonlocal query_count, db_time_ms
            q_start = time.perf_counter()
            try:
                return execute(sql, params, many, context)
            finally:
                db_time_ms += (time.perf_counter() - q_start) * 1000.0
                query_count += 1

        start_time = time.perf_counter()
        response = None
        status_code = 500

        try:
            with connection.execute_wrapper(db_query_logger):
                response = self.get_response(request)
            if response is not None:
                status_code = response.status_code
            return response
        finally:
            total_ms = (time.perf_counter() - start_time) * 1000.0
            resolver_match = getattr(request, "resolver_match", None)
            if resolver_match and hasattr(resolver_match, "route") and resolver_match.route:
                route_pattern = "/" + resolver_match.route.lstrip("/")
            else:
                route_pattern = ID_SCRUB_REGEX.sub("/:id", request.path)

            logger.info(
                "API_PERF req_id=%s method=%s route=%s status=%d total_ms=%.1f db_queries=%d db_time_ms=%.1f",
                correlation_id,
                request.method,
                route_pattern,
                status_code,
                total_ms,
                query_count,
                db_time_ms,
            )

            if response is not None and "X-Request-ID" not in response:
                response["X-Request-ID"] = correlation_id
