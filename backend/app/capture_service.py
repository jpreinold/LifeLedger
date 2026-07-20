from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import hashlib
import re
from uuid import NAMESPACE_URL, uuid5

from app.action_execution_service import ActionExecutionService
from app.action_policy_service import ActionPolicyService
from app.ai_provider import AIInterpretationProvider, ProviderInterpretationError
from app.ai_usage_service import AIBudgetDenied, AIUsageService, estimate_tokens
from app.capture_models import (
    AISettings,
    AISettingsUpdate,
    ActionProposal,
    ActionSeed,
    ActionType,
    Capture,
    CaptureCreateRequest,
    CaptureDetailResponse,
    CaptureFailureCategory,
    CapturePage,
    CaptureSource,
    CaptureStatus,
    ClarificationOption,
    ClarificationQuestion,
    ClarificationSession,
    ClarificationStatus,
    ConfirmationRequirement,
    EntityCandidate,
    InterpreterKind,
    ProposalStatus,
    ProposalActionEditRequest,
    ProposedAction,
    ProviderErrorCategory,
    StructuredInterpretation,
)
from app.capture_repository import AssistantRepository
from app.capture_observability import InterpretationTimer, emit_capture_metric
from app.deterministic_interpreter import DeterministicInterpreter
from app.entity_resolution_service import EntityResolutionService
from app.item_service import ItemApplicationService, ItemDetailConflict, ItemNotFound
from app.responsibility_service import ResponsibilityApplicationService, ResponsibilityNotFound
from app.schemas import RecordType


class CaptureConflict(ValueError):
    pass


