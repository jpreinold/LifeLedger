import json
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def template_text() -> str:
    return (BACKEND_ROOT / "template.yaml").read_text(encoding="utf-8")


def template_section(template: str, start: str, end: str) -> str:
    return template.split(start, maxsplit=1)[1].split(end, maxsplit=1)[0]


def test_sam_template_defaults_to_local_persistence():
    template = template_text()

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
    assert "LOCAL_RECORD_ATTACHMENTS_FILE: /tmp/lifeledger-record-attachments.json" in template
    assert "LOCAL_PREFERENCES_FILE: /tmp/lifeledger-preferences.json" in template
    assert "LOCAL_PUSH_SUBSCRIPTIONS_FILE: /tmp/lifeledger-push-subscriptions.json" in template
    assert "PUSH_SUBSCRIPTIONS_TABLE_NAME: !Ref PushSubscriptionsTable" in template
    assert "RECORDS_TABLE_NAME: !Ref RecordsTable" in template
    assert "RECORD_ATTACHMENTS_TABLE_NAME: !Ref RecordAttachmentsTable" in template
    assert "DocumentStorageMode:" in template
    assert "DOCUMENT_STORAGE_MODE: !Ref DocumentStorageMode" in template
    assert "DOCUMENTS_QUARANTINE_BUCKET: !Ref DocumentsQuarantineBucket" in template
    assert "DOCUMENTS_CLEAN_BUCKET: !Ref DocumentsCleanBucket" in template
    assert "DOCUMENTS_KMS_KEY_ARN: !GetAtt LifeLedgerDocumentsKey.Arn" in template
    assert "ATTACHMENT_MAX_SIZE_BYTES: !Ref AttachmentMaxSizeBytes" in template
    assert "ATTACHMENT_MAX_PER_RECORD: !Ref AttachmentMaxPerRecord" in template
    assert "GoogleClientId:" in template
    assert "GoogleOAuthSecretArn:" in template
    assert "GoogleOAuthRedirectUri:" in template
    assert "GoogleCalendarScopes:" in template
    assert "PushSecretArn:" in template
    assert "RecordEncryptionMode:" in template
    assert "https://www.googleapis.com/auth/calendar.calendarlist.readonly" in template
    assert "GOOGLE_CALENDAR_CONNECTIONS_TABLE_NAME: !Ref GoogleCalendarConnectionsTable" in template
    assert "GOOGLE_OAUTH_STATES_TABLE_NAME: !Ref GoogleOAuthStatesTable" in template
    assert "GOOGLE_CLIENT_ID: !Ref GoogleClientId" in template
    assert "GOOGLE_OAUTH_SECRET_ARN: !Ref GoogleOAuthSecretArn" in template
    assert "GOOGLE_OAUTH_REDIRECT_URI: !Ref GoogleOAuthRedirectUri" in template
    assert "GOOGLE_CALENDAR_SCOPES: !Ref GoogleCalendarScopes" in template
    assert "VAPID_PUBLIC_KEY: !Ref VapidPublicKey" in template
    assert "PUSH_SECRET_ARN: !Ref PushSecretArn" in template
    assert "VAPID_SUBJECT: !Ref VapidSubject" in template
    assert "GoogleClientSecret:" not in template
    assert "VapidPrivateKey:" not in template
    assert "GOOGLE_CLIENT_SECRET: !Ref" not in template
    assert "VAPID_PRIVATE_KEY: !Ref" not in template
    assert "LifeLedgerDataEncryptionKey:" in template
    assert "EnableKeyRotation: true" in template
    assert "LifeLedgerDataEncryptionAlias:" in template
    assert "LifeLedgerDocumentsKey:" in template
    assert "LifeLedgerDocumentsKeyAlias:" in template
    assert "alias/${AWS::StackName}-documents" in template
    assert "DocumentsQuarantineBucket:" in template
    assert "DocumentsCleanBucket:" in template
    assert "BlockPublicAcls: true" in template
    assert "ObjectOwnership: BucketOwnerEnforced" in template
    assert "BucketKeyEnabled: true" in template
    assert "ExpireAbandonedQuarantineUploads" in template
    assert "RecordAttachmentsTable:" in template
    assert "OwnerHashRecordAttachmentIndex" in template
    assert "AWS::GuardDuty::MalwareProtectionPlan" in template
    assert "GuardDuty Malware Protection Object Scan Result" in template
    assert "DATA_ENCRYPTION_KMS_KEY_ARN: !GetAtt LifeLedgerDataEncryptionKey.Arn" in template
    assert "kms:GenerateDataKey" in template
    assert "kms:Decrypt" in template
    assert "kms:EncryptionContext:app: lifeledger" in template
    assert "kms:ViaService: dynamodb.*.amazonaws.com" in template
    assert "kms:CallerAccount: !Ref AWS::AccountId" in template
    assert "kms:GrantIsForAWSResource: true" in template
    assert "secretsmanager:GetSecretValue" in template
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
    assert "SSEType: KMS" in template
    assert "PointInTimeRecoveryEnabled: true" in template
    assert "DataEncryptionKeyArn:" in template
    assert "DataEncryptionKeyAlias:" in template
    assert "DocumentsKeyArn:" in template
    assert "DocumentsQuarantineBucketName:" in template
    assert "RecordAttachmentsTableName:" in template

    digest_section = template_section(template, "LifeLedgerDigestPushFunction:", "RemindersTable:")
    assert "DATA_ENCRYPTION_KMS_KEY_ARN" not in digest_section
    assert "kms:EncryptionContext:app" not in digest_section
    assert "DOCUMENTS_QUARANTINE_BUCKET" not in digest_section
    assert "LifeLedgerDocumentsKey" not in digest_section


