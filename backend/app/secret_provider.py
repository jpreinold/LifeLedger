import json
from typing import Any, Protocol

from app.config import Settings, get_settings
from app.security_audit import log_security_event


class SecretsManagerClient(Protocol):
    def get_secret_value(self, **kwargs: Any) -> dict[str, Any]:
        ...


class SecretConfigurationError(Exception):
    safe_message = "Required secret configuration is missing."


class SecretProvider:
    def __init__(self, settings: Settings | None = None, client: SecretsManagerClient | None = None):
        self.settings = settings or get_settings()
        self.client = client
        self._cache: dict[str, dict[str, str]] = {}

    def google_client_secret(self) -> str:
        if self.settings.google_oauth_secret_arn:
            return self._required_secret_value(
                self.settings.google_oauth_secret_arn,
                "client_secret",
                "google_oauth",
            )

        if self.settings.plaintext_secret_fallback_allowed and self.settings.google_client_secret:
            return self.settings.google_client_secret

        log_security_event("secrets_configuration_missing", secret="google_oauth", result="missing")
        raise SecretConfigurationError()

    def vapid_private_key(self) -> str:
        if self.settings.push_secret_arn:
            return self._required_secret_value(
                self.settings.push_secret_arn,
                "vapid_private_key",
                "push",
            )

        if self.settings.plaintext_secret_fallback_allowed and self.settings.vapid_private_key:
            return self.settings.vapid_private_key

        log_security_event("secrets_configuration_missing", secret="push", result="missing")
        raise SecretConfigurationError()

    def openai_api_key(self) -> str:
        if self.settings.ai_api_secret_arn:
            return self._required_secret_value(
                self.settings.ai_api_secret_arn,
                "api_key",
                "openai",
            )

        if self.settings.plaintext_secret_fallback_allowed and self.settings.openai_api_key:
            return self.settings.openai_api_key

        log_security_event("secrets_configuration_missing", secret="openai", result="missing")
        raise SecretConfigurationError()

    def _required_secret_value(self, secret_arn: str, key: str, safe_name: str) -> str:
        secret = self._secret_json(secret_arn, safe_name)
        value = secret.get(key)
        if not isinstance(value, str) or not value:
            log_security_event("secrets_configuration_missing", secret=safe_name, result="missing_key")
            raise SecretConfigurationError()
        return value

    def _secret_json(self, secret_arn: str, safe_name: str) -> dict[str, str]:
        if secret_arn in self._cache:
            return self._cache[secret_arn]

        try:
            response = self._client().get_secret_value(SecretId=secret_arn)
            secret_string = response.get("SecretString")
            parsed = json.loads(secret_string) if isinstance(secret_string, str) else None
        except Exception as exc:
            log_security_event("secrets_configuration_missing", secret=safe_name, result="read_failed")
            raise SecretConfigurationError() from exc

        if not isinstance(parsed, dict):
            log_security_event("secrets_configuration_missing", secret=safe_name, result="invalid_json")
            raise SecretConfigurationError()

        sanitized = {key: value for key, value in parsed.items() if isinstance(key, str) and isinstance(value, str)}
        self._cache[secret_arn] = sanitized
        return sanitized

    def _client(self) -> SecretsManagerClient:
        if self.client is not None:
            return self.client

        import boto3

        self.client = boto3.client("secretsmanager", region_name=self.settings.aws_region)
        return self.client


_providers: dict[tuple[str, str, str, str, str, str, str, bool], SecretProvider] = {}


def get_secret_provider(settings: Settings | None = None) -> SecretProvider:
    resolved_settings = settings or get_settings()
    cache_key = (
        resolved_settings.aws_region,
        resolved_settings.google_oauth_secret_arn,
        resolved_settings.push_secret_arn,
        resolved_settings.ai_api_secret_arn,
        resolved_settings.google_client_secret,
        resolved_settings.vapid_private_key,
        resolved_settings.openai_api_key,
        resolved_settings.plaintext_secret_fallback_allowed,
    )
    provider = _providers.get(cache_key)
    if provider is None:
        provider = SecretProvider(resolved_settings)
        _providers[cache_key] = provider
    return provider
