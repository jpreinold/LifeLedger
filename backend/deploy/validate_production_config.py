import argparse
import json
from pathlib import Path


REQUIRED_TABLES = {
    "RemindersTableName",
    "RecordsTableName",
    "RecordAttachmentsTableName",
    "LinkedItemsTableName",
    "SearchIndexTableName",
    "SavedViewsTableName",
    "ResponsibilityHistoryTableName",
    "PreferencesTableName",
    "PushSubscriptionsTableName",
    "GoogleCalendarConnectionsTableName",
    "GoogleOAuthStatesTableName",
    "ReconciliationTableName",
    "AccountOperationsTableName",
}


def validate(parameters: dict[str, str]) -> list[str]:
    problems = []
    expected = {
        "AppEnv": "production",
        "AuthMode": "cognito",
        "PersistenceMode": "dynamodb",
        "RecordEncryptionMode": "kms",
        "DocumentStorageMode": "s3",
        "MalwareProtectionEnabled": "true",
    }
    for key, value in expected.items():
        if parameters.get(key) != value:
            problems.append(f"{key} must be {value}")
    cors = [item.strip() for item in parameters.get("CorsAllowedOrigins", "").split(",") if item.strip()]
    if not cors or any(
        not item.startswith("https://") or "localhost" in item or "127.0.0.1" in item or item == "*"
        for item in cors
    ):
        problems.append("CorsAllowedOrigins must contain only explicit HTTPS production origins")
    missing_tables = sorted(key for key in REQUIRED_TABLES if not parameters.get(key))
    if missing_tables:
        problems.append("missing table parameters: " + ", ".join(missing_tables))
    for key in ("GoogleOAuthSecretArn", "PushSecretArn"):
        value = parameters.get(key, "")
        if value and not value.startswith("arn:aws:secretsmanager:"):
            problems.append(f"{key} must be a Secrets Manager ARN")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail-closed validation for versioned LifeLedger production settings.")
    parser.add_argument(
        "--parameters",
        type=Path,
        default=Path(__file__).with_name("production.parameters.json"),
    )
    args = parser.parse_args()
    parameters = json.loads(args.parameters.read_text(encoding="utf-8"))
    problems = validate(parameters)
    if problems:
        for problem in problems:
            print(f"ERROR: {problem}")
        return 1
    print("Production configuration is valid.")
    print(f"APP_ENV={parameters['AppEnv']}")
    print(f"AUTH_MODE={parameters['AuthMode']}")
    print(f"PERSISTENCE_MODE={parameters['PersistenceMode']}")
    print(f"RECORD_ENCRYPTION_MODE={parameters['RecordEncryptionMode']}")
    print(f"DOCUMENT_STORAGE_MODE={parameters['DocumentStorageMode']}")
    print(f"CORS_ALLOWED_ORIGINS={parameters['CorsAllowedOrigins']}")
    print(f"REQUIRED_TABLE_COUNT={len(REQUIRED_TABLES)}")
    print(f"GOOGLE_SECRET_REFERENCE_CONFIGURED={bool(parameters.get('GoogleOAuthSecretArn'))}")
    print(f"PUSH_SECRET_REFERENCE_CONFIGURED={bool(parameters.get('PushSecretArn'))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