class CaptureApplicationService:
    """Owns capture interpretation and proposals; interpreters never receive a repository."""

    def __init__(
        self,
        repository: AssistantRepository,
        deterministic: DeterministicInterpreter,
        entities: EntityResolutionService,
        provider: AIInterpretationProvider,
        usage: AIUsageService,
        policy: ActionPolicyService,
        items: ItemApplicationService,
        responsibilities: ResponsibilityApplicationService,
        execution: ActionExecutionService,
    ):
        self.repository = repository
        self.deterministic = deterministic
        self.entities = entities
        self.provider = provider
        self.usage = usage
        self.policy = policy
        self.items = items
        self.responsibilities = responsibilities
        self.execution = execution

    def create_capture(
        self,
        user_id: str,
        request: CaptureCreateRequest,
        idempotency_key: str,
        *,
        now: datetime | None = None,
    ) -> tuple[Capture, bool]:
        if request.source != CaptureSource.LIFELEDGER_WEB:
            raise CaptureConflict("This capture source is not active yet.")
        if _appears_to_contain_protected_identifier(request.original_text):
            raise CaptureConflict(
                "This looks like protected information. It was not saved. Use the appropriate protected-details screen instead."
            )
        current = _utc(now)
        capture_id = str(uuid5(NAMESPACE_URL, f"lifeledger:capture:{user_id}:{idempotency_key}"))
        capture = Capture(
            capture_id=capture_id,
            user_id=user_id,
            source=request.source,
            original_text=request.original_text,
            captured_at=current,
            client_timestamp=request.client_timestamp,
            timezone=request.timezone,
            locale=request.locale,
            idempotency_key=idempotency_key,
            correlation_id=hashlib.sha256(f"{user_id}:{capture_id}".encode()).hexdigest(),
            created_at=current,
            updated_at=current,
        )
        result = self.repository.create_capture(capture)
        if result[1]:
            emit_capture_metric("CapturesCreated", capture_id=capture.capture_id, correlation_id=capture.correlation_id)
        return result

    def list_captures(
        self,
        user_id: str,
        *,
        statuses: set[CaptureStatus] | None = None,
        limit: int = 25,
        cursor: str | None = None,
    ) -> CapturePage:
        values, next_cursor = self.repository.list_captures(
            user_id, statuses=statuses, limit=limit, cursor=cursor
        )
        return CapturePage(items=values, next_cursor=next_cursor)

    def detail(self, user_id: str, capture_id: str) -> CaptureDetailResponse:
        capture = self._capture(user_id, capture_id)
        proposal = (
            self.repository.get_proposal(user_id, capture.active_proposal_id)
            if capture.active_proposal_id
            else None
        )
        clarification = (
            self.repository.get_clarification(user_id, capture.clarification_session_id)
            if capture.clarification_session_id
            else None
        )
        return CaptureDetailResponse(capture=capture, proposal=proposal, clarification=clarification)

    def interpret(
        self,
        user_id: str,
        capture_id: str,
        *,
        now: datetime | None = None,
        clarification_answers: dict[str, str] | None = None,
    ) -> CaptureDetailResponse:
        current = _utc(now)
        timer = InterpretationTimer()
        capture = self._capture(user_id, capture_id)
        if capture.status in {CaptureStatus.COMPLETED, CaptureStatus.DISMISSED, CaptureStatus.EXECUTING}:
            raise CaptureConflict("This capture cannot be interpreted in its current state.")
        attempt = capture.attempt_count + 1
        capture = capture.model_copy(
            update={
                "status": CaptureStatus.INTERPRETING,
                "attempt_count": attempt,
                "failure_category": None,
                "safe_failure_message": None,
                "updated_at": current,
            }
        )
        self.repository.save_capture(capture)

        interpretation = None
        candidates: list[EntityCandidate] = []
        interpreter = InterpreterKind.DETERMINISTIC
        model_name = None
        prompt_version = None
        user_settings = self.usage.get_settings(user_id, now=current)
        if user_settings.deterministic_first and not clarification_answers:
            interpretation, candidates = self.deterministic.interpret(
                user_id=user_id,
                text=capture.original_text,
                captured_at=capture.captured_at,
                timezone_name=capture.timezone,
            )
        else:
            candidates = self.entities.retrieve(user_id, capture.original_text, limit=12)

        if interpretation is None:
            try:
                estimated = estimate_tokens(capture.original_text) + estimate_tokens(
                    " ".join(item.display_title for item in candidates)
                )
                self.usage.assert_available(user_id, estimated_input_tokens=estimated, now=current)
                provider_arguments = {
                    "original_text": capture.original_text,
                    "captured_at": capture.captured_at,
                    "timezone_name": capture.timezone,
                    "locale": capture.locale,
                    "entity_candidates": candidates,
                    "clarification_answers": clarification_answers,
                    "safety_identifier": hashlib.sha256(f"lifeledger:{user_id}".encode()).hexdigest(),
                }
                try:
                    provider_result = self.provider.interpret_capture(**provider_arguments)
                except ProviderInterpretationError as first_error:
                    self._record_provider_error_usage(user_id, capture, first_error, current)
                    can_escalate = (
                        first_error.category == ProviderErrorCategory.INVALID_OUTPUT
                        and user_settings.allow_model_escalation
                        and bool(self.usage.settings.ai_escalation_model)
                        and self.usage.settings.ai_escalation_model != self.usage.settings.ai_default_model
                    )
                    if not can_escalate:
                        raise
                    self.usage.assert_available(user_id, estimated_input_tokens=estimated, now=current)
                    provider_result = self.provider.interpret_capture(
                        **provider_arguments,
                        model=self.usage.settings.ai_escalation_model,
                    )
                interpretation = provider_result.interpretation
                interpreter = provider_result.provider
                model_name = provider_result.model
                prompt_version = "capture-openai-actions-v2"
                usage_record, _ = self.usage.record(
                    provider_request_id=provider_result.provider_request_id,
                    user_id=user_id,
                    capture_id=capture.capture_id,
                    provider=provider_result.provider.value,
                    model=provider_result.model or "unknown",
                    input_tokens=provider_result.input_tokens,
                    output_tokens=provider_result.output_tokens,
                    result_category="accepted",
                    now=current,
                )
                emit_capture_metric("AIInterpreted", capture_id=capture.capture_id, correlation_id=capture.correlation_id, model=provider_result.model)
                emit_capture_metric("EstimatedAICost", capture_id=capture.capture_id, value=usage_record.estimated_cost_usd, unit="None", model=provider_result.model)
            except AIBudgetDenied as exc:
                category = (
                    CaptureFailureCategory.AI_DISABLED
                    if "disabled" in str(exc).casefold()
                    else CaptureFailureCategory.BUDGET_DENIED
                )
                return self._fail(capture, category, str(exc), InterpreterKind.DISABLED, current, timer=timer)
            except ProviderInterpretationError as exc:
                self._record_provider_error_usage(user_id, capture, exc, current)
                category = {
                    ProviderErrorCategory.DISABLED: CaptureFailureCategory.AI_DISABLED,
                    ProviderErrorCategory.TIMEOUT: CaptureFailureCategory.PROVIDER_TIMEOUT,
                    ProviderErrorCategory.INVALID_OUTPUT: CaptureFailureCategory.INVALID_PROVIDER_OUTPUT,
                }.get(exc.category, CaptureFailureCategory.PROVIDER_UNAVAILABLE)
                return self._fail(capture, category, exc.safe_message, InterpreterKind.DISABLED, current, timer=timer)

        if interpretation is None or not interpretation.supported or not interpretation.actions:
            return self._fail(
                capture,
                CaptureFailureCategory.UNSUPPORTED,
                "LifeLedger could not organize this capture yet. It remains in your Inbox.",
                interpreter,
                current,
                timer=timer,
            )
        proposal, clarification = self._build_proposal(
            capture,
            interpretation,
            candidates,
            interpreter,
            model_name,
            prompt_version,
            current,
        )
        self.repository.create_proposal(proposal)
        if clarification:
            self.repository.save_clarification(clarification)
        updated_capture = capture.model_copy(
            update={
                "status": (
                    CaptureStatus.NEEDS_CLARIFICATION
                    if clarification
                    else CaptureStatus.READY_FOR_REVIEW
                ),
                "interpreter": interpreter,
                "interpretation_version": proposal.structured_output_version,
                "active_proposal_id": proposal.proposal_id,
                "clarification_session_id": clarification.clarification_id if clarification else None,
                "interpretation_summary": proposal.user_facing_summary,
                "relevant_action": proposal.proposed_actions[0].explanation if proposal.proposed_actions else None,
                "updated_at": current,
            }
        )
        self.repository.save_capture(updated_capture)
        emit_capture_metric(
            "NeedsClarification" if clarification else "ReadyForReview",
            capture_id=capture.capture_id,
            proposal_id=proposal.proposal_id,
            correlation_id=capture.correlation_id,
            model=model_name,
        )
        if interpreter == InterpreterKind.DETERMINISTIC:
            emit_capture_metric("DeterministicallyInterpreted", capture_id=capture.capture_id, proposal_id=proposal.proposal_id)
        emit_capture_metric("InterpretationLatencyMs", capture_id=capture.capture_id, value=timer.milliseconds, unit="Milliseconds", result=interpreter.value)
        return CaptureDetailResponse(capture=updated_capture, proposal=proposal, clarification=clarification)

    def retry(self, user_id: str, capture_id: str, *, now: datetime | None = None):
        capture = self._capture(user_id, capture_id)
        if capture.status not in {CaptureStatus.FAILED, CaptureStatus.NEEDS_CLARIFICATION}:
            raise CaptureConflict("Only unresolved or failed captures can be retried.")
        return self.interpret(user_id, capture_id, now=now)

    def dismiss(self, user_id: str, capture_id: str, *, now: datetime | None = None) -> Capture:
        capture = self._capture(user_id, capture_id)
        if capture.status == CaptureStatus.COMPLETED:
            raise CaptureConflict("Completed captures cannot be dismissed.")
        if capture.status == CaptureStatus.DISMISSED:
            return capture
        current = _utc(now)
        updated = capture.model_copy(update={
            "status": CaptureStatus.DISMISSED,
            "updated_at": current,
            "retention_expires_at": current + timedelta(days=90),
        })
        return self.repository.save_capture(updated)

    def get_proposal(self, user_id: str, proposal_id: str) -> ActionProposal:
        proposal = self.repository.get_proposal(user_id, proposal_id)
        if proposal is None:
            raise KeyError("Proposal not found.")
        return proposal

    def edit_proposal_action(
        self,
        user_id: str,
        proposal_id: str,
        request: ProposalActionEditRequest,
        *,
        now: datetime | None = None,
    ) -> ActionProposal:
        current = _utc(now)
        proposal = self.get_proposal(user_id, proposal_id)
        if proposal.expires_at <= current:
            self.repository.save_proposal(
                proposal.model_copy(update={"status": ProposalStatus.EXPIRED, "updated_at": current})
            )
            raise CaptureConflict("This proposal has expired. Retry the capture before editing it.")
        if proposal.status != ProposalStatus.READY_FOR_REVIEW:
            raise CaptureConflict("Only a proposal ready for review can be edited.")
        action_index = next(
            (index for index, action in enumerate(proposal.proposed_actions) if action.action_id == request.action_id),
            None,
        )
        if action_index is None:
            raise CaptureConflict("The proposed action is unavailable.")
        action = proposal.proposed_actions[action_index]
        try:
            seed = ActionSeed(
                action_type=action.action_type,
                target_item_id=action.target_item_id,
                target_responsibility_id=action.target_responsibility_id,
                target_item_action_index=action.target_item_action_index,
                item_type=action.item_type,
                fields={**action.fields, **request.changes},
                explanation=_edited_explanation(action.action_type),
            )
        except ValueError as exc:
            raise CaptureConflict("Those adjusted values are not valid for this proposed change.") from exc

        decision = self.policy.evaluate(seed, has_conflict=self._has_conflict(user_id, seed))
        if decision.requires_clarification:
            raise CaptureConflict("Select the target before editing this proposed change.")
        updated_action = ProposedAction(
            **seed.model_dump(),
            action_id=action.action_id,
            source_capture_id=action.source_capture_id,
            risk_level=decision.risk_level,
            confirmation_requirement=decision.confirmation_requirement,
            idempotency_key=action.idempotency_key,
            schema_version=action.schema_version,
        )
        actions = list(proposal.proposed_actions)
        actions[action_index] = updated_action

        warnings: list[str] = []
        revalidated_actions: list[ProposedAction] = []
        for proposed_action in actions:
            has_conflict = self._has_conflict(user_id, proposed_action)
            action_decision = self.policy.evaluate(proposed_action, has_conflict=has_conflict)
            if has_conflict:
                warnings.append("Existing information differs from the adjusted proposal.")
            if action_decision.prohibited and action_decision.safe_reason:
                warnings.append(action_decision.safe_reason)
            revalidated_actions.append(proposed_action.model_copy(update={
                "risk_level": action_decision.risk_level,
                "confirmation_requirement": action_decision.confirmation_requirement,
            }))

        updated = proposal.model_copy(update={
            "proposed_actions": revalidated_actions,
            "conflict_warnings": list(dict.fromkeys(warnings)),
            "user_facing_summary": "Review the adjusted proposed changes before confirming.",
            "updated_at": current,
        })
        self.repository.save_proposal(updated)
        capture = self._capture(user_id, proposal.capture_id).model_copy(update={
            "status": CaptureStatus.READY_FOR_REVIEW,
            "interpretation_summary": updated.user_facing_summary,
            "relevant_action": updated_action.explanation,
            "updated_at": current,
        })
        self.repository.save_capture(capture)
        emit_capture_metric(
            "ReadyForReview",
            capture_id=capture.capture_id,
            proposal_id=updated.proposal_id,
            correlation_id=capture.correlation_id,
            result="edited",
        )
        return updated

    def reject_proposal(self, user_id: str, proposal_id: str, *, now: datetime | None = None) -> ActionProposal:
        current = _utc(now)
        proposal = self.get_proposal(user_id, proposal_id)
        if proposal.status == ProposalStatus.COMPLETED:
            raise CaptureConflict("Completed proposals cannot be rejected.")
        if proposal.status == ProposalStatus.REJECTED:
            return proposal
        if proposal.status == ProposalStatus.EXECUTING:
            raise CaptureConflict("An executing proposal cannot be rejected.")
        updated = proposal.model_copy(
            update={"status": ProposalStatus.REJECTED, "rejected_at": current, "updated_at": current}
        )
        self.repository.save_proposal(updated)
        capture = self._capture(user_id, proposal.capture_id)
        self.repository.save_capture(capture.model_copy(update={
            "status": CaptureStatus.DISMISSED,
            "updated_at": current,
            "retention_expires_at": current + timedelta(days=90),
        }))
        emit_capture_metric("Rejected", capture_id=proposal.capture_id, proposal_id=proposal.proposal_id)
        return updated

    def approve_proposal(self, user_id: str, proposal_id: str, *, now: datetime | None = None):
        return self.execution.approve_and_execute(user_id, proposal_id, now=now)

    def answer_clarifications(
        self,
        user_id: str,
        proposal_id: str,
        answers: dict[str, str],
        *,
        now: datetime | None = None,
    ) -> CaptureDetailResponse:
        current = _utc(now)
        proposal = self.get_proposal(user_id, proposal_id)
        session = self.repository.get_clarification_for_proposal(user_id, proposal_id)
        if session is None or session.status != ClarificationStatus.OPEN:
            raise CaptureConflict("This clarification is no longer open.")
        if session.expires_at <= current:
            self.repository.save_clarification(
                session.model_copy(update={"status": ClarificationStatus.EXPIRED, "updated_at": current})
            )
            raise CaptureConflict("This clarification has expired. Retry the capture.")
        questions = {item.question_id: item for item in session.questions}
        if not set(answers) <= set(questions):
            raise CaptureConflict("A clarification question is invalid.")
        merged_answers = {**session.answers, **answers}
        actions = list(proposal.proposed_actions)
        candidates = proposal.entity_candidates
        requires_ai_free_text = False
        for question_id, option_id in answers.items():
            question = questions[question_id]
            if question.allow_free_text:
                clean = " ".join(option_id.split())
                if not clean or len(clean) > 500:
                    raise CaptureConflict("A clarification answer must contain 1 to 500 characters.")
                merged_answers[question_id] = clean
                if not _apply_birthday_clarification(actions, question.prompt, clean):
                    requires_ai_free_text = True
                continue
            if not any(item.option_id == option_id for item in question.options):
                raise CaptureConflict("A clarification answer is invalid.")
            action_index = next(
                (index for index, action in enumerate(actions) if action.action_id == question.action_id), None
            )
            if action_index is None:
                continue
            candidate = next(
                (
                    item
                    for item in candidates
                    if _option_id(proposal.proposal_id, question.question_id, item.entity_id) == option_id
                ),
                None,
            )
            if candidate is None:
                raise CaptureConflict("The selected entity is no longer available.")
            action = actions[action_index]
            if question.target_field == "target_item_id":
                action = action.model_copy(update={"target_item_id": candidate.entity_id})
            elif question.target_field == "target_responsibility_id":
                action = action.model_copy(update={"target_responsibility_id": candidate.entity_id})
            actions[action_index] = action.model_copy(
                update={
                    "risk_level": self.policy.evaluate(action).risk_level,
                    "confirmation_requirement": ConfirmationRequirement.ALWAYS,
                }
            )
        all_answered = set(merged_answers) == set(questions)
        if not all_answered:
            updated_session = session.model_copy(update={"answers": merged_answers, "updated_at": current})
            self.repository.save_clarification(updated_session)
            return CaptureDetailResponse(
                capture=self._capture(user_id, proposal.capture_id),
                proposal=proposal,
                clarification=updated_session,
            )
        if requires_ai_free_text:
            if self.usage.settings.ai_max_clarification_calls < 1:
                raise CaptureConflict("This clarification needs manual review because additional AI calls are disabled.")
            capture = self._capture(user_id, proposal.capture_id)
            clarification_calls = max(0, capture.attempt_count - 1)
            if clarification_calls >= self.usage.settings.ai_max_clarification_calls:
                raise CaptureConflict("The AI clarification limit has been reached. Review this capture manually.")
            self.repository.save_clarification(session.model_copy(
                update={"answers": merged_answers, "status": ClarificationStatus.ANSWERED, "updated_at": current}
            ))
            self.repository.save_proposal(proposal.model_copy(update={"status": ProposalStatus.EXPIRED, "updated_at": current}))
            return self.interpret(
                user_id,
                proposal.capture_id,
                now=current,
                clarification_answers=merged_answers,
            )
        updated_proposal = proposal.model_copy(
            update={
                "status": ProposalStatus.READY_FOR_REVIEW,
                "proposed_actions": actions,
                "ambiguity_reasons": [],
                "missing_information": [],
                "updated_at": current,
            }
        )
        updated_session = session.model_copy(
            update={"answers": merged_answers, "status": ClarificationStatus.ANSWERED, "updated_at": current}
        )
        capture = self._capture(user_id, proposal.capture_id).model_copy(
            update={"status": CaptureStatus.READY_FOR_REVIEW, "updated_at": current}
        )
        self.repository.save_proposal(updated_proposal)
        self.repository.save_clarification(updated_session)
        self.repository.save_capture(capture)
        return CaptureDetailResponse(capture=capture, proposal=updated_proposal, clarification=updated_session)

    def _record_provider_error_usage(
        self,
        user_id: str,
        capture: Capture,
        error: ProviderInterpretationError,
        now: datetime,
    ) -> None:
        if not error.provider_request_id:
            return
        usage_record, _ = self.usage.record(
            provider_request_id=error.provider_request_id,
            user_id=user_id,
            capture_id=capture.capture_id,
            provider=error.provider or "unknown",
            model=error.model or "unknown",
            input_tokens=error.input_tokens,
            output_tokens=error.output_tokens,
            result_category=error.category.value,
            now=now,
        )
        emit_capture_metric(
            "EstimatedAICost",
            capture_id=capture.capture_id,
            value=usage_record.estimated_cost_usd,
            unit="None",
            model=error.model,
            result=error.category.value,
        )

    def update_ai_settings(
        self, user_id: str, request: AISettingsUpdate, *, now: datetime | None = None
    ) -> AISettings:
        current = self.usage.get_settings(user_id, now=now)
        changes = request.model_dump(exclude_none=True)
        return self.usage.save_settings(current.model_copy(update={**changes, "updated_at": _utc(now)}))

    def _build_proposal(
        self,
        capture: Capture,
        interpretation: StructuredInterpretation,
        candidates: list[EntityCandidate],
        interpreter: InterpreterKind,
        model_name: str | None,
        prompt_version: str | None,
        now: datetime,
    ) -> tuple[ActionProposal, ClarificationSession | None]:
        proposal_id = str(
            uuid5(NAMESPACE_URL, f"lifeledger:proposal:{capture.capture_id}:{capture.attempt_count}")
        )
        actions: list[ProposedAction] = []
        ambiguity = list(interpretation.ambiguity_reasons)
        conflicts = list(interpretation.conflict_warnings)
        missing = list(interpretation.missing_information)
        questions: list[ClarificationQuestion] = []
        candidate_ids = {item.entity_id for item in candidates}

        for index, seed in enumerate(interpretation.actions):
            seed = self._validated_target(seed, candidates, candidate_ids)
            has_conflict = self._has_conflict(capture.user_id, seed)
            if has_conflict:
                conflicts.append("Existing information differs from the proposed update.")
            decision = self.policy.evaluate(seed, has_conflict=has_conflict)
            action_id = str(uuid5(NAMESPACE_URL, f"{proposal_id}:action:{index}"))
            action = ProposedAction(
                **seed.model_dump(),
                action_id=action_id,
                source_capture_id=capture.capture_id,
                risk_level=decision.risk_level,
                confirmation_requirement=decision.confirmation_requirement,
                idempotency_key=f"capture:{capture.capture_id}:attempt:{capture.attempt_count}:action:{index}",
            )
            actions.append(action)
            if decision.prohibited:
                conflicts.append(decision.safe_reason or "This action is not available through capture.")
                emit_capture_metric(
                    "ActionPolicyRejected",
                    capture_id=capture.capture_id,
                    proposal_id=proposal_id,
                    action_type=seed.action_type.value,
                )
            if decision.requires_clarification and not has_conflict:
                question = self._entity_question(proposal_id, action, candidates, len(questions))
                if question:
                    questions.append(question)
                else:
                    missing.append(decision.safe_reason or "More information is needed.")

        if _has_yearless_birthday_action(actions):
            missing = [item for item in missing if "birth year" not in item.casefold()]

        needs_clarification = bool(questions or ambiguity or missing or conflicts)
        # Prohibited proposals remain reviewable but cannot execute; the review explains why.
        if any(action.confirmation_requirement == ConfirmationRequirement.PROHIBITED for action in actions):
            needs_clarification = False
        proposal = ActionProposal(
            proposal_id=proposal_id,
            user_id=capture.user_id,
            capture_id=capture.capture_id,
            status=ProposalStatus.NEEDS_CLARIFICATION if needs_clarification else ProposalStatus.READY_FOR_REVIEW,
            proposed_actions=actions,
            entity_candidates=candidates,
            ambiguity_reasons=list(dict.fromkeys(ambiguity)),
            conflict_warnings=list(dict.fromkeys(conflicts)),
            missing_information=list(dict.fromkeys(missing)),
            user_facing_summary=interpretation.summary,
            interpreter=interpreter,
            model_name=model_name,
            prompt_version=prompt_version,
            expires_at=now + timedelta(days=7),
            created_at=now,
            updated_at=now,
        )
        clarification = None
        if questions:
            clarification_id = str(uuid5(NAMESPACE_URL, f"{proposal_id}:clarification"))
            clarification = ClarificationSession(
                clarification_id=clarification_id,
                user_id=capture.user_id,
                capture_id=capture.capture_id,
                proposal_id=proposal_id,
                questions=questions[:5],
                expires_at=proposal.expires_at,
                created_at=now,
                updated_at=now,
            )
        elif needs_clarification and not any(
            action.confirmation_requirement == ConfirmationRequirement.PROHIBITED for action in actions
        ):
            clarification_id = str(uuid5(NAMESPACE_URL, f"{proposal_id}:clarification"))
            question_id = str(uuid5(NAMESPACE_URL, f"{proposal_id}:question:general"))
            prompt = (missing or ambiguity or ["What detail should LifeLedger use?"])[0]
            clarification = ClarificationSession(
                clarification_id=clarification_id,
                user_id=capture.user_id,
                capture_id=capture.capture_id,
                proposal_id=proposal_id,
                questions=[ClarificationQuestion(
                    question_id=question_id,
                    prompt=prompt,
                    options=[],
                    allow_free_text=True,
                    target_field="clarification_context",
                )],
                expires_at=proposal.expires_at,
                created_at=now,
                updated_at=now,
            )
        return proposal, clarification

    def _validated_target(
        self, seed: ActionSeed, candidates: list[EntityCandidate], candidate_ids: set[str]
    ) -> ActionSeed:
        if seed.target_item_id:
            if seed.target_item_id not in candidate_ids:
                return seed.model_copy(update={"target_item_id": None})
            candidate = next(item for item in candidates if item.entity_id == seed.target_item_id)
            if candidate.entity_type != "item":
                return seed.model_copy(update={"target_item_id": None})
            return seed.model_copy(update={"item_type": candidate.item_type})
        if seed.target_responsibility_id:
            candidate = next(
                (item for item in candidates if item.entity_id == seed.target_responsibility_id), None
            )
            if candidate is None or candidate.entity_type != "responsibility":
                return seed.model_copy(update={"target_responsibility_id": None})
        return seed

    def _has_conflict(self, user_id: str, seed: ActionSeed) -> bool:
        if seed.action_type != ActionType.UPDATE_ITEM_DETAIL or not seed.target_item_id:
            return False
        try:
            current = self.items.get_normal_detail(
                user_id, seed.target_item_id, str(seed.fields.get("detail_key"))
            )
        except (ItemNotFound, ValueError):
            return False
        proposed = seed.fields.get("value")
        if isinstance(current, (date, datetime)):
            current = current.isoformat()
        return current not in (None, "") and str(current) != str(proposed)

    def _entity_question(
        self,
        proposal_id: str,
        action: ProposedAction,
        candidates: list[EntityCandidate],
        number: int,
    ) -> ClarificationQuestion | None:
        target_field = None
        entity_type = None
        if action.action_type in {ActionType.UPDATE_ITEM_DETAIL, ActionType.ADD_SAFE_NOTE}:
            target_field, entity_type = "target_item_id", "item"
        elif action.action_type in {
            ActionType.COMPLETE_RESPONSIBILITY,
            ActionType.RENEW_RESPONSIBILITY,
            ActionType.SNOOZE_RESPONSIBILITY,
        }:
            target_field, entity_type = "target_responsibility_id", "responsibility"
        if not target_field:
            return None
        values = [item for item in candidates if item.entity_type == entity_type][:10]
        if not values:
            return None
        question_id = str(uuid5(NAMESPACE_URL, f"{proposal_id}:question:{number}"))
        return ClarificationQuestion(
            question_id=question_id,
            prompt=(
                "Which item did you mean?"
                if entity_type == "item"
                else "Which responsibility did you mean?"
            ),
            options=[
                ClarificationOption(
                    option_id=_option_id(proposal_id, question_id, item.entity_id),
                    label=item.display_title,
                )
                for item in values
            ],
            action_id=action.action_id,
            target_field=target_field,
        )

    def _fail(
        self,
        capture: Capture,
        category: CaptureFailureCategory,
        message: str,
        interpreter: InterpreterKind,
        now: datetime,
        timer: InterpretationTimer | None = None,
    ) -> CaptureDetailResponse:
        updated = capture.model_copy(
            update={
                "status": CaptureStatus.FAILED,
                "interpreter": interpreter,
                "failure_category": category,
                "safe_failure_message": " ".join(message.split())[:240],
                "updated_at": now,
            }
        )
        self.repository.save_capture(updated)
        metric = {
            CaptureFailureCategory.BUDGET_DENIED: "BudgetDenied",
            CaptureFailureCategory.PROVIDER_TIMEOUT: "ProviderTimeout",
            CaptureFailureCategory.INVALID_PROVIDER_OUTPUT: "SchemaValidationFailure",
        }.get(category, "Failed")
        emit_capture_metric(metric, capture_id=capture.capture_id, correlation_id=capture.correlation_id, result=category.value)
        if timer:
            emit_capture_metric("InterpretationLatencyMs", capture_id=capture.capture_id, value=timer.milliseconds, unit="Milliseconds", result=category.value)
        return CaptureDetailResponse(capture=updated)

    def _capture(self, user_id: str, capture_id: str) -> Capture:
        capture = self.repository.get_capture(user_id, capture_id)
        if capture is None:
            raise KeyError("Capture not found.")
        return capture


