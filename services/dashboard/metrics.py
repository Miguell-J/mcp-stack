"""Metric aggregation and honest interval estimates, independent of presentation."""

import math

from prometheus_client.parser import text_string_to_metric_families
from pydantic import BaseModel, ConfigDict, Field


class MetricModel(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)


class Totals(MetricModel):
    calls: float = 0
    call_errors: float = 0
    domain_errors: float = 0
    infra_failures: float = 0
    timeouts: float = 0
    circuit_opens: float = 0
    refreshes: float = 0
    cache_hits: float = 0
    cache_misses: float = 0
    catalog_bytes: float = 0
    latency_seconds: float = 0
    latency_count: float = 0
    latency_buckets: dict[str, float] = Field(default_factory=dict)

    @property
    def average_ms(self) -> float | None:
        return self.latency_seconds * 1000 / self.latency_count if self.latency_count else None

    @property
    def error_percent(self) -> float | None:
        return self.call_errors * 100 / self.calls if self.calls else None

    def percentile_upper_ms(self, fraction: float = 0.95) -> float | None:
        if not self.latency_count:
            return None
        for bound, count in sorted(self.latency_buckets.items(), key=lambda item: float(item[0])):
            if count >= self.latency_count * fraction:
                return float(bound) * 1000 if math.isfinite(float(bound)) else None
        return None

    @property
    def p95_overflow(self) -> bool:
        return bool(
            self.latency_buckets and self.latency_count and self.percentile_upper_ms() is None
        )


class Sample(MetricModel):
    at: str
    calls_per_minute: float | None = None
    average_ms: float | None = None
    error_percent: float | None = None
    p95_upper_ms: float | None = None


class ParsedMetrics(MetricModel):
    totals: Totals
    servers: dict[str, Totals]


def parse_metrics(source: str, server_ids: set[str]) -> ParsedMetrics:
    """Only known metric families and configured server labels contribute to totals."""
    parsed = ParsedMetrics(totals=Totals(), servers={key: Totals() for key in server_ids})
    names = {
        "mcp_one_tool_calls_total": "calls",
        "mcp_one_infra_failures_total": "infra_failures",
        "mcp_one_timeouts_total": "timeouts",
        "mcp_one_circuit_opens_total": "circuit_opens",
        "mcp_one_registry_refresh_total": "refreshes",
        "mcp_one_catalog_bytes": "catalog_bytes",
        "mcp_one_tool_latency_seconds_sum": "latency_seconds",
        "mcp_one_tool_latency_seconds_count": "latency_count",
    }
    recognized = False
    for family in text_string_to_metric_families(source):
        for sample in family.samples:
            server = sample.labels.get("server", "unlabelled")
            if server not in server_ids | {""}:
                continue
            if not math.isfinite(sample.value) or sample.value < 0:
                raise ValueError("invalid metric value")
            targets = [parsed.totals]
            if server in parsed.servers:
                targets.append(parsed.servers[server])
            for totals in targets:
                field = names.get(sample.name)
                if field:
                    recognized = True
                    setattr(totals, field, getattr(totals, field) + sample.value)
                if sample.name == "mcp_one_catalog_tools":
                    recognized = True
                if sample.name == "mcp_one_tool_calls_total":
                    outcome = sample.labels.get("outcome")
                    if outcome == "domain_error":
                        totals.domain_errors += sample.value
                    if outcome != "success":
                        totals.call_errors += sample.value
                if sample.name == "mcp_one_catalog_cache_total":
                    if sample.labels.get("outcome") == "hit":
                        totals.cache_hits += sample.value
                    elif sample.labels.get("outcome") == "miss":
                        totals.cache_misses += sample.value
                if sample.name == "mcp_one_tool_latency_seconds_bucket":
                    bound = sample.labels["le"]
                    value = float(bound)
                    if math.isnan(value) or value < 0:
                        raise ValueError("invalid histogram bound")
                    totals.latency_buckets[bound] = (
                        totals.latency_buckets.get(bound, 0) + sample.value
                    )
    if not recognized and server_ids:
        raise ValueError("gateway metrics absent")
    for totals in [parsed.totals, *parsed.servers.values()]:
        if totals.latency_buckets:
            ordered = sorted(totals.latency_buckets, key=float)
            counts = [totals.latency_buckets[bound] for bound in ordered]
            if (
                counts != sorted(counts)
                or counts[-1] != totals.latency_count
                or float(ordered[-1]) != math.inf
            ):
                raise ValueError("inconsistent histogram")
    return parsed


def sample_delta(previous: Totals | None, current: Totals, elapsed: float, at: str) -> Sample:
    sample = Sample(at=at)
    if previous is None or elapsed <= 0:
        return sample
    calls = current.calls - previous.calls
    errors = current.call_errors - previous.call_errors
    count = current.latency_count - previous.latency_count
    seconds = current.latency_seconds - previous.latency_seconds
    if min(calls, errors, count, seconds) < 0:
        return sample  # Reset counters invalidate this interval, not the current observation.
    sample.calls_per_minute = calls * 60 / elapsed
    if calls > 0 and errors <= calls:
        sample.error_percent = errors * 100 / calls
    if count > 0:
        sample.average_ms = seconds * 1000 / count
        if current.latency_buckets.keys() == previous.latency_buckets.keys():
            buckets = {
                key: value - previous.latency_buckets[key]
                for key, value in current.latency_buckets.items()
            }
            if all(value >= 0 for value in buckets.values()):
                sample.p95_upper_ms = Totals(
                    latency_count=count, latency_buckets=buckets
                ).percentile_upper_ms()
    return sample
