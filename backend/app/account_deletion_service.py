from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import datetime, timezone
from uuid import uuid4

from app.account_data_inventory import AccountDataInventory
from app.account_models import (
    AccountDeletionVerification,
    AccountLifecycle,
    AccountOperation,
    AccountOperationStatus,
    AccountOperationStep,
    AccountOperationType,
    AccountState,
    AccountStepStatus,
)
from app.account_operations_repository import AccountOperationsRepository
from app.reconciliation import ReconciliationDomain, ReconciliationSeverity
from app.reconciliation_service import ReconciliationService


logger = logging.getLogger(__name__)


class AccountDeletionService:
    def __init__(
        self,
        inventory: AccountDataInventory,
        operations: AccountOperationsRepository,
        reconciliation: ReconciliationService,
        identity_cleaner: Callable[[str], None],
        *,
        batch_size: int = 100,
        max_batches_per_step: int = 10,
    ):
        self.inventory = inventory
        self.operations = operations
        self.reconciliation = reconciliation
        self.identity_cleaner = identity_cleaner
        self.batch_size = batch_size
        self.max_batches_per_step = max_batches_per_step

    def request_deletion(self, user_id: str, *, now: datetime | None = None) -> tuple[AccountOperation, bool]:
        lifecycle = self.operations.get_lifecycle(user_id)
        existing = self.operations.find_open_operation(user_id, AccountOperationType.DELETION)
        if existing:
            return existing, False
        if lifecycle.state == AccountState.DELETED:
            raise ValueError("Account deletion is already complete.")
        requested_at = _utc(now or datetime.now(timezone.utc))
        failed = next(
            (
                item
                for item in self.operations.list_operations(user_id, limit=100)
                if item.operation_type == AccountOperationType.DELETION
                and item.status == AccountOperationStatus.FAILED
            ),
            None,
        )
        if failed is not None:
            operation = failed.model_copy(
                update={
                    "status": AccountOperationStatus.PENDING,
                    "safe_error": None,
                    "updated_at": requested_at,
                    "steps": [
                        step.model_copy(
                            update={"status": AccountStepStatus.PENDING, "safe_error": None, "updated_at": requested_at}
                        )
                        if step.status == AccountStepStatus.FAILED
                        else step
                        for step in failed.steps
                    ],
                }
            )
            self.operations.save_operation(operation)
        else:
            steps = [
                AccountOperationStep(name=store.name, updated_at=requested_at)
                for store in self.inventory.deletion_stores
            ] + [
                AccountOperationStep(name="verification", updated_at=requested_at),
                AccountOperationStep(name="cognito_identity", updated_at=requested_at),
            ]
            operation = AccountOperation(
                operation_id=str(uuid4()),
                user_id=user_id,
                operation_type=AccountOperationType.DELETION,
                status=AccountOperationStatus.PENDING,
                created_at=requested_at,
                updated_at=requested_at,
                steps=steps,
            )
            self.operations.create_operation(operation)
        self.operations.save_lifecycle(
            AccountLifecycle(
                user_id=user_id,
                state=AccountState.DELETION_REQUESTED,
                current_operation_id=operation.operation_id,
                updated_at=requested_at,
            )
        )
        _log("deletion_requested", operation)
        return operation, True

    def mark_dispatch_failed(
        self, user_id: str, operation_id: str, *, now: datetime | None = None
    ) -> AccountOperation:
        operation = self._required(user_id, operation_id)
        current = _utc(now or datetime.now(timezone.utc))
        operation = operation.model_copy(
            update={
                "status": AccountOperationStatus.FAILED,
                "safe_error": "Account deletion was recorded but processing could not start.",
                "updated_at": current,
            }
        )
        self.operations.save_operation(operation)
        self.operations.save_lifecycle(
            AccountLifecycle(
                user_id=user_id,
                state=AccountState.DELETION_REQUIRES_ATTENTION,
                current_operation_id=operation.operation_id,
                updated_at=current,
            )
        )
        self.reconciliation.detect(
            user_id=user_id,
            domain=ReconciliationDomain.ACCOUNT_DELETION,
            entity_type="account_operation",
            entity_id=operation.operation_id,
            issue_type="incomplete_dispatch",
            severity=ReconciliationSeverity.CRITICAL,
            retryable=True,
            correlation_id=operation.operation_id,
            now=current,
        )
        _log("deletion_failed", operation, step="dispatch")
        return operation

    def process_deletion(self, user_id: str, operation_id: str, *, now: datetime | None = None) -> AccountOperation:
        operation = self.operations.get_operation(user_id, operation_id)
        if operation is None and self.operations.has_deletion_receipt(operation_id):
            current = _utc(now or datetime.now(timezone.utc))
            return AccountOperation(
                operation_id=operation_id,
                user_id=user_id,
                operation_type=AccountOperationType.DELETION,
                status=AccountOperationStatus.COMPLETE,
                created_at=current,
                updated_at=current,
            )
        if operation is None:
            raise KeyError("Account operation not found.")
        if operation.operation_type != AccountOperationType.DELETION:
            raise ValueError("Operation is not account deletion.")
        if operation.status == AccountOperationStatus.COMPLETE:
            return operation
        current = _utc(now or datetime.now(timezone.utc))
        operation = operation.model_copy(
            update={"status": AccountOperationStatus.IN_PROGRESS, "updated_at": current, "safe_error": None}
        )
        self.operations.save_operation(operation)
        self.operations.save_lifecycle(
            AccountLifecycle(
                user_id=user_id,
                state=AccountState.DELETING,
                current_operation_id=operation.operation_id,
                updated_at=current,
            )
        )

        for store in self.inventory.deletion_stores:
            step = _step(operation, store.name)
            if step.status == AccountStepStatus.COMPLETE and store.count_reader(user_id, 1) == 0:
                continue
            operation = _replace_step(
                operation,
                step.model_copy(
                    update={
                        "status": AccountStepStatus.IN_PROGRESS,
                        "attempt_count": step.attempt_count + 1,
                        "updated_at": current,
                        "safe_error": None,
                    }
                ),
            )
            self.operations.save_operation(operation)
            try:
                for _ in range(self.max_batches_per_step):
                    if store.count_reader(user_id, 1) == 0:
                        break
                    store.delete_action(user_id, self.batch_size)
                remaining = store.count_reader(user_id, self.batch_size)
                if remaining:
                    raise RuntimeError("Bounded cleanup left additional rows.")
            except Exception:
                return self._fail(operation, store.name, current)
            operation = _replace_step(
                operation,
                _step(operation, store.name).model_copy(
                    update={"status": AccountStepStatus.COMPLETE, "updated_at": current}
                ),
            )
            self.operations.save_operation(operation)
            _log("deletion_step", operation, step=store.name)

        verification = self.verify(user_id, operation.operation_id, now=current)
        if not verification.complete:
            return self._fail(operation, "verification", current)
        operation = _replace_step(
            operation,
            _step(operation, "verification").model_copy(
                update={"status": AccountStepStatus.COMPLETE, "updated_at": current}
            ),
        )
        self.operations.save_operation(operation)

        try:
            self.identity_cleaner(user_id)
        except Exception:
            return self._fail(operation, "cognito_identity", current)
        operation = _replace_step(
            operation,
            _step(operation, "cognito_identity").model_copy(
                update={"status": AccountStepStatus.COMPLETE, "updated_at": current}
            ),
        ).model_copy(update={"status": AccountOperationStatus.COMPLETE, "updated_at": current})
        _log("deletion_completed", operation)
        # The user-scoped control row is removed only after data and identity cleanup
        # succeed. The returned object is safe status and is not retained as user data.
        self.operations.save_deletion_receipt(operation.operation_id, current)
        self.operations.delete_for_user(user_id)
        return operation

    def verify(
        self, user_id: str, operation_id: str, *, now: datetime | None = None
    ) -> AccountDeletionVerification:
        self._required(user_id, operation_id)
        counts = {
            store.name: max(0, int(store.count_reader(user_id, self.batch_size)))
            for store in self.inventory.stores
        }
        return AccountDeletionVerification(
            operation_id=operation_id,
            complete=all(count == 0 for count in counts.values()),
            counts=counts,
            checked_at=_utc(now or datetime.now(timezone.utc)),
        )

    def _fail(self, operation: AccountOperation, step_name: str, now: datetime) -> AccountOperation:
        step = _step(operation, step_name)
        operation = _replace_step(
            operation,
            step.model_copy(
                update={
                    "status": AccountStepStatus.FAILED,
                    "safe_error": "Cleanup is incomplete and will be retried safely.",
                    "updated_at": now,
                }
            ),
        ).model_copy(
            update={
                "status": AccountOperationStatus.FAILED,
                "safe_error": "Account deletion requires additional cleanup.",
                "updated_at": now,
            }
        )
        self.operations.save_operation(operation)
        self.operations.save_lifecycle(
            AccountLifecycle(
                user_id=operation.user_id,
                state=AccountState.DELETION_REQUIRES_ATTENTION,
                current_operation_id=operation.operation_id,
                updated_at=now,
            )
        )
        self.reconciliation.detect(
            user_id=operation.user_id,
            domain=ReconciliationDomain.ACCOUNT_DELETION,
            entity_type="account_operation",
            entity_id=operation.operation_id,
            issue_type=f"incomplete_{step_name}",
            severity=ReconciliationSeverity.CRITICAL,
            retryable=True,
            correlation_id=operation.operation_id,
            now=now,
        )
        _log("deletion_failed", operation, step=step_name)
        return operation

    def _required(self, user_id: str, operation_id: str) -> AccountOperation:
        operation = self.operations.get_operation(user_id, operation_id)
        if operation is None:
            raise KeyError("Account operation not found.")
        return operation


def _step(operation: AccountOperation, name: str) -> AccountOperationStep:
    return next(step for step in operation.steps if step.name == name)


def _replace_step(operation: AccountOperation, replacement: AccountOperationStep) -> AccountOperation:
    return operation.model_copy(
        update={"steps": [replacement if step.name == replacement.name else step for step in operation.steps]}
    )


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _log(event: str, operation: AccountOperation, **extra) -> None:
    logger.info(
        json.dumps(
            {
                "event": event,
                "operation_id": operation.operation_id,
                "status": operation.status.value,
                **extra,
            }
        )
    )
