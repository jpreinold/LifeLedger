from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from uuid import NAMESPACE_URL, uuid5

from app.models import DynamicRecordField, Record
from app.records_repository import RecordRepository
from app.schemas import DynamicFieldType, LinkedEntityType, RecordStatus, RecordType, normalize_dynamic_field_value
from app.search_service import SearchProjectionService


class ItemNotFound(KeyError):
    pass


class ItemDetailNotAllowed(ValueError):
    pass


class ItemDetailConflict(ValueError):
    pass


@dataclass(frozen=True)
class DetailSpec:
    key: str
    label: str
    field_type: DynamicFieldType
    record_field: str | None = None
    select_options: tuple[str, ...] = ()


def _detail(
    key: str,
    label: str,
    field_type: DynamicFieldType = DynamicFieldType.SHORT_TEXT,
    *,
    record_field: str | None = None,
    select_options: tuple[str, ...] = (),
) -> DetailSpec:
    return DetailSpec(key, label, field_type, record_field, select_options)


COMMON_DETAILS = {
    "subtitle": _detail("subtitle", "Description", record_field="subtitle"),
    "owner_name": _detail("owner_name", "Owner", record_field="owner_name"),
    "provider_or_brand": _detail("provider_or_brand", "Provider or brand", record_field="provider_or_brand"),
    "start_date": _detail("start_date", "Start date", DynamicFieldType.DATE, record_field="start_date"),
    "issue_date": _detail("issue_date", "Issue date", DynamicFieldType.DATE, record_field="issue_date"),
    "expiration_date": _detail("expiration_date", "Expiration date", DynamicFieldType.DATE, record_field="expiration_date"),
    "purchase_date": _detail("purchase_date", "Purchase date", DynamicFieldType.DATE, record_field="purchase_date"),
    "renewal_date": _detail("renewal_date", "Renewal date", DynamicFieldType.DATE, record_field="renewal_date"),
    "location_hint": _detail("location_hint", "Location", record_field="location_hint"),
}


ITEM_DETAIL_SPECS: dict[RecordType, dict[str, DetailSpec]] = {
    RecordType.GENERAL: dict(COMMON_DETAILS),
    RecordType.PASSPORT: dict(COMMON_DETAILS),
    RecordType.DRIVER_LICENSE: dict(COMMON_DETAILS),
    RecordType.VEHICLE: {
        **COMMON_DETAILS,
        "model": _detail("model", "Model"),
        "year": _detail("year", "Year", DynamicFieldType.NUMBER),
        "color": _detail("color", "Color"),
        "mileage": _detail("mileage", "Mileage", DynamicFieldType.NUMBER),
        "registration_expiration": _detail("registration_expiration", "Registration expiration", DynamicFieldType.DATE),
        "registration_authority": _detail("registration_authority", "Registration state or authority"),
        "purchase_price": _detail("purchase_price", "Purchase price", DynamicFieldType.MONEY),
    },
    RecordType.INSURANCE: {**COMMON_DETAILS, "coverage": _detail("coverage", "Coverage")},
    RecordType.APPLIANCE: {**COMMON_DETAILS, "model_number": _detail("model_number", "Model number")},
    RecordType.PET: {
        **COMMON_DETAILS,
        "breed": _detail("breed", "Breed"),
        "birthday": _detail("birthday", "Birthday", DynamicFieldType.DATE),
        "vet": _detail("vet", "Veterinarian"),
        "next_vaccination_due_date": _detail("next_vaccination_due_date", "Next vaccination due", DynamicFieldType.DATE),
    },
    RecordType.HOME: {
        **COMMON_DETAILS,
        "home_type": _detail(
            "home_type",
            "Home type",
            DynamicFieldType.SELECT,
            select_options=("House", "Condo", "Apartment", "Townhouse", "Other"),
        ),
        "year_built": _detail("year_built", "Year built", DynamicFieldType.NUMBER),
    },
    RecordType.SUBSCRIPTION: {
        **COMMON_DETAILS,
        "billing_cycle": _detail(
            "billing_cycle",
            "Billing frequency",
            DynamicFieldType.SELECT,
            select_options=("Monthly", "Quarterly", "Yearly", "Custom or non-recurring"),
        ),
        "cost": _detail("cost", "Price", DynamicFieldType.MONEY),
        "cancellation_info": _detail("cancellation_info", "Cancellation information", DynamicFieldType.LONG_TEXT),
        "website": _detail("website", "Website", DynamicFieldType.URL),
    },
    RecordType.WARRANTY: {**COMMON_DETAILS, "coverage": _detail("coverage", "Coverage")},
    RecordType.PERSON: {
        "preferred_name": _detail("preferred_name", "Preferred name"),
        # Person birthdays intentionally support either YYYY-MM-DD or --MM-DD.
        "birthday": _detail("birthday", "Birthday"),
        "relationship_context": _detail(
            "relationship_context",
            "Relationship",
            DynamicFieldType.SELECT,
            select_options=("Friend", "Family", "Coworker", "Neighbor", "Other"),
        ),
        "aliases": _detail("aliases", "Aliases"),
    },
}


