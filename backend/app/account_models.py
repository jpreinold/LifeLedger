from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class AccountState(StrEnum):
    ACTIVE = "active"
    EXPORT_PENDING = "export_pending"
    DELETION_REQUESTED = "deletion_requested"
    DELETING = "deleting"
    DELETION_REQUIRES_ATTENTION = "deletion_requires_attention"
    DELETED = "deleted"


class AccountOperationType(StrEnum):
    EXPORT = "export"
    DELETION = "deletion"


class AccountOperationStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    FAILED = "failed"
    EXPIRED = "expired"


class AccountStepStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    FAILED = "failed"


class AccountLifecycle(BaseModel):
    user_id: str
    state: AccountState = AccountState.ACTIVE
    current_operation_id: str | None = None
    updated_at: datetime
    schema_version: int = 1


class AccountOperationStep(BaseModel):
    name: str
    status: AccountStepStatus = AccountStepStatus.PENDING
    attempt_count: int = 0
    retryable: bool = True
    safe_error: str | None = None
    updated_at: datetime


class AccountOperation(BaseModel):
    operation_id: str
    user_id: str
    operation_type: AccountOperationType
    status: AccountOperationStatus = AccountOperationStatus.PENDING
    include_protected_details: bool = False
    created_at: datetime
    updated_at: datetime
    expires_at: datetime | None = None
    artifact_key: str | None = None
    artifact_size_bytes: int | None = None
    steps: list[AccountOperationStep] = Field(default_factory=list)
    safe_error: str | None = None
    retryable: bool = True
    schema_version: int = 1


class AccountExportManifest(BaseModel):
    schema_version: int = 1
    export_id: str
    generated_at: datetime
    include_protected_details: bool
    stores: dict[str, int]
    documents_included: int = 0


class AccountDeletionVerification(BaseModel):
    operation_id: str
    complete: bool
    counts: dict[str, int]
    checked_at: datetime
