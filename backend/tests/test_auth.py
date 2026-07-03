import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.auth import get_current_user
from app.config import get_settings


def test_get_current_user_reads_cognito_sub_from_api_gateway_event(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "cognito")
    get_settings.cache_clear()
    request = make_request(
        {
            "requestContext": {
                "authorizer": {
                    "jwt": {
                        "claims": {
                            "sub": "cognito-user-sub",
                        }
                    }
                }
            }
        }
    )

    user = get_current_user(request)

    assert user.user_id == "cognito-user-sub"

    get_settings.cache_clear()


def test_get_current_user_rejects_missing_cognito_sub(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "cognito")
    get_settings.cache_clear()

    with pytest.raises(HTTPException) as error:
        get_current_user(make_request({}))

    assert error.value.status_code == 401

    get_settings.cache_clear()


def make_request(event):
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/reminders",
            "headers": [],
            "aws.event": event,
        }
    )
