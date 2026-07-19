from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json

from app.capture_models import AISettings, AIUsageRecord, AIUsageSummary
from app.capture_repository import AssistantRepository
from app.config import Settings


class AIBudgetDenied(ValueError):
    pass


class AIUsageService:
    def __init__(self, repository: AssistantRepository, settings: Settings):
        self.repository = repository
        self.settings = settings

    def get_settings(self, user_id: str, *, now: datetime | None = None) -> AISettings:
        existing = self.repository.get_ai_settings(user_id)
        if existing is not None:
            return existing
        return AISettings(
            user_id=user_id,
            monthly_budget_usd=self.settings.ai_default_monthly_budget_usd,
            daily_request_limit=self.settings.ai_default_daily_request_limit,
            updated_at=_utc(now),
        )

    def save_settings(self, value: AISettings) -> AISettings:
        return self.repository.save_ai_settings(value)

    def summary(self, user_id: str, *, now: datetime | None = None) -> AIUsageSummary:
        current = _utc(now)
        user_settings = self.get_settings(user_id, now=current)
        month = current.strftime("%Y-%m")
        day = current.strftime("%Y-%m-%d")
        month_records = self.repository.list_usage(user_id, month)
        day_count = sum(1 for item in month_records if item.billing_day == day)
        cost = round(sum(item.estimated_cost_usd for item in month_records), 6)
        return AIUsageSummary(
            billing_month=month,
            estimated_cost_usd=cost,
            input_tokens=sum(item.input_tokens for item in month_records),
            output_tokens=sum(item.output_tokens for item in month_records),
            request_count=len(month_records),
            monthly_budget_usd=user_settings.monthly_budget_usd,
            remaining_budget_usd=round(max(0.0, user_settings.monthly_budget_usd - cost), 6),
            daily_request_count=day_count,
            daily_request_limit=user_settings.daily_request_limit,
        )

    def assert_available(
        self,
        user_id: str,
        *,
        estimated_input_tokens: int,
        now: datetime | None = None,
    ) -> None:
        user_settings = self.get_settings(user_id, now=now)
        if self.settings.ai_emergency_disabled or not user_settings.ai_enabled:
            raise AIBudgetDenied("AI-assisted interpretation is disabled.")
        if estimated_input_tokens > self.settings.ai_input_token_limit:
            raise AIBudgetDenied("Capture exceeds the AI input limit.")
        usage = self.summary(user_id, now=now)
        if usage.estimated_cost_usd >= user_settings.monthly_budget_usd:
            raise AIBudgetDenied("Monthly AI budget has been reached.")
        if usage.daily_request_count >= user_settings.daily_request_limit:
            raise AIBudgetDenied("Daily AI request limit has been reached.")

    def record(
        self,
        *,
        provider_request_id: str,
        user_id: str,
        capture_id: str,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        result_category: str,
        now: datetime | None = None,
    ) -> tuple[AIUsageRecord, bool]:
        current = _utc(now)
        usage_id = hashlib.sha256(f"{user_id}\x1f{provider_request_id}".encode()).hexdigest()
        record = AIUsageRecord(
            usage_id=usage_id,
            provider_request_id=provider_request_id,
            user_id=user_id,
            capture_id=capture_id,
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=self.estimate_cost(model, input_tokens, output_tokens),
            timestamp=current,
            result_category=result_category,
            billing_month=current.strftime("%Y-%m"),
            billing_day=current.strftime("%Y-%m-%d"),
        )
        return self.repository.record_usage_once(record)

    def estimate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        try:
            pricing = json.loads(self.settings.ai_model_pricing_json)
            rates = pricing[model]
            input_rate = float(rates["input"])
            output_rate = float(rates["output"])
        except Exception:
            return 0.0
        return round((input_tokens * input_rate + output_tokens * output_rate) / 1_000_000, 8)


def estimate_tokens(value: str) -> int:
    # A conservative local estimate used only for the pre-call budget gate.
    return max(1, (len(value.encode("utf-8")) + 2) // 3)


def _utc(value: datetime | None) -> datetime:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None:
        return current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc)