def test_sam_kms_permissions_split_app_and_dynamodb_access():
    template = template_text()
    api_section = template_section(template, "LifeLedgerApiFunction:", "LifeLedgerDigestPushFunction:")
    digest_section = template_section(template, "LifeLedgerDigestPushFunction:", "RemindersTable:")

    assert "kms:GenerateDataKey" in api_section
    assert "kms:Decrypt" in api_section
    assert "kms:EncryptionContext:app: lifeledger" in api_section
    assert "DATA_ENCRYPTION_KMS_KEY_ARN: !GetAtt LifeLedgerDataEncryptionKey.Arn" in api_section
    assert "DOCUMENTS_KMS_KEY_ARN: !GetAtt LifeLedgerDocumentsKey.Arn" in api_section
    assert "Resource: !GetAtt LifeLedgerDocumentsKey.Arn" in api_section
    assert "Resource: !Sub \"${DocumentsQuarantineBucket.Arn}/quarantine/*\"" in api_section
    assert "Resource: !Sub \"${DocumentsCleanBucket.Arn}/clean/*\"" in api_section

    for section in (api_section, digest_section):
        assert "kms:Encrypt" in section
        assert "kms:Decrypt" in section
        assert "kms:ReEncrypt*" in section
        assert "kms:GenerateDataKey*" in section
        assert "kms:DescribeKey" in section
        assert "kms:CreateGrant" in section
        assert "kms:CallerAccount: !Ref AWS::AccountId" in section
        assert "kms:ViaService: dynamodb.*.amazonaws.com" in section
        assert "kms:GrantIsForAWSResource: true" in section
        assert "Resource: !GetAtt LifeLedgerDataEncryptionKey.Arn" in section
        assert "Resource: \"*\"" not in section

    assert "kms:EncryptionContext:app" not in digest_section
    assert "DATA_ENCRYPTION_KMS_KEY_ARN" not in digest_section
    assert "LifeLedgerDocumentsKey" not in digest_section


