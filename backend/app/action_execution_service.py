from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from app.action_policy_service import ActionPolicyService
from app.capture_models import (
    ActionProposal,
    ActionResult,
    ActionResultStatus,
    ActionType,
    CaptureFailureCategory,
    CaptureStatus,
    ConfirmationRequirement,
    ProposalStatus,
)
from app.capture_repository import AssistantRepository
from app.capture_observability import emit_capture_metric
from app.item_service import ItemApplicationService, ItemNotFound
from app.reconciliation import ReconciliationDomain, ReconciliationSeverity
from app.reconciliation_service import ReconciliationService
from app.responsibility_service import RelationshipApplicationService, ResponsibilityApplicationService
from app.schemas import LinkedEntityType, RelationshipType


class ProposalExecutionConflict(ValueError):
    pass


class ActionExecutionService:
    def __init__(
        self,
        repository: AssistantRepository,
        items: ItemApplicationService,
        responsibilities: ResponsibilityApplicationService,
        relationships: RelationshipApplicationService,
        policy: ActionPolicyService,
        reconciliation: ReconciliationService,
    ):
        self.repository = repository
        self.items = items
        self.responsibilities = responsibilities
        self.relationships = relationships
        self.policy = policy
        self.reconciliation = reconciliation

    def approve_and_execute(
        self, user_id: str, proposal_id: str, *, now: datetime | None = None
    ) -> ActionProposal:
        current = _utc(now)
        proposal = self.repository.get_proposal(user_id, proposal_id)
        if proposal is None:
            raise KeyError("Proposal not found.")
        if proposal.status == ProposalStatus.COMPLETED:
            return proposal
        if proposal.status == ProposalStatus.REJECTED:
            raise ProposalExecutionConflict("Rejected proposals cannot execute.")
        if proposal.expires_at <= current:
            expired = proposal.model_copy(update={"status": ProposalStatus.EXPIRED, "updated_at": current})
            self.repository.save_proposal(expired)
            raise ProposalExecutionConflict("This proposal has expired. Reinterpret the capture before approving it.")
        if proposal.status == ProposalStatus.NEEDS_CLARIFICATION:
            raise ProposalExecutionConflict("Answer the clarification before approving this proposal.")
        if proposal.status not in {
            ProposalStatus.READY_FOR_REVIEW,
            ProposalStatus.FAILED,
            ProposalStatus.PARTIALLY_COMPLETED,
        }:
            raise ProposalExecutionConflict("This proposal is not ready for approval.")
        if any(
            action.confirmation_requirement == ConfirmationRequirement.PROHIBITED
            for action in proposal.proposed_actions
        ):
            raise ProposalExecutionConflict("This proposal contains an action that cannot run through capture.")

        capture = self.repository.get_capture(user_id, proposal.capture_id)
        if capture is None:
            raise ProposalExecutionConflict("The source capture is unavailable.")
        proposal = proposal.model_copy(
            update={"status": ProposalStatus.EXECUTING, "approved_at": proposal.approved_at or current, "updated_at": current}
        )
        capture = capture.model_copy(update={"status": CaptureStatus.EXECUTING, "updated_at": current})
        self.repository.save_proposal(proposal)
        self.repository.save_capture(capture)
        emit_capture_metric("Approved", capture_id=capture.capture_id, proposal_id=proposal.proposal_id, correlation_id=capture.correlation_id)

        results = {item.action_id: item for item in proposal.action_results}
        ordered = sorted(proposal.proposed_actions, key=_action_order)
        for action in ordered:
            previous = results.get(action.action_id)
            if previous and previous.status == ActionResultStatus.COMPLETED:
                continue
            decision = self.policy.evaluate(action, has_conflict=self._has_current_value_conflict(user_id, action))
            if decision.prohibited or action.confirmation_requirement == ConfirmationRequirement.PROHIBITED:
                result = ActionResult(
                    proposal_id=proposal.proposal_id,
                    action_id=action.action_id,
                    action_type=action.action_type,
                    status=ActionResultStatus.PROHIBITED,
                    safe_summary=decision.safe_reason or "This action is not available through capture.",
                    executed_at=current,
                    correction_available=True,
                )
            elif decision.requires_clarification:
                result = ActionResult(
                    proposal_id=proposal.proposal_id,
                    action_id=action.action_id,
                    action_type=action.action_type,
                    status=ActionResultStatus.FAILED,
                    safe_summary=decision.safe_reason or "This action still needs clarification.",
                    executed_at=current,
                    correction_available=True,
                )
            else:
                try:
                    result = self._execute_one(user_id, proposal, action, results, current)
                except Exception:
                    self.reconciliation.detect(
                        user_id=user_id,
                        domain=ReconciliationDomain.CAPTURE,
                        entity_type="proposal",
                        entity_id=proposal.proposal_id,
                        issue_type="partial_action_execution",
                        severity=ReconciliationSeverity.HIGH,
                        retryable=True,
                        correlation_id=capture.correlation_id,
                        now=current,
                    )
                    result = ActionResult(
                        proposal_id=proposal.proposal_id,
                        action_id=action.action_id,
                        action_type=action.action_type,
                        status=ActionResultStatus.FAILED,
                        safe_summary="LifeLedger could not complete this action safely. You can retry it from the Inbox.",
                        executed_at=current,
                        reconciliation_required=True,
                        correction_available=True,
                    )
            results[action.action_id] = result
            proposal = proposal.model_copy(update={"action_results": list(results.values()), "updated_at": current})
            self.repository.save_proposal(proposal)
            if result.status != ActionResultStatus.COMPLETED:
                break

        completed = sum(item.status == ActionResultStatus.COMPLETED for item in results.values())
        all_completed = len(results) == len(proposal.proposed_actions) and all(
            item.status == ActionResultStatus.COMPLETED for item in results.values()
        )
        if all_completed:
            proposal_status = ProposalStatus.COMPLETED
            capture_status = CaptureStatus.COMPLETED
            failure_category = None
            failure_message = None
        elif completed:
            proposal_status = ProposalStatus.PARTIALLY_COMPLETED
            capture_status = CaptureStatus.FAILED
            failure_category = CaptureFailureCategory.EXECUTION_FAILED
            failure_message = "Some approved changes were saved. Review the remaining action before retrying."
        else:
            proposal_status = ProposalStatus.FAILED
            capture_status = CaptureStatus.FAILED
            failure_category = CaptureFailureCategory.EXECUTION_FAILED
            failure_message = "LifeLedger could not complete the approved changes safely."
        proposal = proposal.model_copy(update={"status": proposal_status, "action_results": list(results.values()), "updated_at": current})
        capture = capture.model_copy(
            update={
                "status": capture_status,
                "failure_category": failure_category,
                "safe_failure_message": failure_message,
                "retention_expires_at": current + timedelta(days=90) if capture_status == CaptureStatus.COMPLETED else None,
                "updated_at": current,
            }
        )
        self.repository.save_proposal(proposal)
        self.repository.save_capture(capture)
        emit_capture_metric(
            "Completed" if all_completed else "PartiallyCompleted" if completed else "Failed",
            capture_id=capture.capture_id,
            proposal_id=proposal.proposal_id,
            correlation_id=capture.correlation_id,
            result=proposal_status.value,
        )
        return proposal

    def _execute_one(self, user_id, proposal, action, results, now) -> ActionResult:
        item_id = self._target_item_id(proposal, action, results)
        resulting_id = None
        replay = False
        summary = "Action completed."
        if action.action_type == ActionType.CREATE_ITEM:
            item, replay = self.items.create_item(
                user_id=user_id,
                item_type=action.item_type,
                title=action.fields["title"],
                details=action.fields.get("details", {}),
                idempotency_key=action.idempotency_key,
                now=now,
            )
            resulting_id = item.id
            summary = f"Created {item.title}."
        elif action.action_type == ActionType.UPDATE_ITEM_DETAIL:
            item, replay = self.items.update_normal_detail(
                user_id=user_id,
                item_id=item_id,
                detail_key=action.fields["detail_key"],
                value=action.fields.get("value"),
                now=now,
            )
            resulting_id = item.id
            summary = f"Updated {item.title}."
        elif action.action_type == ActionType.ADD_SAFE_NOTE:
            item, replay = self.items.add_safe_note(
                user_id=user_id, item_id=item_id, note=action.fields["note"], now=now
            )
            resulting_id = item.id
            summary = f"Added a note to {item.title}."
        elif action.action_type == ActionType.CREATE_RESPONSIBILITY:
            result = self.responsibilities.create(
                user_id=user_id,
                fields=action.fields,
                item_id=item_id,
                idempotency_key=action.idempotency_key,
                now=now,
            )
            resulting_id, replay = result.reminder.id, result.idempotent_replay
            summary = f"Created {result.reminder.title}."
        elif action.action_type == ActionType.COMPLETE_RESPONSIBILITY:
            result = self.responsibilities.complete(
                user_id=user_id,
                reminder_id=action.target_responsibility_id,
                fields=action.fields,
                idempotency_key=action.idempotency_key,
                now=now,
            )
            resulting_id, replay = result.reminder.id, result.idempotent_replay
            summary = f"Completed {result.reminder.title}."
        elif action.action_type == ActionType.RENEW_RESPONSIBILITY:
            result = self.responsibilities.renew(
                user_id=user_id,
                reminder_id=action.target_responsibility_id,
                fields=action.fields,
                idempotency_key=action.idempotency_key,
                now=now,
            )
            resulting_id, replay = result.reminder.id, result.idempotent_replay
            summary = f"Renewed {result.reminder.title}."
        elif action.action_type == ActionType.SNOOZE_RESPONSIBILITY:
            result = self.responsibilities.snooze(
                user_id=user_id,
                reminder_id=action.target_responsibility_id,
                snoozed_until=datetime.fromisoformat(action.fields["snoozed_until"]),
                idempotency_key=action.idempotency_key,
                now=now,
            )
            resulting_id, replay = result.reminder.id, result.idempotent_replay
            summary = f"Snoozed {result.reminder.title}."
        elif action.action_type == ActionType.CREATE_RELATIONSHIP:
            fields = action.fields
            source_type, source_id = _relationship_endpoint(
                fields["source_entity_type"], fields.get("source_entity_id") or item_id
            )
            target_type, target_id = _relationship_endpoint(
                fields["target_entity_type"], fields.get("target_entity_id")
            )
            link, replay = self.relationships.create(
                user_id=user_id,
                source_type=source_type,
                source_id=source_id,
                target_type=target_type,
                target_id=target_id,
                relationship_type=RelationshipType(fields.get("relationship_type", "related")),
                label=fields.get("custom_label"),
                idempotency_key=action.idempotency_key,
                now=now,
            )
            resulting_id = link.link_id
            summary = "Created the relationship."
        elif action.action_type in {ActionType.REQUEST_CLARIFICATION, ActionType.NO_ACTION}:
            summary = action.explanation
        return ActionResult(
            proposal_id=proposal.proposal_id,
            action_id=action.action_id,
            action_type=action.action_type,
            status=ActionResultStatus.COMPLETED,
            resulting_entity_id=resulting_id,
            safe_summary=summary,
            executed_at=now,
            idempotent_replay=replay,
            reconciliation_required=False,
            correction_available=True,
        )

    def _has_current_value_conflict(self, user_id: str, action) -> bool:
        if action.action_type != ActionType.UPDATE_ITEM_DETAIL or not action.target_item_id:
            return False
        try:
            current = self.items.get_normal_detail(
                user_id, action.target_item_id, str(action.fields.get("detail_key"))
            )
        except (ItemNotFound, ValueError):
            return False
        proposed = action.fields.get("value")
        if isinstance(current, (date, datetime)):
            current = current.isoformat()
        return current not in (None, "") and str(current) != str(proposed)

    @staticmethod
    def _target_item_id(proposal, action, results) -> str | None:
        if action.target_item_id:
            return action.target_item_id
        if action.target_item_action_index is None:
            return None
        if action.target_item_action_index >= len(proposal.proposed_actions):
            raise ProposalExecutionConflict("A proposed action dependency is invalid.")
        dependency = proposal.proposed_actions[action.target_item_action_index]
        result = results.get(dependency.action_id)
        if result is None or result.status != ActionResultStatus.COMPLETED or not result.resulting_entity_id:
            raise ProposalExecutionConflict("A required earlier action has not completed.")
        return result.resulting_entity_id


