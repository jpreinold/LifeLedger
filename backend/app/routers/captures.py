from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status

from app.action_execution_service import ProposalExecutionConflict
from app.auth import UserContext, get_current_user
from app.capture_models import (
    AISettingsResponse,
    AISettingsUpdate,
    AIUsageSummary,
    ActionProposal,
    Capture,
    CaptureCreateRequest,
    CaptureDetailResponse,
    CapturePage,
    CaptureStatus,
    ClarificationAnswerRequest,
    ProposalActionEditRequest,
)
from app.capture_service import CaptureApplicationService, CaptureConflict
from app.config import AI_PROVIDER_DISABLED, Settings
from app.route_support import (
    get_app_settings,
    get_capture_application_service,
    no_store_headers,
)


router = APIRouter(tags=["capture"])


def _private(response: Response) -> None:
    for key, value in no_store_headers().items():
        response.headers[key] = value


def _not_found(exc: KeyError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc).strip("'"))


def _conflict(exc: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.post("/captures", response_model=Capture, status_code=status.HTTP_201_CREATED)
def create_capture(
    payload: CaptureCreateRequest,
    response: Response,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=128),
    current_user: UserContext = Depends(get_current_user),
    service: CaptureApplicationService = Depends(get_capture_application_service),
) -> Capture:
    _private(response)
    try:
        capture, created = service.create_capture(current_user.user_id, payload, idempotency_key)
    except CaptureConflict as exc:
        raise _conflict(exc) from exc
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return capture