def test_sam_local_env_file_uses_local_persistence():
    env_file = json.loads((BACKEND_ROOT / "env.local.json").read_text(encoding="utf-8"))

    function_env = env_file["LifeLedgerApiFunction"]
    assert function_env["AUTH_MODE"] == "local"
    assert function_env["LOCAL_DEV_USER_ID"] == "local-dev-user"
    assert function_env["PERSISTENCE_MODE"] == "local"
    assert function_env["LOCAL_DATA_FILE"] == "/tmp/lifeledger-reminders.json"
    assert function_env["LOCAL_RECORDS_FILE"] == "/tmp/lifeledger-records.json"
    assert function_env["LOCAL_RECORD_ATTACHMENTS_FILE"] == "/tmp/lifeledger-record-attachments.json"
    assert function_env["LOCAL_PREFERENCES_FILE"] == "/tmp/lifeledger-preferences.json"
    assert function_env["LOCAL_PUSH_SUBSCRIPTIONS_FILE"] == "/tmp/lifeledger-push-subscriptions.json"
    assert function_env["PUSH_SUBSCRIPTIONS_TABLE_NAME"] == "lifeledger-push-subscriptions-auth"
    assert function_env["RECORDS_TABLE_NAME"] == "lifeledger-records-auth"
    assert function_env["RECORD_ATTACHMENTS_TABLE_NAME"] == "lifeledger-record-attachments-auth"
    assert function_env["GOOGLE_CALENDAR_CONNECTIONS_TABLE_NAME"] == "lifeledger-google-calendar-connections-auth"
    assert function_env["GOOGLE_OAUTH_STATES_TABLE_NAME"] == "lifeledger-google-oauth-states-auth"
    assert function_env["LOCAL_GOOGLE_CALENDAR_CONNECTIONS_FILE"] == "/tmp/lifeledger-google-calendar-connections.json"
    assert function_env["LOCAL_GOOGLE_OAUTH_STATES_FILE"] == "/tmp/lifeledger-google-oauth-states.json"
    assert function_env["DATA_ENCRYPTION_KMS_KEY_ARN"] == ""
    assert function_env["RECORD_ENCRYPTION_MODE"] == "disabled"
    assert function_env["LOCAL_RECORDS_ENCRYPTION_KEY"] == ""
    assert function_env["DOCUMENT_STORAGE_MODE"] == "disabled"
    assert function_env["DOCUMENTS_QUARANTINE_BUCKET"] == ""
    assert function_env["DOCUMENTS_CLEAN_BUCKET"] == ""
    assert function_env["DOCUMENTS_KMS_KEY_ARN"] == ""
    assert function_env["ATTACHMENT_MAX_SIZE_BYTES"] == "10485760"
    assert function_env["ATTACHMENT_MAX_PER_RECORD"] == "5"
    assert function_env["GOOGLE_OAUTH_SECRET_ARN"] == ""
    assert function_env["PUSH_SECRET_ARN"] == ""
    assert function_env["ALLOW_PLAINTEXT_PRODUCTION_SECRETS"] == "false"
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
    assert digest_env["LOCAL_RECORD_ATTACHMENTS_FILE"] == "/tmp/lifeledger-record-attachments.json"
    assert digest_env["LOCAL_PUSH_SUBSCRIPTIONS_FILE"] == "/tmp/lifeledger-push-subscriptions.json"
    assert digest_env["PUSH_SECRET_ARN"] == ""
    assert digest_env["ALLOW_PLAINTEXT_PRODUCTION_SECRETS"] == "false"
    assert "DATA_ENCRYPTION_KMS_KEY_ARN" not in digest_env
    assert "DOCUMENTS_KMS_KEY_ARN" not in digest_env

    finalizer_env = env_file["LifeLedgerAttachmentScanFinalizerFunction"]
    assert finalizer_env["PERSISTENCE_MODE"] == "local"
    assert finalizer_env["LOCAL_RECORD_ATTACHMENTS_FILE"] == "/tmp/lifeledger-record-attachments.json"
    assert finalizer_env["RECORD_ATTACHMENTS_TABLE_NAME"] == "lifeledger-record-attachments-auth"
    assert finalizer_env["DOCUMENT_STORAGE_MODE"] == "disabled"
