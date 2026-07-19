from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field

from app.account_deletion_service import AccountDeletionService
from app.account_export_service import AccountExportService, AccountUnavailable, ExportAuthenticationRequired, ExportExpired
from app.account_models import AccountOperation, AccountOperationStatus
from app.account_operations_repository import AccountOperationsRepository
from app.account_runtime import (
    dispatch_account_operation,
    get_account_deletion_service,
    get_account_export_service,
    get_account_operations_repository,
)
from app.auth import UserContext, get_current_user
from app.config import COGNITO_AUTH_MODE, get_settings


router = APIRouter(prefix="/account", tags=["account"])


def get_account_dispatcher():
    return dispatch_account_operation


class ExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    include_protected_details: bool = False
    confirm_sensitive_export: bool = False


class DeleteAccountRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirmation: str = Field(min_length=1, max_length=40)


class AccountOperationResponse(BaseModel):
    operation_id: str
    operation_type: str
    status: str
    include_protected_details: bool = False
    created_at: datetime
    updated_at: datetime
    expires_at: datetime | None = None
    artifact_size_bytes: int | None = None
    safe_error: str | None = None
    steps: list[dict] = Field(default_factory=list)


class ExportDownloadResponse(BaseModel):
    download_url: str
    expires_in_seconds: int


@router.get("/status")
def account_status(
    response: Response,
    current_user: UserContext = Depends(get_current_user),
    operations: AccountOperationsRepository = Depends(get_account_operations_repository),
):
    _no_store(response)
    lifecycle = operations.get_lifecycle(current_user.user_id)
    operation = (
        operations.get_operation(current_user.user_id, lifecycle.current_operation_id)
        if lifecycle.current_operation_id
        else None
    )
    if operation is None:
        recent = operations.list_operations(current_user.user_id, limit=1)
        operation = recent[0] if recent else None
    return {
        "state": lifecycle.state.value,
        "current_operation": _response(operation).model_dump(mode="json") if operation else None,
    }


@router.post("/exports", response_model=AccountOperationResponse, status_code=status.HTTP_202_ACCEPTED)
def create_export(
    payload: ExportRequest,
    response: Response,
    current_user: UserContext = Depends(get_current_user),
    service: AccountExportService = Depends(get_account_export_service),
    dispatcher=Depends(get_account_dispatcher),
):
    _no_store(response)
    if payload.include_protected_details and not payload.confirm_sensitive_export:
        raise _error(status.HTTP_422_UNPROCESSABLE_ENTITY, "protected_export_confirmation_required", "Confirm that the export will contain sensitive plaintext.")
    settings = get_settings()
    recently_authenticated = settings.auth_mode != COGNITO_AUTH_MODE or current_user.is_recently_authenticated()
    try:
        operation, should_dispatch = service.request_export(
            current_user.user_id,
            include_protected_details=payload.include_protected_details,
            recently_authenticated=recently_authenticated,
        )
    except ExportAuthenticationRequired as exc:
        raise _error(status.HTTP_401_UNAUTHORIZED, "recent_authentication_required", str(exc)) from exc
    except AccountUnavailable as exc:
        raise _error(status.HTTP_409_CONFLICT, "account_unavailable", str(exc)) from exc
    except ValueError as exc:
        raise _error(status.HTTP_409_CONFLICT, "export_in_progress", str(exc)) from exc
    if should_dispatch:
        try:
            processed = dispatcher(current_user.user_id, operation.operation_id, "export")
        except Exception as exc:
            service.mark_dispatch_failed(current_user.user_id, operation.operation_id)
            raise _error(status.HTTP_503_SERVICE_UNAVAILABLE, "external_cleanup_incomplete", "The export was queued but processing is temporarily unavailable.") from exc
        refreshed = service.operations.get_operation(current_user.user_id, operation.operation_id)
        operation = processed or refreshed or operation
    return _response(operation)


