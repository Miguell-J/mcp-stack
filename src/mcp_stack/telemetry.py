"""Standard OTel tracing with data-minimizing JSON logs."""

import logging
import os
from typing import Any

import structlog
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

_provider: TracerProvider | None = None


def configure(service: str) -> None:
    global _provider
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    # HTTP access messages can include resource URLs. Our logs contain no arguments or headers.
    for name in ("httpx", "httpx2", "mcp"):
        logging.getLogger(name).setLevel(logging.WARNING)
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
    )
    if _provider is None:
        _provider = TracerProvider(resource=Resource.create({"service.name": service}))
        endpoint = os.environ.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
        if endpoint:
            _provider.add_span_processor(
                BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, timeout=3))
            )
        trace.set_tracer_provider(_provider)


def trace_fields() -> dict[str, Any]:
    context = trace.get_current_span().get_span_context()
    if not context.is_valid:
        return {}
    return {"traceId": f"{context.trace_id:032x}", "spanId": f"{context.span_id:016x}"}
