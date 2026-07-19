from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
import time


logger = logging.getLogger("app.capture")


class InterpretationTimer:
    def __init__(self):
        self.started = time.perf_counter()

    @property
    def milliseconds(self) -> float:
        return round((time.perf_counter() - self.started) * 1000, 2)


def emit_capture_metric(
    name: str,
    *,
    capture_id: str | None = None,
    proposal_id: str | None = None,
    correlation_id: str | None = None,
    result: str = "success",
    value: float = 1,
    unit: str = "Count",
    model: str | None = None,
    action_type: str | None = None,
) -> None:
    """Emit CloudWatch EMF without any user-authored or protected content."""
    allowed = {
        "CapturesCreated", "DeterministicallyInterpreted", "AIInterpreted", "NeedsClarification",
        "ReadyForReview", "Approved", "Rejected", "Completed", "PartiallyCompleted", "Failed",
        "BudgetDenied", "ProviderTimeout", "SchemaValidationFailure", "ActionPolicyRejected",
        "EstimatedAICost", "InterpretationLatencyMs",
    }
    if name not in allowed:
        raise ValueError("Unsupported capture metric.")
    payload = {
        "_aws": {
            "Timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
            "CloudWatchMetrics": [{
                "Namespace": "LifeLedger/Capture",
                "Dimensions": [["Result"]],
                "Metrics": [{"Name": name, "Unit": unit}],
            }],
        },
        "Result": result,
        name: value,
        "capture_id": capture_id,
        "proposal_id": proposal_id,
        "correlation_id": correlation_id,
        "model": model,
        "action_type": action_type,
    }
    logger.info(json.dumps({key: value for key, value in payload.items() if value is not None}))