def _action_order(action) -> tuple[int, str]:
    order = {
        ActionType.CREATE_ITEM: 1,
        ActionType.UPDATE_ITEM_DETAIL: 2,
        ActionType.ADD_SAFE_NOTE: 2,
        ActionType.CREATE_RESPONSIBILITY: 3,
        ActionType.CREATE_RELATIONSHIP: 4,
        ActionType.COMPLETE_RESPONSIBILITY: 5,
        ActionType.RENEW_RESPONSIBILITY: 5,
        ActionType.SNOOZE_RESPONSIBILITY: 5,
        ActionType.REQUEST_CLARIFICATION: 9,
        ActionType.NO_ACTION: 9,
    }
    return order[action.action_type], action.action_id


def _relationship_endpoint(value: str, entity_id: str | None):
    if not entity_id:
        raise ProposalExecutionConflict("A relationship target is missing.")
    aliases = {"item": LinkedEntityType.RECORD, "responsibility": LinkedEntityType.REMINDER}
    if value in aliases:
        return aliases[value], entity_id
    try:
        return LinkedEntityType(value), entity_id
    except ValueError as exc:
        raise ProposalExecutionConflict("A relationship endpoint type is unsupported.") from exc


def _utc(value: datetime | None) -> datetime:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None:
        return current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc)
