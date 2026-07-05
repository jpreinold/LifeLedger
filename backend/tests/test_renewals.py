from datetime import date, timedelta

from app.renewals import get_renewal_computed_label, get_renewal_status_label, get_renewal_window_label
from app.schemas import RenewalDetails, RenewalKind


def test_renewal_status_labels_handle_relative_days():
    today = date(2026, 7, 5)

    assert get_renewal_status_label(
        RenewalDetails(item_name="Car tag", renewal_kind=RenewalKind.RENEWAL, renewal_date=today + timedelta(days=42)),
        today=today,
    ) == "Renews in 42 days"
    assert get_renewal_status_label(
        RenewalDetails(item_name="Car tag", renewal_kind=RenewalKind.RENEWAL, renewal_date=today),
        today=today,
    ) == "Renews today"
    assert get_renewal_status_label(
        RenewalDetails(item_name="Car tag", renewal_kind=RenewalKind.RENEWAL, renewal_date=today - timedelta(days=3)),
        today=today,
    ) == "Renewal overdue by 3 days"


def test_expiration_status_labels_handle_past_and_future_dates():
    today = date(2026, 7, 5)

    assert get_renewal_status_label(
        RenewalDetails(item_name="Passport", renewal_kind=RenewalKind.EXPIRATION, expiration_date=today + timedelta(days=86)),
        today=today,
    ) == "Expires in 86 days"
    assert get_renewal_status_label(
        RenewalDetails(item_name="Passport", renewal_kind=RenewalKind.EXPIRATION, expiration_date=today),
        today=today,
    ) == "Expires today"
    assert get_renewal_status_label(
        RenewalDetails(item_name="Passport", renewal_kind=RenewalKind.EXPIRATION, expiration_date=today - timedelta(days=12)),
        today=today,
    ) == "Expired 12 days ago"


def test_review_and_window_labels_stay_simple():
    details = RenewalDetails(
        item_name="Home insurance",
        renewal_kind=RenewalKind.REVIEW,
        renewal_date=date(2027, 6, 1),
        renewal_window_days=31,
        review_lead_days=30,
    )

    assert get_renewal_computed_label(details, today=date(2026, 7, 5)) == "Review 30 days before renewal"
    assert get_renewal_window_label(details) == "Renewal window starts May 1"


def test_unknown_renewal_date_gets_clear_label():
    details = RenewalDetails(item_name="Mystery renewal", renewal_kind=RenewalKind.RENEWAL)

    assert get_renewal_status_label(details, today=date(2026, 7, 5)) == "Renewal date unknown"
    assert get_renewal_computed_label(details, today=date(2026, 7, 5)) == "Renewal date unknown"
