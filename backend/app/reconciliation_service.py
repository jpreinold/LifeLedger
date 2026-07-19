from __future__ import annotations

import hashlib
import json
import logging
import re
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.reconciliation import (
    ReconciliationBatchResult,
    ReconciliationDomain,
    ReconciliationIssue,
    ReconciliationSeverity,
    ReconciliationStatus,
)
from app.reconciliation_repository import ReconciliationRepository

Repairer = Callable[[ReconciliationIssue], str | None]

logger = logging.getLogger(__name__)


class ReconciliationService:
    def __init__(
        self,
        repository: ReconciliationRepository,
        repairers: dict[tuple[ReconciliationDomain, str], Repairer] | None = None,
        *,
        max_attempts: int = 5,
        base_backoff_seconds: int = 300,
        resolved_retention_days: int = 90,
    ):
        self.repository = repository
        self.repairers = repairers or {}
        self.max_attempts = max_attempts
        self.base_backoff_seconds = base_backoff_seconds
        self.resolved_retention_days = resolved_retention_days

    def detect(
        self,
        *,
        user_id: str,
        domain: ReconciliationDomain,
        entity_type: str,
        entity_id: str,
        issue_type: str,
        severity: ReconciliationSeverity = ReconciliationSeverity.MEDIUM,
        retryable: bool = True,
        correlation_id: str | None = None,
        now: datetime | None = None,
    ) -> tuple[ReconciliationIssue, bool]:
        detected_at = _utc(now or datetime.now(timezone.utc))
        reconciliation_id = self.issue_id(user_id, domain, entity_type, entity_id, issue_type)
        issue = ReconciliationIssue(
            reconciliation_id=reconciliation_id,
            user_id=user_id,
            domain=domain,
            entity_type=entity_type,
            entity_id=entity_id,
            issue_type=issue_type,
            detected_at=detected_at,
            status=ReconciliationStatus.PENDING,
            severity=severity,
            retryable=retryable,
            next_retry_at=detected_at if retryable else None,
            correlation_id=_safe_correlation_id(correlation_id) if correlation_id else str(uuid4()),
            safe_summary=f"{domain.value} reconciliation detected for {entity_type}: {issue_type}.",
        )
        saved, created = self.repository.create_or_get(issue)
        if created:
            _log("reconciliation_detected", saved)
        return saved, created

    @staticmethod
    def issue_id(
        user_id: str,
        domain: ReconciliationDomain,
        entity_type: str,
        entity_id: str,
        issue_type: str,
    ) -> str:
        identity = "\x1f".join((user_id, domain.value, entity_type, entity_id, issue_type))
        return hashlib.sha256(identity.encode("utf-8")).hexdigest()

    def resolve_matching(
        self,
        *,
        user_id: str,
        domain: ReconciliationDomain,
        entity_type: str,
        entity_id: str,
        issue_type: str,
        resolution: str,
        now: datetime | None = None,
    ) -> ReconciliationIssue | None:
        reconciliation_id = self.issue_id(user_id, domain, entity_type, entity_id, issue_type)
        issue = self.repository.get(reconciliation_id)
        if issue is None:
            return None
        return self.resolve(reconciliation_id, resolution, now=now)

    def retry_one(
        self,
        reconciliation_id: str,
        *,
        expected_user_id: str | None = None,
        now: datetime | None = None,
    ) -> ReconciliationIssue:
        issue = self.repository.get(reconciliation_id)
        if issue is None or (expected_user_id is not None and issue.user_id != expected_user_id):
            raise KeyError("Reconciliation issue not found.")
        if issue.status in {ReconciliationStatus.RESOLVED, ReconciliationStatus.IGNORED}:
            return issue
        if not issue.retryable:
            return self.require_attention(issue, "Verified manual repair is required.", now=now)

        attempted_at = _utc(now or datetime.now(timezone.utc))
        issue = issue.model_copy(
            update={
                "status": ReconciliationStatus.RETRYING,
                "last_attempt_at": attempted_at,
                "attempt_count": issue.attempt_count + 1,
                "next_retry_at": None,
            }
        )
        self.repository.save(issue)
        _log("reconciliation_retry", issue)
        repairer = self.repairers.get((issue.domain, issue.issue_type))
        if repairer is None:
            return self.require_attention(issue, "No automatic repair is registered.", now=attempted_at)

        try:
            resolution = repairer(issue) or "Verified idempotent repair completed."
        except Exception:
            if issue.attempt_count >= self.max_attempts:
                return self.require_attention(issue, "Automatic repair attempts were exhausted.", now=attempted_at)
            delay = min(self.base_backoff_seconds * (2 ** (issue.attempt_count - 1)), 24 * 60 * 60)
            issue = issue.model_copy(
                update={
                    "status": ReconciliationStatus.RETRYING,
                    "next_retry_at": attempted_at + timedelta(seconds=delay),
                    "resolution": "Automatic repair failed; a bounded retry is scheduled.",
                }
            )
            self.repository.save(issue)
            _log("reconciliation_retry_failed", issue)
            return issue
        # Account deletion may intentionally remove its own user-scoped issue as
        # the last data-cleanup step. Never recreate that deleted row merely to
        # record a terminal operational status.
        if self.repository.get(issue.reconciliation_id) is None:
            return issue.model_copy(
                update={
                    "status": ReconciliationStatus.RESOLVED,
                    "resolution": _safe_resolution(resolution),
                    "resolved_at": attempted_at,
                    "next_retry_at": None,
                }
            )
        return self.resolve(issue.reconciliation_id, resolution, now=attempted_at)

    def process_due(
        self,
        *,
        now: datetime | None = None,
        limit: int = 25,
        dry_run: bool = False,
    ) -> ReconciliationBatchResult:
        if limit < 1 or limit > 100:
            raise ValueError("Reconciliation batch limit must be between 1 and 100.")
        issues = self.repository.list_due(_utc(now or datetime.now(timezone.utc)), limit=limit)
        if dry_run:
            return ReconciliationBatchResult(
                considered=len(issues), attempted=0, resolved=0, failed=0, requires_attention=0, dry_run=True
            )

        resolved = failed = attention = 0
        for issue in issues:
            try:
                updated = self.retry_one(issue.reconciliation_id, now=now)
            except Exception:
                failed += 1
                continue
            if updated.status == ReconciliationStatus.RESOLVED:
                resolved += 1
            elif updated.status == ReconciliationStatus.REQUIRES_ATTENTION:
                attention += 1
            else:
                failed += 1
        return ReconciliationBatchResult(
            considered=len(issues),
            attempted=len(issues),
            resolved=resolved,
            failed=failed,
            requires_attention=attention,
        )

    def resolve(self, reconciliation_id: str, resolution: str, *, now: datetime | None = None) -> ReconciliationIssue:
        issue = self._required(reconciliation_id)
        if issue.status == ReconciliationStatus.RESOLVED:
            return issue
        resolved_at = _utc(now or datetime.now(timezone.utc))
        updated = issue.model_copy(
            update={
                "status": ReconciliationStatus.RESOLVED,
                "resolution": _safe_resolution(resolution),
                "resolved_at": resolved_at,
                "next_retry_at": None,
                "expires_at": int((resolved_at + timedelta(days=self.resolved_retention_days)).timestamp()),
            }
        )
        self.repository.save(updated)
        _log("reconciliation_resolved", updated)
        return updated

    def ignore(self, reconciliation_id: str, reason: str, *, now: datetime | None = None) -> ReconciliationIssue:
        if not reason.strip():
            raise ValueError("An ignore reason is required.")
        issue = self._required(reconciliation_id)
        updated = issue.model_copy(
            update={
                "status": ReconciliationStatus.IGNORED,
                "resolution": _safe_resolution(reason),
                "resolved_at": _utc(now or datetime.now(timezone.utc)),
                "next_retry_at": None,
                "expires_at": None,
            }
        )
        return self.repository.save(updated)

    def require_attention(
        self, issue: ReconciliationIssue, resolution: str, *, now: datetime | None = None
    ) -> ReconciliationIssue:
        updated = issue.model_copy(
            update={
                "status": ReconciliationStatus.REQUIRES_ATTENTION,
                "resolution": _safe_resolution(resolution),
                "next_retry_at": None,
                "resolved_at": None,
                "expires_at": None,
            }
        )
        self.repository.save(updated)
        _log("reconciliation_requires_attention", updated)
        return updated

    def _required(self, reconciliation_id: str) -> ReconciliationIssue:
        issue = self.repository.get(reconciliation_id)
        if issue is None:
            raise KeyError("Reconciliation issue not found.")
        return issue


def _safe_resolution(value: str) -> str:
    sanitized = " ".join(value.split())
    if re.fullmatch(r"[a-z0-9][a-z0-9_-]{2,79}", sanitized):
        return sanitized
    safe_messages = {
        "Verified manual repair is required.",
        "No automatic repair is registered.",
        "Automatic repair attempts were exhausted.",
        "Automatic repair failed; a bounded retry is scheduled.",
        "Verified idempotent repair completed.",
        "Search projection was rebuilt and verified.",
        "Account deletion cleanup was resumed and verified.",
    }
    return sanitized if sanitized in safe_messages else "Verified operational disposition recorded."


def _safe_correlation_id(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _log(event: str, issue: ReconciliationIssue) -> None:
    logger.info(
        json.dumps(
            {
                "event": event,
                "operation_id": issue.reconciliation_id,
                "domain": issue.domain.value,
                "entity_type": issue.entity_type,
                "entity_id": issue.entity_id,
                "status": issue.status.value,
                "retryable": issue.retryable,
                "attempt_count": issue.attempt_count,
                "correlation_id": issue.correlation_id,
            }
        )
    )