ITEM_CATEGORIES: dict[RecordType, str] = {
    RecordType.GENERAL: "General",
    RecordType.PASSPORT: "Identity",
    RecordType.DRIVER_LICENSE: "Identity",
    RecordType.VEHICLE: "Transportation",
    RecordType.INSURANCE: "Finance",
    RecordType.APPLIANCE: "Home",
    RecordType.PET: "Family",
    RecordType.HOME: "Property",
    RecordType.SUBSCRIPTION: "Finance",
    RecordType.WARRANTY: "Purchases",
    RecordType.PERSON: "People",
}


def allowed_detail_keys(item_type: RecordType) -> set[str]:
    return set(ITEM_DETAIL_SPECS[item_type])


class ItemApplicationService:
    """The only normal-item mutation boundary used by assistant execution."""

    def __init__(self, records: RecordRepository, search: SearchProjectionService):
        self.records = records
        self.search = search

    def create_item(
        self,
        *,
        user_id: str,
        item_type: RecordType,
        title: str,
        details: dict[str, object],
        idempotency_key: str,
        now: datetime | None = None,
    ) -> tuple[Record, bool]:
        item_id = str(uuid5(NAMESPACE_URL, f"lifeledger:item-service:{user_id}:{idempotency_key}"))
        existing = self.records.get_record(user_id, item_id)
        if existing is not None:
            self.search.sync_entity_observed(user_id, LinkedEntityType.RECORD, existing.id, operation="assistant_item_replay")
            return existing, True

        current = _utc(now)
        record_values: dict[str, object] = {}
        dynamic_fields: list[DynamicRecordField] = []
        for order, (key, value) in enumerate(details.items(), start=1):
            if key == "notes":
                record_values["notes"] = _safe_note(value)
                continue
            spec = self._required_spec(item_type, key)
            normalized = _normalize_detail_value(spec, value)
            if spec.record_field:
                record_values[spec.record_field] = normalized
            else:
                dynamic_fields.append(self._new_dynamic_field(item_id, spec, normalized, order, current))

        item = Record(
            id=item_id,
            user_id=user_id,
            record_type=item_type,
            title=title.strip(),
            category=ITEM_CATEGORIES[item_type],
            dynamic_fields=dynamic_fields,
            created_at=current,
            updated_at=current,
            **record_values,
        )
        saved = self.records.create_record(item)
        self.search.sync_entity_observed(user_id, LinkedEntityType.RECORD, saved.id, operation="assistant_item_create")
        return saved, False

    def update_normal_detail(
        self,
        *,
        user_id: str,
        item_id: str,
        detail_key: str,
        value: object,
        allow_replace: bool = False,
        now: datetime | None = None,
    ) -> tuple[Record, bool]:
        item = self._required_item(user_id, item_id)
        spec = self._required_spec(item.record_type, detail_key)
        normalized = _normalize_detail_value(spec, value)
        current = _utc(now)
        replay = False

        if spec.record_field:
            previous = getattr(item, spec.record_field)
            if _json_value(previous) == _json_value(normalized):
                return item, True
            if previous not in (None, "") and not allow_replace:
                raise ItemDetailConflict(f"{spec.label} already has a different value.")
            updated = item.model_copy(update={spec.record_field: normalized, "updated_at": current})
        else:
            existing = next((field for field in item.dynamic_fields if field.key == detail_key), None)
            if existing is not None:
                if _json_value(existing.value) == _json_value(normalized):
                    return item, True
                if existing.has_value and not allow_replace:
                    raise ItemDetailConflict(f"{spec.label} already has a different value.")
                replacement = existing.model_copy(
                    update={"value": normalized, "has_value": normalized is not None, "updated_at": current}
                )
                fields = [replacement if field.field_id == existing.field_id else field for field in item.dynamic_fields]
            else:
                fields = [*item.dynamic_fields, self._new_dynamic_field(item.id, spec, normalized, len(item.dynamic_fields) + 1, current)]
            updated = item.model_copy(update={"dynamic_fields": fields, "updated_at": current})

        saved = self.records.update_record(updated)
        self.search.sync_entity_observed(user_id, LinkedEntityType.RECORD, saved.id, operation="assistant_item_detail")
        return saved, replay

    def add_safe_note(
        self, *, user_id: str, item_id: str, note: str, now: datetime | None = None
    ) -> tuple[Record, bool]:
        item = self._required_item(user_id, item_id)
        clean = _safe_note(note)
        if item.notes and clean in item.notes.split("\n"):
            return item, True
        combined = clean if not item.notes else f"{item.notes}\n{clean}"
        if len(combined) > 1000:
            raise ItemDetailConflict("This note would exceed the item note limit.")
        saved = self.records.update_record(item.model_copy(update={"notes": combined, "updated_at": _utc(now)}))
        self.search.sync_entity_observed(user_id, LinkedEntityType.RECORD, saved.id, operation="assistant_item_note")
        return saved, False

    def get_item(self, user_id: str, item_id: str) -> Record:
        return self._required_item(user_id, item_id)

    def get_normal_detail(self, user_id: str, item_id: str, detail_key: str):
        """Return one allowlisted normal detail for conflict checks without protected data."""
        item = self._required_item(user_id, item_id)
        spec = self._required_spec(item.record_type, detail_key)
        if spec.record_field:
            return getattr(item, spec.record_field)
        field = next((value for value in item.dynamic_fields if value.key == detail_key), None)
        if field is None or field.is_sensitive or not field.has_value:
            return None
        return field.value

    def _required_item(self, user_id: str, item_id: str) -> Record:
        item = self.records.get_record(user_id, item_id)
        if item is None:
            raise ItemNotFound("Item not found.")
        if item.status == RecordStatus.ARCHIVED:
            raise ItemDetailConflict("Archived items cannot be changed through capture.")
        return item

    @staticmethod
    def _required_spec(item_type: RecordType, key: str) -> DetailSpec:
        spec = ITEM_DETAIL_SPECS.get(item_type, {}).get(key)
        if spec is None:
            raise ItemDetailNotAllowed(f"Detail key '{key}' is not supported for {item_type.value}.")
        return spec

    @staticmethod
    def _new_dynamic_field(
        item_id: str, spec: DetailSpec, value: object, order: int, now: datetime
    ) -> DynamicRecordField:
        field_id = str(uuid5(NAMESPACE_URL, f"lifeledger:item-detail:{item_id}:{spec.key}"))
        return DynamicRecordField(
            field_id=field_id,
            key=spec.key,
            label=spec.label,
            field_type=spec.field_type,
            value=value,
            is_sensitive=False,
            has_value=value is not None,
            display_order=order * 10,
            select_options=list(spec.select_options),
            created_at=now,
            updated_at=now,
        )