@router.get("/captures", response_model=CapturePage)
def list_captures(
    response: Response,
    status_filter: list[CaptureStatus] | None = Query(default=None, alias="status"),
    limit: int = Query(default=25, ge=1, le=100),
    cursor: str | None = Query(default=None),
    current_user: UserContext = Depends(get_current_user),
    service: CaptureApplicationService = Depends(get_capture_application_service),
) -> CapturePage:
    _private(response)
    try:
        return service.list_captures(
            current_user.user_id,
            statuses=set(status_filter) if status_filter else None,
            limit=limit,
            cursor=cursor,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("/captures/{capture_id}", response_model=CaptureDetailResponse)
def get_capture(
    capture_id: str,
    response: Response,
    current_user: UserContext = Depends(get_current_user),
    service: CaptureApplicationService = Depends(get_capture_application_service),
) -> CaptureDetailResponse:
    _private(response)
    try:
        return service.detail(current_user.user_id, capture_id)
    except KeyError as exc:
        raise _not_found(exc) from exc


@router.post("/captures/{capture_id}/interpret", response_model=CaptureDetailResponse)
def interpret_capture(
    capture_id: str,
    response: Response,
    current_user: UserContext = Depends(get_current_user),
    service: CaptureApplicationService = Depends(get_capture_application_service),
) -> CaptureDetailResponse:
    _private(response)
    try:
        return service.interpret(current_user.user_id, capture_id)
    except KeyError as exc:
        raise _not_found(exc) from exc
    except CaptureConflict as exc:
        raise _conflict(exc) from exc


@router.post("/captures/{capture_id}/retry", response_model=CaptureDetailResponse)
def retry_capture(
    capture_id: str,
    response: Response,
    current_user: UserContext = Depends(get_current_user),
    service: CaptureApplicationService = Depends(get_capture_application_service),
) -> CaptureDetailResponse:
    _private(response)
    try:
        return service.retry(current_user.user_id, capture_id)
    except KeyError as exc:
        raise _not_found(exc) from exc
    except CaptureConflict as exc:
        raise _conflict(exc) from exc


@router.post("/captures/{capture_id}/dismiss", response_model=Capture)
def dismiss_capture(
    capture_id: str,
    response: Response,
    current_user: UserContext = Depends(get_current_user),
    service: CaptureApplicationService = Depends(get_capture_application_service),
) -> Capture:
    _private(response)
    try:
        return service.dismiss(current_user.user_id, capture_id)
    except KeyError as exc:
        raise _not_found(exc) from exc
    except CaptureConflict as exc:
        raise _conflict(exc) from exc


@router.get("/proposals/{proposal_id}", response_model=ActionProposal)
def get_proposal(
    proposal_id: str,
    response: Response,
    current_user: UserContext = Depends(get_current_user),
    service: CaptureApplicationService = Depends(get_capture_application_service),
) -> ActionProposal:
    _private(response)
    try:
        return service.get_proposal(current_user.user_id, proposal_id)
    except KeyError as exc:
        raise _not_found(exc) from exc


@router.patch("/proposals/{proposal_id}", response_model=ActionProposal)
def edit_proposal_action(
    proposal_id: str,
    payload: ProposalActionEditRequest,
    response: Response,
    current_user: UserContext = Depends(get_current_user),
    service: CaptureApplicationService = Depends(get_capture_application_service),
) -> ActionProposal:
    _private(response)
    try:
        return service.edit_proposal_action(current_user.user_id, proposal_id, payload)
    except KeyError as exc:
        raise _not_found(exc) from exc
    except CaptureConflict as exc:
        raise _conflict(exc) from exc


@router.post("/proposals/{proposal_id}/clarifications", response_model=CaptureDetailResponse)
def answer_clarifications(
    proposal_id: str,
    payload: ClarificationAnswerRequest,
    response: Response,
    current_user: UserContext = Depends(get_current_user),
    service: CaptureApplicationService = Depends(get_capture_application_service),
) -> CaptureDetailResponse:
    _private(response)
    try:
        return service.answer_clarifications(current_user.user_id, proposal_id, payload.answers)
    except KeyError as exc:
        raise _not_found(exc) from exc
    except CaptureConflict as exc:
        raise _conflict(exc) from exc


@router.post("/proposals/{proposal_id}/approve", response_model=ActionProposal)
def approve_proposal(
    proposal_id: str,
    response: Response,
    current_user: UserContext = Depends(get_current_user),
    service: CaptureApplicationService = Depends(get_capture_application_service),
) -> ActionProposal:
    _private(response)
    try:
        return service.approve_proposal(current_user.user_id, proposal_id)
    except KeyError as exc:
        raise _not_found(exc) from exc
    except ProposalExecutionConflict as exc:
        raise _conflict(exc) from exc


@router.post("/proposals/{proposal_id}/reject", response_model=ActionProposal)
def reject_proposal(
    proposal_id: str,
    response: Response,
    current_user: UserContext = Depends(get_current_user),
    service: CaptureApplicationService = Depends(get_capture_application_service),
) -> ActionProposal:
    _private(response)
    try:
        return service.reject_proposal(current_user.user_id, proposal_id)
    except KeyError as exc:
        raise _not_found(exc) from exc
    except CaptureConflict as exc:
        raise _conflict(exc) from exc


@router.get("/ai-usage", response_model=AIUsageSummary)
def ai_usage(
    response: Response,
    current_user: UserContext = Depends(get_current_user),
    service: CaptureApplicationService = Depends(get_capture_application_service),
) -> AIUsageSummary:
    _private(response)
    return service.usage.summary(current_user.user_id)


@router.get("/ai-settings", response_model=AISettingsResponse)
def ai_settings(
    response: Response,
    current_user: UserContext = Depends(get_current_user),
    service: CaptureApplicationService = Depends(get_capture_application_service),
    settings: Settings = Depends(get_app_settings),
) -> AISettingsResponse:
    _private(response)
    return AISettingsResponse(
        settings=service.usage.get_settings(current_user.user_id),
        usage=service.usage.summary(current_user.user_id),
        provider_configured=settings.ai_provider != AI_PROVIDER_DISABLED and not settings.ai_emergency_disabled,
        default_model=settings.ai_default_model,
        escalation_model=settings.ai_escalation_model or None,
    )


@router.put("/ai-settings", response_model=AISettingsResponse)
def update_ai_settings(
    payload: AISettingsUpdate,
    response: Response,
    current_user: UserContext = Depends(get_current_user),
    service: CaptureApplicationService = Depends(get_capture_application_service),
    settings: Settings = Depends(get_app_settings),
) -> AISettingsResponse:
    _private(response)
    saved = service.update_ai_settings(current_user.user_id, payload)
    return AISettingsResponse(
        settings=saved,
        usage=service.usage.summary(current_user.user_id),
        provider_configured=settings.ai_provider != AI_PROVIDER_DISABLED and not settings.ai_emergency_disabled,
        default_model=settings.ai_default_model,
        escalation_model=settings.ai_escalation_model or None,
    )
