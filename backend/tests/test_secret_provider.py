import pytest

from app.config import load_settings
from app.secret_provider import SecretProvider


class FakeSecretsManagerClient:
    def __init__(self):
        self.calls: list[str] = []
        self.secrets = {
            "google-secret": '{"client_secret": "google-client-secret"}',
            "push-secret": '{"vapid_private_key": "push-private-key"}',
        }

    def get_secret_value(self, SecretId: str):
        self.calls.append(SecretId)
        return {"SecretString": self.secrets[SecretId]}


def test_secret_provider_loads_and_caches_google_secret():
    client = FakeSecretsManagerClient()
    provider = SecretProvider(
        load_settings({"GOOGLE_OAUTH_SECRET_ARN": "google-secret"}),
        client=client,
    )

    assert provider.google_client_secret() == "google-client-secret"
    assert provider.google_client_secret() == "google-client-secret"
    assert client.calls == ["google-secret"]


def test_secret_provider_loads_and_caches_push_secret():
    client = FakeSecretsManagerClient()
    provider = SecretProvider(
        load_settings({"PUSH_SECRET_ARN": "push-secret"}),
        client=client,
    )

    assert provider.vapid_private_key() == "push-private-key"
    assert provider.vapid_private_key() == "push-private-key"
    assert client.calls == ["push-secret"]


def test_secret_provider_disallows_plaintext_production_fallback_at_startup():
    with pytest.raises(ValueError, match="local plaintext secret providers are not allowed"):
        load_settings(
            {
                "APP_ENV": "production",
                "GOOGLE_CLIENT_SECRET": "google-client-secret",
                "VAPID_PRIVATE_KEY": "push-private-key",
            }
        )


def test_secret_provider_allows_plaintext_local_fallback():
    provider = SecretProvider(
        load_settings(
            {
                "GOOGLE_CLIENT_SECRET": "google-client-secret",
                "VAPID_PRIVATE_KEY": "push-private-key",
            }
        )
    )

    assert provider.google_client_secret() == "google-client-secret"
    assert provider.vapid_private_key() == "push-private-key"