def _normalize_detail_value(spec: DetailSpec, value: object):
    if spec.key == "birthday" and spec.field_type == DynamicFieldType.SHORT_TEXT:
        text = str(value).strip()
        if not _valid_person_birthday(text):
            raise ItemDetailNotAllowed("Person birthdays must use YYYY-MM-DD or --MM-DD.")
        return text
    normalized = normalize_dynamic_field_value(spec.field_type, value, list(spec.select_options))
    if spec.record_field and spec.field_type == DynamicFieldType.DATE and isinstance(normalized, str):
        return date.fromisoformat(normalized)
    return normalized


def _valid_person_birthday(value: str) -> bool:
    try:
        if value.startswith("--") and len(value) == 7:
            date(2000, int(value[2:4]), int(value[5:7]))
            return value[4] == "-"
        date.fromisoformat(value)
        return True
    except (TypeError, ValueError):
        return False


def _safe_note(value: object) -> str:
    clean = " ".join(str(value).split())
    if not clean or len(clean) > 500:
        raise ItemDetailNotAllowed("Safe notes must contain 1 to 500 characters.")
    return clean


def _utc(value: datetime | None) -> datetime:
    resolved = value or datetime.now(timezone.utc)
    if resolved.tzinfo is None:
        return resolved.replace(tzinfo=timezone.utc)
    return resolved.astimezone(timezone.utc)


def _json_value(value: object):
    return value.isoformat() if isinstance(value, (date, datetime)) else value
