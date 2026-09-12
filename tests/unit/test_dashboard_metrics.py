import pytest
from prometheus_client import CollectorRegistry, Counter, Histogram, generate_latest

from services.dashboard.metrics import Totals, parse_metrics, sample_delta


def test_per_server_histograms_rates_and_retry_failures():
    registry = CollectorRegistry()
    calls = Counter("mcp_one_tool_calls_total", "calls", ["server", "outcome"], registry=registry)
    failures = Counter(
        "mcp_one_infra_failures_total", "attempts", ["server", "outcome"], registry=registry
    )
    latency = Histogram(
        "mcp_one_tool_latency_seconds",
        "seconds",
        ["server"],
        buckets=(0.01, 0.1, 1),
        registry=registry,
    )
    calls.labels("a", "success").inc(9)
    calls.labels("a", "domain_error").inc()
    calls.labels("b", "success").inc(10)
    failures.labels("a", "CALL_TIMEOUT").inc(3)
    for value in [0.001] * 8 + [0.05, 0.5]:
        latency.labels("a").observe(value)
    for _ in range(10):
        latency.labels("b").observe(0.001)
    metrics = parse_metrics(generate_latest(registry).decode(), {"a", "b"})
    assert metrics.totals.calls == 20 and metrics.totals.infra_failures == 3
    assert metrics.totals.error_percent == 5  # attempt failures aren't extra failed calls
    assert metrics.servers["a"].error_percent == 10
    assert metrics.servers["b"].error_percent == 0
    assert metrics.totals.average_ms == pytest.approx(28.4)
    assert metrics.totals.percentile_upper_ms() == 100
    assert metrics.servers["a"].percentile_upper_ms() == 1000
    assert metrics.servers["b"].percentile_upper_ms() == 10
    baseline = Totals(latency_buckets={key: 0 for key in metrics.totals.latency_buckets})
    sample = sample_delta(baseline, metrics.totals, 5, "now")
    assert sample.calls_per_minute == 240
    assert sample.error_percent == 5 and sample.p95_upper_ms == 100
    quiet = sample_delta(metrics.totals, metrics.totals, 5, "later")
    assert quiet.calls_per_minute == 0
    assert quiet.average_ms is None and quiet.error_percent is None
    reset = sample_delta(metrics.totals, baseline, 5, "restart")
    assert reset.calls_per_minute is None and reset.p95_upper_ms is None


def test_histogram_overflow_is_not_reported_as_finite_p95():
    totals = Totals(latency_count=1, latency_buckets={"0.1": 0, "1.0": 0, "+Inf": 1})
    assert totals.percentile_upper_ms() is None
    assert totals.p95_overflow
    assert not Totals().p95_overflow


def test_inconsistent_histogram_is_an_invalid_observation():
    source = """
mcp_one_tool_latency_seconds_bucket{server="a",le="0.1"} 3
mcp_one_tool_latency_seconds_bucket{server="a",le="1.0"} 1
mcp_one_tool_latency_seconds_bucket{server="a",le="+Inf"} 2
mcp_one_tool_latency_seconds_count{server="a"} 2
"""
    with pytest.raises(ValueError, match="inconsistent histogram"):
        parse_metrics(source, {"a"})