def _option_id(proposal_id: str, question_id: str, entity_id: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"{proposal_id}:{question_id}:{entity_id}"))


def _has_yearless_birthday_action(actions: list[ProposedAction]) -> bool:
    return any(
        action.action_type == ActionType.CREATE_ITEM
        and action.item_type in {RecordType.PERSON, RecordType.PET}
        and str(action.fields.get("details", {}).get("birthday", "")).startswith("--")
        for action in actions
    )


def _apply_birthday_clarification(actions: list[ProposedAction], prompt: str, answer: str) -> bool:
    if "birth year" not in prompt.casefold():
        return False
    year_match = re.fullmatch(r"(?:the\s+year\s+)?(?P<year>\d{4})", answer.strip(), flags=re.IGNORECASE)
    age_match = re.fullmatch(
        r"(?:(?:turning|turns?|age(?:\s+at\s+next\s+birthday)?)\s+)?(?P<age>\d{1,3})",
        answer.strip(),
        flags=re.IGNORECASE,
    )
    for index, action in enumerate(actions):
        if action.action_type != ActionType.CREATE_ITEM or action.item_type not in {RecordType.PERSON, RecordType.PET}:
            continue
        details = dict(action.fields.get("details", {}))
        birthday = str(details.get("birthday", ""))
        if not re.fullmatch(r"--\d{2}-\d{2}", birthday):
            continue
        if year_match:
            year = int(year_match.group("year"))
            try:
                date.fromisoformat(f"{year:04d}{birthday[1:]}")
            except ValueError:
                return False
            details["birthday"] = f"{year:04d}{birthday[1:]}"
            details.pop("birthday_turning_age", None)
        elif age_match and 0 <= int(age_match.group("age")) <= 150:
            details["birthday_turning_age"] = int(age_match.group("age"))
        else:
            return False
        fields = {**action.fields, "details": details}
        actions[index] = action.model_copy(update={
            "fields": fields,
            "explanation": _edited_explanation(action.action_type),
            "confirmation_requirement": ConfirmationRequirement.ALWAYS,
        })
        return True
    return False


