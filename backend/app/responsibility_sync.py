from dataclasses import dataclass
from datetime import date, datetime
from uuid import NAMESPACE_URL, uuid5

from app.models import DynamicRecordField, Record, Reminder
from app.records_repository import RecordRepository
from app.schemas import DynamicFieldType, RecordStatus, ResponsibilityWorkflowId


@dataclass(frozen=True)
class ResponsibilityDateTarget:
    key: str
    label: str
    record_field: str | None = None
    dynamic_field_key: str | None = None
    display_order: int = 190


WORKFLOW_DATE_TARGETS: dict[ResponsibilityWorkflowId, ResponsibilityDateTarget] = {
    ResponsibilityWorkflowId.PASSPORT_EXPIRATION: ResponsibilityDateTarget(
        key="expiration_date",
        label="Expiration date",
        record_field="expiration_date",
    ),
    ResponsibilityWorkflowId.VEHICLE_REGISTRATION: ResponsibilityDateTarget(
        key="registration_expiration",
        label="Registration expiration",
        dynamic_field_key="registration_expiration",
        display_order=185,
    ),
    ResponsibilityWorkflowId.PET_VACCINATION: ResponsibilityDateTarget(
        key="next_vaccination_due_date",
        label="Next vaccination due",
        dynamic_field_key="next_vaccination_due_date",
        display_order=150,
    ),
    ResponsibilityWorkflowId.SUBSCRIPTION_RENEWAL: ResponsibilityDateTarget(
        key="renewal_date",
        label="Renewal date",
        record_field="renewal_date",
    ),
}


class ItemDateConflict(Exception):
    pass


def resolve_date_target(reminder: Reminder, record: Record | None = None) -> ResponsibilityDateTarget | None:
    if reminder.workflow_id is not None:
        return WORKFLOW_DATE_TARGETS.get(reminder.workflow_id)
    if record is None:
        return None
    if record.renewal_date == reminder.due_date:
        return ResponsibilityDateTarget(key="renewal_date", label="Renewal date", record_field="renewal_date")
    if record.expiration_date == reminder.due_date:
        return ResponsibilityDateTarget(key="expiration_date", label="Expiration date", record_field="expiration_date")
    return None


def resolve_date_target_for_key(key: str | None) -> ResponsibilityDateTarget | None:
    if not key:
        return None
    for target in WORKFLOW_DATE_TARGETS.values():
        if target.key == key:
            return target
    if key == "renewal_date":
        return ResponsibilityDateTarget(key=key, label="Renewal date", record_field=key)
    if key == "expiration_date":
        return ResponsibilityDateTarget(key=key, label="Expiration date", record_field=key)
    return None


def synchronize_item_date(
    record_repo: RecordRepository,
    record: Record,
    target: ResponsibilityDateTarget,
    *,
    previous_due_date: date,
    next_due_date: date,
    now: datetime,
) -> Record:
    if record.status == RecordStatus.ARCHIVED:
        raise ItemDateConflict("The connected item is archived.")

    if target.record_field:
        current = getattr(record, target.record_field)
        _assert_safe_transition(current, previous_due_date, next_due_date, target.label)
        if current == next_due_date:
            return record
        return record_repo.update_record(
            record.model_copy(update={target.record_field: next_due_date, "updated_at": now})
        )

    if not target.dynamic_field_key:
        return record
    fields = list(record.dynamic_fields)
    existing_index = next(
        (index for index, field in enumerate(fields) if field.key == target.dynamic_field_key),
        None,
    )
    if existing_index is None:
        fields.append(
            DynamicRecordField(
                field_id=str(uuid5(NAMESPACE_URL, f"lifeledger:record-field:{record.id}:{target.dynamic_field_key}")),
                key=target.dynamic_field_key,
                label=target.label,
                field_type=DynamicFieldType.DATE,
                value=next_due_date.isoformat(),
                has_value=True,
                display_order=target.display_order,
                created_at=now,
                updated_at=now,
            )
        )
    else:
        existing = fields[existing_index]
        current = date.fromisoformat(str(existing.value)) if existing.value else None
        _assert_safe_transition(current, previous_due_date, next_due_date, target.label)
        if current == next_due_date:
            return record
        fields[existing_index] = existing.model_copy(
            update={"value": next_due_date.isoformat(), "has_value": True, "updated_at": now}
        )
    return record_repo.update_record(record.model_copy(update={"dynamic_fields": fields, "updated_at": now}))


def current_item_date(record: Record, target: ResponsibilityDateTarget) -> date | None:
    if target.record_field:
        return getattr(record, target.record_field)
    if target.dynamic_field_key:
        field = next((item for item in record.dynamic_fields if item.key == target.dynamic_field_key), None)
        if field and field.value:
            try:
                return date.fromisoformat(str(field.value))
            except ValueError:
                return None
    return None


def _assert_safe_transition(
    current: date | None,
    previous_due_date: date,
    next_due_date: date,
    label: str,
) -> None:
    if current is None or current in {previous_due_date, next_due_date}:
        return
    raise ItemDateConflict(
        f"The connected item's {label.lower()} is {current.isoformat()}, so it was not overwritten."
    )
