from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas import (
    MaintenanceArea,
    MaintenanceIntervalUnit,
    PriorityOption,
    RecordType,
    RelationshipType,
    ReminderCategory,
    ReminderLeadUnit,
    ReminderType,
    RenewalKind,
    RepeatOption,
)


SCHEMA_VERSION = 1
ACTION_SCHEMA_VERSION = 1
INTERPRETATION_VERSION = "capture-v1"
PROMPT_VERSION = "capture-openai-v1"


class CaptureSource(StrEnum):
    LIFELEDGER_WEB = "lifeledger_web"
    FUTURE_SHORTCUT = "future_shortcut"
    FUTURE_CHATGPT = "future_chatgpt"
    FUTURE_SHARE_SHEET = "future_share_sheet"
    MANUAL = "manual"


class CaptureInputType(StrEnum):
    TEXT = "text"


class CaptureStatus(StrEnum):
    NEW = "new"
    INTERPRETING = "interpreting"
    NEEDS_CLARIFICATION = "needs_clarification"
    READY_FOR_REVIEW = "ready_for_review"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    DISMISSED = "dismissed"


class InterpreterKind(StrEnum):
    DETERMINISTIC = "deterministic"
    OPENAI = "openai"
    MOCK = "mock"
    DISABLED = "disabled"
    MANUAL = "manual"


class CaptureFailureCategory(StrEnum):
    AI_DISABLED = "ai_disabled"
    BUDGET_DENIED = "budget_denied"
    PROVIDER_TIMEOUT = "provider_timeout"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    INVALID_PROVIDER_OUTPUT = "invalid_provider_output"
    UNSUPPORTED = "unsupported"
    EXECUTION_FAILED = "execution_failed"


class ActionType(StrEnum):
    CREATE_ITEM = "create_item"
    UPDATE_ITEM_DETAIL = "update_item_detail"
    CREATE_RESPONSIBILITY = "create_responsibility"
    COMPLETE_RESPONSIBILITY = "complete_responsibility"
    RENEW_RESPONSIBILITY = "renew_responsibility"
    SNOOZE_RESPONSIBILITY = "snooze_responsibility"
    CREATE_RELATIONSHIP = "create_relationship"
    ADD_SAFE_NOTE = "add_safe_note"
    REQUEST_CLARIFICATION = "request_clarification"
    NO_ACTION = "no_action"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ConfirmationRequirement(StrEnum):
    ALWAYS = "always"
    CLARIFICATION = "clarification"
    PROHIBITED = "prohibited"


class ProposalStatus(StrEnum):
    DRAFT = "draft"
    NEEDS_CLARIFICATION = "needs_clarification"
    READY_FOR_REVIEW = "ready_for_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTING = "executing"
    PARTIALLY_COMPLETED = "partially_completed"
    COMPLETED = "completed"
    EXPIRED = "expired"
    FAILED = "failed"


class ClarificationStatus(StrEnum):
    OPEN = "open"
    ANSWERED = "answered"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class ActionResultStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    PROHIBITED = "prohibited"


