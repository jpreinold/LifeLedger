from datetime import date, timedelta

from app.maintenance import (
    add_maintenance_interval,
    advance_maintenance_details,
    get_maintenance_computed_label,
    get_maintenance_due_date,
    get_maintenance_next_due_label,
    get_maintenance_schedule_label,
    get_maintenance_status_label,
    prepare_maintenance_details,
)
from app.schemas import MaintenanceDetails, MaintenanceIntervalUnit


def test_maintenance_due_date_calculates_from_last_completed_and_interval():
    details = MaintenanceDetails(
        item_name="Change HVAC filter",
        maintenance_area="home",
        last_completed_date=date(2026, 5, 1),
        interval_value=3,
        interval_unit="months",
    )

    prepared = prepare_maintenance_details(details)

    assert prepared.next_due_date == date(2026, 8, 1)
    assert get_maintenance_due_date(prepared) == date(2026, 8, 1)
    assert get_maintenance_schedule_label(prepared) == "Every 3 months"
    assert get_maintenance_next_due_label(prepared) == "Next due Aug 1"


def test_maintenance_status_labels_handle_due_and_overdue_dates():
    today = date(2026, 7, 5)

    assert get_maintenance_status_label(
        MaintenanceDetails(item_name="Smoke detectors", next_due_date=today),
        today=today,
    ) == "Due today"
    assert get_maintenance_status_label(
        MaintenanceDetails(item_name="Smoke detectors", next_due_date=today + timedelta(days=1)),
        today=today,
    ) == "Due tomorrow"
    assert get_maintenance_status_label(
        MaintenanceDetails(item_name="Smoke detectors", next_due_date=today + timedelta(days=6)),
        today=today,
    ) == "Due in 6 days"
    assert get_maintenance_status_label(
        MaintenanceDetails(item_name="Smoke detectors", next_due_date=today - timedelta(days=3)),
        today=today,
    ) == "Overdue by 3 days"


def test_maintenance_computed_label_combines_schedule_and_status():
    details = MaintenanceDetails(
        item_name="Heartworm medicine",
        maintenance_area="pet",
        interval_value=1,
        interval_unit="months",
        next_due_date=date(2026, 7, 5),
    )

    assert get_maintenance_computed_label(details, today=date(2026, 7, 5)) == "Every month \u2022 Due today"


def test_maintenance_completion_advances_from_completion_date():
    details = MaintenanceDetails(
        item_name="Clean dryer vent",
        maintenance_area="home",
        last_completed_date=date(2026, 1, 1),
        interval_value=1,
        interval_unit="years",
        next_due_date=date(2027, 1, 1),
    )

    advanced = advance_maintenance_details(details, date(2026, 9, 1))

    assert advanced.last_completed_date == date(2026, 9, 1)
    assert advanced.next_due_date == date(2027, 9, 1)


def test_maintenance_interval_adds_months_with_end_of_month_clamping():
    assert add_maintenance_interval(date(2026, 1, 31), 1, MaintenanceIntervalUnit.MONTHS) == date(2026, 2, 28)