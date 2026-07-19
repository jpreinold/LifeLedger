from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class ReconciliationStatus(StrEnum):
    PENDING = "pending"
    RETRYING = "retrying"
    RESOLVED = "resolved"
    REQUIRES_ATTENTION = "requires_attention"
    IGNORED = "ignored"


class ReconciliationDomain(StrEnum):
    SEARCH = "search"
    LIFECYCLE = "lifecycle"
    ITEM_SYNC = "item_sync"
    DOCUMENT = "document"
    RELATIONSHIP = "relationship"
    ACCOUNT_DELETION = "account_deletion"
    WORKFLOW = "workflow"


class ReconciliationSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ReconciliationIssue(BaseModel):
    reconciliation_id: str
    user_id: str
    domain: ReconciliationDomain
    entity_type: str = Field(min_length=1, max_length=80)
    entity_id: str = Field(min_length=1, max_length=200)
    issue_type: str = Field(min_length=1, max_length=100)
    detected_at: datetime
    last_attempt_at: datetime | None = None
    attempt_count: int = 0
    status: ReconciliationStatus = ReconciliationStatus.PENDING
    severity: ReconciliationSeverity = ReconciliationSeverity.MEDIUM
    retryable: bool = True
    next_retry_at: datetime | None = None
    correlation_id: str
    safe_summary: str = Field(max_length=240)
    resolution: str | None = Field(default=None, max_length=240)
    resolved_at: datetime | None = None
    expires_at: int | None = None
    schema_version: int = 1


class ReconciliationBatchResult(BaseModel):
    considered: int
    attempted: int
    resolved: int
    failed: int
    requires_attention: int
    dry_run: bool = False
