import json
import logging

from app.account_runtime import get_account_deletion_service, get_account_export_service
from app.account_models import AccountOperationStatus


logger = logging.getLogger(__name__)


def handler(event, _context):
    failures = []
    for record in event.get("Records", []):
        message_id = record.get("messageId", "unknown")
        try:
            payload = json.loads(record.get("body", "{}"))
            operation_type = payload["operation_type"]
            user_id = payload["user_id"]
            operation_id = payload["operation_id"]
            if operation_type == "export":
                result = get_account_export_service().process_export(user_id, operation_id)
            elif operation_type == "deletion":
                result = get_account_deletion_service().process_deletion(user_id, operation_id)
            else:
                raise ValueError("Unsupported account operation type.")
            if result.status == AccountOperationStatus.FAILED:
                failures.append({"itemIdentifier": message_id})
        except Exception:
            logger.error("account_operation_failed", extra={"message_id": message_id})
            failures.append({"itemIdentifier": message_id})
    return {"batchItemFailures": failures}