class ConfidenceCategory(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ProviderErrorCategory(StrEnum):
    DISABLED = "disabled"
    BUDGET_DENIED = "budget_denied"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    AUTHENTICATION = "authentication"
    UNAVAILABLE = "unavailable"
    INVALID_OUTPUT = "invalid_output"
    REFUSAL = "refusal"


class Capture(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capture_id: str
    user_id: str
    source: CaptureSource = CaptureSource.LIFELEDGER_WEB
    input_type: CaptureInputType = CaptureInputType.TEXT
    original_text: str = Field(min_length=1, max_length=4_000)
    captured_at: datetime
    client_timestamp: datetime | None = None
    timezone: str = Field(default="UTC", min_length=1, max_length=100)
    locale: str = Field(default="en-US", min_length=2, max_length=40)
    status: CaptureStatus = CaptureStatus.NEW
    interpreter: InterpreterKind | None = None
    interpretation_version: str | None = None
    active_proposal_id: str | None = None
    clarification_session_id: str | None = None
    interpretation_summary: str | None = Field(default=None, max_length=500)
    relevant_action: str | None = Field(default=None, max_length=240)
    failure_category: CaptureFailureCategory | None = None
    safe_failure_message: str | None = Field(default=None, max_length=240)
    attempt_count: int = Field(default=0, ge=0)
    idempotency_key: str = Field(min_length=8, max_length=200)
    correlation_id: str = Field(min_length=8, max_length=200)
    created_at: datetime
    updated_at: datetime
    retention_expires_at: datetime | None = None
    schema_version: int = SCHEMA_VERSION

    @field_validator("original_text", mode="before")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value


class EntityCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_type: str
    entity_id: str
    display_title: str = Field(max_length=120)
    item_type: RecordType | None = None
    safe_aliases: list[str] = Field(default_factory=list, max_length=10)
    relationship_context: str | None = Field(default=None, max_length=80)
    relevant_responsibility_id: str | None = None
    relevant_responsibility_title: str | None = Field(default=None, max_length=120)
    relevant_dates: dict[str, date] = Field(default_factory=dict)
    match_reasons: list[str] = Field(default_factory=list, max_length=6)
    score: int = Field(default=0, ge=0, le=100)


class CreateItemFields(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=120)
    details: dict[str, str | float | bool | None] = Field(default_factory=dict)


class UpdateItemDetailFields(BaseModel):
    model_config = ConfigDict(extra="forbid")
    detail_key: str = Field(min_length=1, max_length=80)
    value: str | float | bool | None


class BirthdayActionDetails(BaseModel):
    model_config = ConfigDict(extra="forbid")
    person_name: str = Field(min_length=1, max_length=120)
    birth_month: int = Field(ge=1, le=12)
    birth_day: int = Field(ge=1, le=31)
    birth_year: int | None = Field(default=None, ge=1, le=9999)
    relationship: str | None = Field(default=None, max_length=80)


class RenewalActionDetails(BaseModel):
    model_config = ConfigDict(extra="forbid")
    item_name: str = Field(min_length=1, max_length=120)
    renewal_kind: RenewalKind = RenewalKind.RENEWAL
    owner_name: str | None = Field(default=None, max_length=120)
    provider: str | None = Field(default=None, max_length=120)
    renewal_date: date | None = None
    expiration_date: date | None = None
    renewal_window_days: int | None = Field(default=None, ge=0, le=365)
    review_lead_days: int | None = Field(default=None, ge=0, le=365)
    frequency: str | None = Field(default=None, max_length=80)


class MaintenanceActionDetails(BaseModel):
    model_config = ConfigDict(extra="forbid")
    item_name: str = Field(min_length=1, max_length=120)
    maintenance_area: MaintenanceArea = MaintenanceArea.OTHER
    last_completed_date: date | None = None
    interval_value: int | None = Field(default=None, ge=1, le=365)
    interval_unit: MaintenanceIntervalUnit | None = None
    next_due_date: date | None = None
    instructions: str | None = Field(default=None, max_length=1000)


class CreateResponsibilityFields(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=120)
    category: ReminderCategory = ReminderCategory.OTHER
    due_date: date
    repeat: RepeatOption = RepeatOption.NONE
    priority: PriorityOption = PriorityOption.MEDIUM
    notes: str | None = Field(default=None, max_length=1000)
    reminder_lead_value: int | None = Field(default=None, ge=0, le=36)
    reminder_lead_unit: ReminderLeadUnit | None = None
    reminder_time: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    reminder_type: ReminderType = ReminderType.GENERIC
    birthday_details: BirthdayActionDetails | None = None
    renewal_details: RenewalActionDetails | None = None
    maintenance_details: MaintenanceActionDetails | None = None

    @model_validator(mode="after")
    def validate_details(self) -> "CreateResponsibilityFields":
        expected = {
            ReminderType.BIRTHDAY: self.birthday_details,
            ReminderType.RENEWAL: self.renewal_details,
            ReminderType.MAINTENANCE: self.maintenance_details,
        }
        required = expected.get(self.reminder_type)
        if self.reminder_type != ReminderType.GENERIC and required is None:
            raise ValueError(f"{self.reminder_type.value} responsibility details are required")
        if self.reminder_type != ReminderType.BIRTHDAY and self.birthday_details is not None:
            raise ValueError("birthday_details are only valid for birthday responsibilities")
        if self.reminder_type != ReminderType.RENEWAL and self.renewal_details is not None:
            raise ValueError("renewal_details are only valid for renewal responsibilities")
        if self.reminder_type != ReminderType.MAINTENANCE and self.maintenance_details is not None:
            raise ValueError("maintenance_details are only valid for maintenance responsibilities")
        return self


class CompleteResponsibilityFields(BaseModel):
    model_config = ConfigDict(extra="forbid")
    completed_on: date | None = None
    note: str | None = Field(default=None, max_length=500)


class RenewResponsibilityFields(BaseModel):
    model_config = ConfigDict(extra="forbid")
    new_due_date: date
    renewed_on: date | None = None
    note: str | None = Field(default=None, max_length=500)


class SnoozeResponsibilityFields(BaseModel):
    model_config = ConfigDict(extra="forbid")
    snoozed_until: datetime


class CreateRelationshipFields(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_entity_type: str
    source_entity_id: str | None = None
    target_entity_type: str
    target_entity_id: str | None = None
    relationship_type: RelationshipType = RelationshipType.RELATED
    custom_label: str | None = Field(default=None, max_length=40)


class AddSafeNoteFields(BaseModel):
    model_config = ConfigDict(extra="forbid")
    note: str = Field(min_length=1, max_length=500)


class RequestClarificationFields(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=240)


class NoActionFields(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=1, max_length=240)


ACTION_FIELD_MODELS: dict[ActionType, type[BaseModel]] = {
    ActionType.CREATE_ITEM: CreateItemFields,
    ActionType.UPDATE_ITEM_DETAIL: UpdateItemDetailFields,
    ActionType.CREATE_RESPONSIBILITY: CreateResponsibilityFields,
    ActionType.COMPLETE_RESPONSIBILITY: CompleteResponsibilityFields,
    ActionType.RENEW_RESPONSIBILITY: RenewResponsibilityFields,
    ActionType.SNOOZE_RESPONSIBILITY: SnoozeResponsibilityFields,
    ActionType.CREATE_RELATIONSHIP: CreateRelationshipFields,
    ActionType.ADD_SAFE_NOTE: AddSafeNoteFields,
    ActionType.REQUEST_CLARIFICATION: RequestClarificationFields,
    ActionType.NO_ACTION: NoActionFields,
}


class ActionSeed(BaseModel):
    """Untrusted interpreter output before LifeLedger assigns policy and identity."""

    model_config = ConfigDict(extra="forbid")
    action_type: ActionType
    target_item_id: str | None = None
    target_responsibility_id: str | None = None
    target_item_action_index: int | None = Field(default=None, ge=0, le=20)
    item_type: RecordType | None = None
    fields: dict[str, Any] = Field(default_factory=dict)
    explanation: str = Field(min_length=1, max_length=240)

    @model_validator(mode="after")
    def validate_action_fields(self) -> "ActionSeed":
        model = ACTION_FIELD_MODELS[self.action_type].model_validate(self.fields)
        self.fields = model.model_dump(mode="json", exclude_none=True)
        if self.action_type == ActionType.CREATE_ITEM and self.item_type is None:
            raise ValueError("create_item requires item_type")
        return self


class ProposedAction(ActionSeed):
    action_id: str
    source_capture_id: str
    risk_level: RiskLevel
    confirmation_requirement: ConfirmationRequirement
    idempotency_key: str = Field(min_length=8, max_length=200)
    schema_version: int = ACTION_SCHEMA_VERSION


class ActionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    proposal_id: str
    action_id: str
    action_type: ActionType
    status: ActionResultStatus
    resulting_entity_id: str | None = None
    safe_summary: str = Field(max_length=240)
    executed_at: datetime | None = None
    idempotent_replay: bool = False
    reconciliation_required: bool = False
    correction_available: bool = True


class ActionProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    proposal_id: str
    user_id: str
    capture_id: str
    status: ProposalStatus
    proposed_actions: list[ProposedAction] = Field(default_factory=list, max_length=12)
    action_results: list[ActionResult] = Field(default_factory=list, max_length=12)
    entity_candidates: list[EntityCandidate] = Field(default_factory=list, max_length=20)
    ambiguity_reasons: list[str] = Field(default_factory=list, max_length=10)
    conflict_warnings: list[str] = Field(default_factory=list, max_length=10)
    missing_information: list[str] = Field(default_factory=list, max_length=10)
    user_facing_summary: str = Field(min_length=1, max_length=500)
    interpreter: InterpreterKind
    model_name: str | None = Field(default=None, max_length=120)
    prompt_version: str | None = Field(default=None, max_length=80)
    structured_output_version: str = INTERPRETATION_VERSION
    expires_at: datetime
    approved_at: datetime | None = None
    rejected_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    schema_version: int = SCHEMA_VERSION


class ClarificationOption(BaseModel):
    model_config = ConfigDict(extra="forbid")
    option_id: str
    label: str = Field(min_length=1, max_length=120)


class ClarificationQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question_id: str
    prompt: str = Field(min_length=1, max_length=240)
    options: list[ClarificationOption] = Field(default_factory=list, max_length=10)
    allow_free_text: bool = False
    action_id: str | None = None
    target_field: str | None = None


class ClarificationSession(BaseModel):
    model_config = ConfigDict(extra="forbid")
    clarification_id: str
    user_id: str
    capture_id: str
    proposal_id: str
    questions: list[ClarificationQuestion] = Field(min_length=1, max_length=5)
    answers: dict[str, str] = Field(default_factory=dict)
    status: ClarificationStatus = ClarificationStatus.OPEN
    expires_at: datetime
    created_at: datetime
    updated_at: datetime
    schema_version: int = SCHEMA_VERSION


class StructuredInterpretation(BaseModel):
    """Strict provider output. Every value is still revalidated and policy-owned."""

    model_config = ConfigDict(extra="forbid")
    supported: bool
    confidence: ConfidenceCategory
    summary: str = Field(min_length=1, max_length=500)
    actions: list[ActionSeed] = Field(default_factory=list, max_length=12)
    ambiguity_reasons: list[str] = Field(default_factory=list, max_length=10)
    conflict_warnings: list[str] = Field(default_factory=list, max_length=10)
    missing_information: list[str] = Field(default_factory=list, max_length=10)


class AIUsageRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    usage_id: str
    provider_request_id: str
    user_id: str
    capture_id: str
    provider: str
    model: str
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0)
    timestamp: datetime
    result_category: str = Field(max_length=80)
    billing_month: str = Field(pattern=r"^\d{4}-\d{2}$")
    billing_day: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    schema_version: int = SCHEMA_VERSION


class AISettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: str
    ai_enabled: bool = True
    monthly_budget_usd: float = Field(default=5.0, ge=0, le=100)
    daily_request_limit: int = Field(default=50, ge=1, le=500)
    deterministic_first: bool = True
    allow_model_escalation: bool = True
    updated_at: datetime
    schema_version: int = SCHEMA_VERSION


class CaptureCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    original_text: str = Field(min_length=1, max_length=4_000)
    client_timestamp: datetime | None = None
    timezone: str = Field(default="UTC", min_length=1, max_length=100)
    locale: str = Field(default="en-US", min_length=2, max_length=40)
    source: CaptureSource = CaptureSource.LIFELEDGER_WEB

    @field_validator("original_text", mode="before")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value


class CapturePage(BaseModel):
    items: list[Capture]
    next_cursor: str | None = None


class CaptureDetailResponse(BaseModel):
    capture: Capture
    proposal: ActionProposal | None = None
    clarification: ClarificationSession | None = None


class ClarificationAnswerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answers: dict[str, str] = Field(min_length=1, max_length=5)


class ProposalActionEditRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action_id: str = Field(min_length=1, max_length=200)
    changes: dict[str, Any] = Field(min_length=1, max_length=20)


class AISettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ai_enabled: bool | None = None
    monthly_budget_usd: float | None = Field(default=None, ge=0, le=100)
    daily_request_limit: int | None = Field(default=None, ge=1, le=500)
    deterministic_first: bool | None = None
    allow_model_escalation: bool | None = None


class AIUsageSummary(BaseModel):
    billing_month: str
    estimated_cost_usd: float
    input_tokens: int
    output_tokens: int
    request_count: int
    monthly_budget_usd: float
    remaining_budget_usd: float
    daily_request_count: int
    daily_request_limit: int


class AISettingsResponse(BaseModel):
    settings: AISettings
    usage: AIUsageSummary
    provider_configured: bool
    default_model: str
    escalation_model: str | None
