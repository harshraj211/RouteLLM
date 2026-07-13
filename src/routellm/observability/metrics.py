from prometheus_client import Counter, Gauge, Histogram

REQUEST_COUNTER = Counter(
    "routellm_requests_total",
    "Total number of routing requests processed.",
    ["task_type", "workflow_id", "selected_model"],
)

REQUEST_LATENCY = Histogram(
    "routellm_request_latency_seconds",
    "End-to-end routing latency in seconds.",
    ["task_type", "workflow_id", "selected_model"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

REQUEST_COST = Histogram(
    "routellm_request_cost_usd",
    "Observed request cost in USD.",
    ["task_type", "workflow_id", "selected_model"],
    buckets=(0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05, 0.1, 0.5),
)

ACTIVE_REQUESTS = Gauge(
    "routellm_active_requests",
    "Current number of active routing requests.",
)

ESCALATION_COUNTER = Counter(
    "routellm_escalations_total",
    "Number of requests routed from one candidate model to another.",
    ["task_type", "workflow_id"],
)

INFERENCE_FAILURE_COUNTER = Counter(
    "routellm_inference_failures_total",
    "Number of failed upstream inference attempts.",
    ["model", "reason_code", "retryable"],
)

INFERENCE_RETRY_COUNTER = Counter(
    "routellm_inference_retries_total",
    "Number of same-model upstream inference retries.",
    ["model", "reason_code"],
)

MODEL_FAILOVER_COUNTER = Counter(
    "routellm_model_failovers_total",
    "Number of upstream transport failovers between models.",
    ["from_model", "to_model", "reason_code"],
)
