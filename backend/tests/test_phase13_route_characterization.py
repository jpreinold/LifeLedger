"""Characterization tests that protect the Phase 12 HTTP surface during router extraction."""

from pathlib import Path

from app.main import app


EXPECTED_ROUTE_METHODS = {
    ("GET", "/health"),
    ("GET", "/search"),
    ("GET", "/saved-views"),
    ("POST", "/saved-views"),
    ("GET", "/saved-views/{saved_view_id}"),
    ("PATCH", "/saved-views/{saved_view_id}"),
    ("DELETE", "/saved-views/{saved_view_id}"),
    ("GET", "/alerts"),
    ("GET", "/records"),
    ("POST", "/records"),
    ("GET", "/records/{record_id}"),
    ("PUT", "/records/{record_id}"),
    ("DELETE", "/records/{record_id}"),
    ("GET", "/records/{record_id}/activity"),
    ("POST", "/records/{record_id}/archive"),
    ("POST", "/records/{record_id}/restore"),
    ("POST", "/records/{record_id}/fields"),
    ("PUT", "/records/{record_id}/fields/{field_id}"),
    ("GET", "/records/{record_id}/fields/{field_id}/reveal"),
    ("DELETE", "/records/{record_id}/fields/{field_id}"),
    ("GET", "/records/{record_id}/protected/status"),
    ("PUT", "/records/{record_id}/protected"),
    ("PATCH", "/records/{record_id}/protected"),
    ("GET", "/records/{record_id}/protected"),
    ("DELETE", "/records/{record_id}/protected"),
    ("GET", "/records/{record_id}/links"),
    ("POST", "/records/{record_id}/links"),
    ("DELETE", "/records/{record_id}/links/{link_id}"),
    ("GET", "/relationships/candidates"),
    ("POST", "/relationships"),
    ("GET", "/relationships/{relationship_id}"),
    ("PATCH", "/relationships/{relationship_id}"),
    ("DELETE", "/relationships/{relationship_id}"),
    ("GET", "/records/{record_id}/attachments"),
    ("POST", "/records/{record_id}/attachments/upload-intent"),
    ("POST", "/records/{record_id}/attachments/{attachment_id}/complete"),
    ("GET", "/records/{record_id}/attachments/{attachment_id}"),
    ("POST", "/records/{record_id}/attachments/{attachment_id}/refresh-status"),
    ("POST", "/records/{record_id}/attachments/{attachment_id}/download-url"),
    ("POST", "/records/{record_id}/attachments/{attachment_id}/preview-url"),
    ("DELETE", "/records/{record_id}/attachments/{attachment_id}"),
    ("GET", "/preferences/digest"),
    ("PUT", "/preferences/digest"),
    ("GET", "/integrations/google-calendar/status"),
    ("POST", "/integrations/google-calendar/connect"),
    ("POST", "/integrations/google-calendar/callback"),
    ("GET", "/integrations/google-calendar/calendars"),
    ("PUT", "/integrations/google-calendar/calendar"),
    ("DELETE", "/integrations/google-calendar/disconnect"),
    ("GET", "/push/config"),
    ("GET", "/push/status"),
    ("POST", "/push/test"),
    ("GET", "/push/subscriptions"),
    ("POST", "/push/subscriptions"),
    ("DELETE", "/push/subscriptions/{subscription_id}"),
    ("GET", "/reminders"),
    ("POST", "/reminders"),
    ("GET", "/reminders/{reminder_id}"),
    ("PUT", "/reminders/{reminder_id}"),
    ("DELETE", "/reminders/{reminder_id}"),
    ("POST", "/reminders/{reminder_id}/alert/dismiss"),
    ("POST", "/reminders/{reminder_id}/alert/snooze"),
    ("POST", "/reminders/{reminder_id}/calendar-sync/enable"),
    ("POST", "/reminders/{reminder_id}/calendar-sync/disable"),
    ("POST", "/reminders/{reminder_id}/snooze"),
    ("POST", "/reminders/{reminder_id}/snooze/clear"),
    ("POST", "/reminders/{reminder_id}/renew"),
    ("POST", "/reminders/{reminder_id}/complete"),
    ("POST", "/reminders/{reminder_id}/reopen"),
    ("GET", "/reminders/{reminder_id}/history"),
    ("POST", "/reminders/{reminder_id}/history/evidence"),
    ("POST", "/reminders/{reminder_id}/history/reconcile"),
    ("POST", "/responsibility-history/reconcile"),
    ("GET", "/responsibility-events/{event_id}"),
    ("GET", "/reminders/{reminder_id}/links"),
    ("DELETE", "/reminders/{reminder_id}/links/{link_id}"),
}


def test_phase12_route_surface_is_preserved():
    actual = {
        (method.upper(), path)
        for path, operations in app.openapi()["paths"].items()
        for method in operations
        if method.upper() not in {"HEAD", "OPTIONS", "PARAMETERS"}
    }

    assert EXPECTED_ROUTE_METHODS <= actual


def test_openapi_operation_ids_are_unique():
    operation_ids = [
        operation["operationId"]
        for path in app.openapi()["paths"].values()
        for operation in path.values()
        if "operationId" in operation
    ]

    assert len(operation_ids) == len(set(operation_ids))


def test_router_modules_own_handlers_without_importing_the_composition_root():
    app_root = Path(__file__).resolve().parents[1] / "app"
    main_source = (app_root / "main.py").read_text(encoding="utf-8")
    assert len(main_source.splitlines()) < 250

    for name in (
        "records",
        "reminders",
        "lifecycle",
        "documents",
        "relationships",
        "search",
        "preferences",
        "integrations",
        "push",
        "account",
        "health",
    ):
        source = (app_root / "routers" / f"{name}.py").read_text(encoding="utf-8")
        assert "from app.main" not in source
        assert "@" in source and "router" in source
