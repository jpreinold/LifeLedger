import json
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_sam_template_defaults_to_local_persistence():
    template = (BACKEND_ROOT / "template.yaml").read_text(encoding="utf-8")

    assert "PersistenceMode:" in template
    assert "Default: local" in template
    assert "LifeLedgerHttpApi:" in template
    assert "LifeLedgerLocalHttpApi" not in template
    assert "LifeLedgerCognitoHttpApi" not in template
    assert "PERSISTENCE_MODE: !Ref PersistenceMode" in template
    assert "AUTH_MODE: !Ref AuthMode" in template
    assert "DefaultAuthorizer: CognitoJwtAuthorizer" in template
    assert "Health:" in template
    assert "Authorizer: NONE" in template
    assert "OptionsProxy:" in template
    assert "Method: OPTIONS" in template
    assert "ApiProxy:" in template
    assert "AdminCreateUserConfig:" in template
    assert "AllowAdminCreateUserOnly: true" in template
    assert "LOCAL_DATA_FILE: /tmp/lifeledger-reminders.json" in template
    assert "LOCAL_RECORDS_FILE: /tmp/lifeledger-records.json" in template
    assert "LOCAL_PREFERENCES_FILE: /tmp/lifeledger-preferences.json" in template
    assert "LOCAL_PUSH_SUBSCRIPTIONS_FILE: /tmp/lifeledger-push-subscriptions.json" in template
    assert "PUSH_SUBSCRIPTIONS_TABLE_NAME: !Ref PushSubscriptionsTable" in template
    assert "RECORDS_TABLE_NAME: !Ref RecordsTable" in template
    assert "GoogleClientId:" in template
    assert "GoogleClientSecret:" in template
    assert "NoEcho: true" in template
    assert "GoogleOAuthRedirectUri:" in template
    assert "GoogleCalendarScopes:" in template
    assert "https://www.googleapis.com/auth/calendar.calendarlist.readonly" in template
    assert "GOOGLE_CALENDAR_CONNECTIONS_TABLE_NAME: !Ref GoogleCalendarConnectionsTable" in template
    assert "GOOGLE_OAUTH_STATES_TABLE_NAME: !Ref GoogleOAuthStatesTable" in template
    assert "GOOGLE_CLIENT_ID: !Ref GoogleClientId" in template
    assert "GOOGLE_CLIENT_SECRET: !Ref GoogleClientSecret" in template
    assert "GOOGLE_OAUTH_REDIRECT_URI: !Ref GoogleOAuthRedirectUri" in template
    assert "GOOGLE_CALENDAR_SCOPES: !Ref GoogleCalendarScopes" in template
    assert "VAPID_PUBLIC_KEY: !Ref VapidPublicKey" in template
    assert "VAPID_PRIVATE_KEY: !Ref VapidPrivateKey" in template
    assert "VAPID_SUBJECT: !Ref VapidSubject" in template
    assert "LifeLedgerDigestPushFunction:" in template
    assert "Handler: digest_push_handler.handler" in template
    assert "Schedule: rate(15 minutes)" in template
    assert "CORS_ALLOWED_ORIGINS: !Ref CorsAllowedOrigins" in template
    assert "https://lifeledger.jpreinold.com" in template
    assert "https://www.lifeledger.jpreinold.com" in template
    assert "DeletionPolicy: Retain" in template
    assert "AttributeName: user_id" in template
    assert "AttributeName: subscription_id" in template
    assert "GoogleCalendarConnectionsTable:" in template
    assert "GoogleOAuthStatesTable:" in template
    assert "RecordsTable:" in template
    assert "AttributeName: state" in template


def test_sam_local_env_file_uses_local_persistence():
    env_file = json.loads((BACKEND_ROOT / "env.local.json").read_text(encoding="utf-8"))

    function_env = env_file["LifeLedgerApiFunction"]
    assert function_env["AUTH_MODE"] == "local"
    assert function_env["LOCAL_DEV_USER_ID"] == "local-dev-user"
    assert function_env["PERSISTENCE_MODE"] == "local"
    assert function_env["LOCAL_DATA_FILE"] == "/tmp/lifeledger-reminders.json"
    assert function_env["LOCAL_RECORDS_FILE"] == "/tmp/lifeledger-records.json"
    assert function_env["LOCAL_PREFERENCES_FILE"] == "/tmp/lifeledger-preferences.json"
    assert function_env["LOCAL_PUSH_SUBSCRIPTIONS_FILE"] == "/tmp/lifeledger-push-subscriptions.json"
    assert function_env["PUSH_SUBSCRIPTIONS_TABLE_NAME"] == "lifeledger-push-subscriptions-auth"
    assert function_env["RECORDS_TABLE_NAME"] == "lifeledger-records-auth"
    assert function_env["GOOGLE_CALENDAR_CONNECTIONS_TABLE_NAME"] == "lifeledger-google-calendar-connections-auth"
    assert function_env["GOOGLE_OAUTH_STATES_TABLE_NAME"] == "lifeledger-google-oauth-states-auth"
    assert function_env["LOCAL_GOOGLE_CALENDAR_CONNECTIONS_FILE"] == "/tmp/lifeledger-google-calendar-connections.json"
    assert function_env["LOCAL_GOOGLE_OAUTH_STATES_FILE"] == "/tmp/lifeledger-google-oauth-states.json"
    assert function_env["GOOGLE_CLIENT_ID"] == ""
    assert function_env["GOOGLE_CLIENT_SECRET"] == ""
    assert function_env["GOOGLE_OAUTH_REDIRECT_URI"] == ""
    assert (
        function_env["GOOGLE_CALENDAR_SCOPES"]
        == "https://www.googleapis.com/auth/calendar.events https://www.googleapis.com/auth/calendar.calendarlist.readonly"
    )
    assert function_env["VAPID_PUBLIC_KEY"] == ""
    assert function_env["VAPID_PRIVATE_KEY"] == ""
    assert function_env["VAPID_SUBJECT"] == ""
    assert "https://lifeledger.jpreinold.com" in function_env["CORS_ALLOWED_ORIGINS"]
    assert "https://www.lifeledger.jpreinold.com" in function_env["CORS_ALLOWED_ORIGINS"]

    digest_env = env_file["LifeLedgerDigestPushFunction"]
    assert digest_env["PERSISTENCE_MODE"] == "local"
    assert digest_env["LOCAL_RECORDS_FILE"] == "/tmp/lifeledger-records.json"
    assert digest_env["LOCAL_PUSH_SUBSCRIPTIONS_FILE"] == "/tmp/lifeledger-push-subscriptions.json"
