from __future__ import annotations

from dataclasses import dataclass

from app.capture_models import (
    ActionSeed,
    ActionType,
    ConfirmationRequirement,
    RiskLevel,
)
from app.item_service import ITEM_DETAIL_SPECS


PROTECTED_OR_DESTRUCTIVE_KEYS = {
    "document_number",
    "license_number",
    "vin",
    "policy_number",
    "member_number",
    "serial_number",
    "account_reference",
    "sensitive_notes",
    "license_plate",
    "microchip",
    "password",
    "authentication_code",
    "payment_card",
    "passport_number",
}


@dataclass(frozen=True)
class PolicyDecision:
    risk_level: RiskLevel
    confirmation_requirement: ConfirmationRequirement
    requires_clarification: bool
    prohibited: bool
    reauthentication_required: bool
    groupable: bool
    safe_reason: str | None = None


class ActionPolicyService:
    """Deterministic policy. Model confidence and suggested risk never authorize writes."""

    def evaluate(self, action: ActionSeed, *, has_conflict: bool = False) -> PolicyDecision:
        prohibited_reason = self._prohibited_reason(action)
        if prohibited_reason:
            return PolicyDecision(
                risk_level=RiskLevel.HIGH,
                confirmation_requirement=ConfirmationRequirement.PROHIBITED,
                requires_clarification=False,
                prohibited=True,
                reauthentication_required=False,
                groupable=False,
                safe_reason=prohibited_reason,
            )
        missing_target = self._missing_target(action)
        if has_conflict:
            return PolicyDecision(
                risk_level=RiskLevel.HIGH,
                confirmation_requirement=ConfirmationRequirement.PROHIBITED,
                requires_clarification=False,
                prohibited=True,
                reauthentication_required=False,
                groupable=False,
                safe_reason="Existing information conflicts with this proposal. Use the normal item editor to review it.",
            )
        if missing_target:
            return PolicyDecision(
                risk_level=self._risk(action),
                confirmation_requirement=ConfirmationRequirement.CLARIFICATION,
                requires_clarification=True,
                prohibited=False,
                reauthentication_required=False,
                groupable=False,
                safe_reason=missing_target,
            )
        return PolicyDecision(
            risk_level=self._risk(action),
            confirmation_requirement=ConfirmationRequirement.ALWAYS,
            requires_clarification=False,
            prohibited=False,
            reauthentication_required=False,
            groupable=action.action_type not in {ActionType.REQUEST_CLARIFICATION, ActionType.NO_ACTION},
        )

    @staticmethod
    def _risk(action: ActionSeed) -> RiskLevel:
        if action.action_type in {
            ActionType.COMPLETE_RESPONSIBILITY,
            ActionType.SNOOZE_RESPONSIBILITY,
            ActionType.ADD_SAFE_NOTE,
            ActionType.REQUEST_CLARIFICATION,
            ActionType.NO_ACTION,
        }:
            return RiskLevel.LOW
        return RiskLevel.MEDIUM

    @staticmethod
    def _missing_target(action: ActionSeed) -> str | None:
        if action.action_type in {ActionType.UPDATE_ITEM_DETAIL, ActionType.ADD_SAFE_NOTE}:
            if not action.target_item_id and action.target_item_action_index is None:
                return "The target item needs clarification."
        if action.action_type in {
            ActionType.COMPLETE_RESPONSIBILITY,
            ActionType.RENEW_RESPONSIBILITY,
            ActionType.SNOOZE_RESPONSIBILITY,
        } and not action.target_responsibility_id:
            return "The target responsibility needs clarification."
        return None

    @staticmethod
    def _prohibited_reason(action: ActionSeed) -> str | None:
        if action.action_type == ActionType.UPDATE_ITEM_DETAIL:
            key = str(action.fields.get("detail_key") or "").casefold()
            if key in PROTECTED_OR_DESTRUCTIVE_KEYS:
                return "Protected details cannot be changed through natural-language capture."
            if action.item_type is not None and key not in ITEM_DETAIL_SPECS.get(action.item_type, {}):
                return "This detail is not supported for the selected item type."
        if action.action_type == ActionType.CREATE_ITEM:
            if action.item_type is None:
                return "An item type is required."
            details = action.fields.get("details") or {}
            allowed = ITEM_DETAIL_SPECS.get(action.item_type, {})
            for key in details:
                if key == "notes":
                    continue
                if key.casefold() in PROTECTED_OR_DESTRUCTIVE_KEYS or key not in allowed:
                    return "The proposal contains an unsupported or protected item detail."
        if action.action_type == ActionType.CREATE_RELATIONSHIP:
            relationship_type = str(action.fields.get("relationship_type") or "")
            if relationship_type in {"owned_by", "covers", "insures"}:
                return "Consequential relationship changes are not available through capture."
        return None