@router.get("/exports/{operation_id}", response_model=AccountOperationResponse)
def get_export(
    operation_id: str,
    response: Response,
    current_user: UserContext = Depends(get_current_user),
    operations: AccountOperationsRepository = Depends(get_account_operations_repository),
):
    _no_store(response)
    operation = operations.get_operation(current_user.user_id, operation_id)
    if operation is None or operation.operation_type.value != "export":
        raise _error(status.HTTP_404_NOT_FOUND, "account_operation_not_found", "Export was not found.")
    return _response(operation)


@router.post("/exports/{operation_id}/download", response_model=ExportDownloadResponse)
def download_export(
    operation_id: str,
    response: Response,
    current_user: UserContext = Depends(get_current_user),
    service: AccountExportService = Depends(get_account_export_service),
):
    _no_store(response)
    try:
        url = service.get_download_url(current_user.user_id, operation_id, expires_in_seconds=300)
    except KeyError as exc:
        raise _error(status.HTTP_404_NOT_FOUND, "account_operation_not_found", "Export was not found.") from exc
    except ExportExpired as exc:
        raise _error(status.HTTP_410_GONE, "export_expired", str(exc)) from exc
    return ExportDownloadResponse(download_url=url, expires_in_seconds=300)


@router.post("/deletion", response_model=AccountOperationResponse, status_code=status.HTTP_202_ACCEPTED)
def request_deletion(
    payload: DeleteAccountRequest,
    response: Response,
    current_user: UserContext = Depends(get_current_user),
    service: AccountDeletionService = Depends(get_account_deletion_service),
    dispatcher=Depends(get_account_dispatcher),
):
    _no_store(response)
    if payload.confirmation.strip() != "DELETE MY ACCOUNT":
        raise _error(status.HTTP_422_UNPROCESSABLE_ENTITY, "deletion_confirmation_required", "Type DELETE MY ACCOUNT to confirm.")
    if get_settings().auth_mode == COGNITO_AUTH_MODE and not current_user.is_recently_authenticated():
        raise _error(status.HTTP_401_UNAUTHORIZED, "recent_authentication_required", "Recent authentication is required for account deletion.")
    operation, should_dispatch = service.request_deletion(current_user.user_id)
    if should_dispatch:
        try:
            processed = dispatcher(current_user.user_id, operation.operation_id, "deletion")
        except Exception as exc:
            service.mark_dispatch_failed(current_user.user_id, operation.operation_id)
            raise _error(status.HTTP_503_SERVICE_UNAVAILABLE, "external_cleanup_incomplete", "Deletion was recorded but processing is temporarily unavailable.") from exc
        refreshed = service.operations.get_operation(current_user.user_id, operation.operation_id)
        operation = processed or refreshed or operation
    return _response(operation)


@router.get("/deletion/{operation_id}", response_model=AccountOperationResponse)
def get_deletion(
    operation_id: str,
    response: Response,
    current_user: UserContext = Depends(get_current_user),
    operations: AccountOperationsRepository = Depends(get_account_operations_repository),
):
    _no_store(response)
    operation = operations.get_operation(current_user.user_id, operation_id)
    if operation is None or operation.operation_type.value != "deletion":
        raise _error(status.HTTP_404_NOT_FOUND, "account_operation_not_found", "Deletion request was not found.")
    return _response(operation)


def _response(operation: AccountOperation) -> AccountOperationResponse:
    return AccountOperationResponse(
        operation_id=operation.operation_id,
        operation_type=operation.operation_type.value,
        status=operation.status.value,
        include_protected_details=operation.include_protected_details,
        created_at=operation.created_at,
        updated_at=operation.updated_at,
        expires_at=operation.expires_at,
        artifact_size_bytes=operation.artifact_size_bytes,
        safe_error=operation.safe_error,
        steps=[step.model_dump(mode="json") for step in operation.steps],
    )


def _error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message},
        headers={"Cache-Control": "no-store, private", "Pragma": "no-cache"},
    )


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["Pragma"] = "no-cache"