def _appears_to_contain_protected_identifier(value: str) -> bool:
    """Conservative preflight for a few obvious cases; not a complete DLP system."""
    text = " ".join(value.casefold().split())
    if re.search(r"\b(password|passcode|authentication code|recovery code|api key)\b", text):
        return True
    if re.search(r"\bpassport\s*(?:number|no\.?|#)\s*(?:is|:)?\s*[a-z0-9-]{6,20}\b", text):
        return True
    if re.search(r"\bvin\s*(?:is|:|#)?\s*[a-hj-npr-z0-9]{17}\b", text):
        return True
    digits = re.sub(r"[^0-9]", "", text)
    return bool(re.search(r"\b(card|credit card|debit card)\b", text) and 13 <= len(digits) <= 19)


def _edited_explanation(action_type: ActionType) -> str:
    return {
        ActionType.CREATE_ITEM: "Create the item using the adjusted details.",
        ActionType.UPDATE_ITEM_DETAIL: "Update the selected item using the adjusted value.",
        ActionType.CREATE_RESPONSIBILITY: "Create the responsibility using the adjusted schedule.",
        ActionType.COMPLETE_RESPONSIBILITY: "Complete the selected responsibility using the adjusted details.",
        ActionType.RENEW_RESPONSIBILITY: "Renew the selected responsibility using the adjusted dates.",
        ActionType.SNOOZE_RESPONSIBILITY: "Snooze the selected responsibility until the adjusted time.",
        ActionType.CREATE_RELATIONSHIP: "Create the adjusted relationship.",
        ActionType.ADD_SAFE_NOTE: "Add the adjusted safe note.",
        ActionType.REQUEST_CLARIFICATION: "Use the adjusted clarification request.",
        ActionType.NO_ACTION: "Keep this capture without making a change.",
    }[action_type]


def _utc(value: datetime | None) -> datetime:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None:
        return current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc)
