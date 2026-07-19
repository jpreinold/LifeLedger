# Authenticated production E2E

The deployed Playwright project is a manually triggered smoke test for a dedicated non-personal Cognito account. It is never a pull-request check and must not be pointed at a personal account.

## Dedicated account

Create a Cognito user used only for acceptance data and add it to the configured `E2E_ACCOUNT_GROUP`. Grant no administrative privileges. Protect staging and production credentials with GitHub Environments and require the environment's normal reviewers. Rotate the password after suspected exposure or an abnormal run.

Required GitHub environment secrets/variables, without values, are:

- `E2E_BASE_URL`
- `E2E_API_BASE_URL`
- `E2E_USERNAME`
- `E2E_PASSWORD`
- `E2E_ACCOUNT_GROUP`
- optional `AWS_ROLE_TO_ASSUME` for safe E2E metrics

The workflow masks credentials, limits concurrency to one run per environment, bounds execution to 15 minutes, and does not save browser storage, traces, or video. JSON reporting and failure screenshots are uploaded only after failure and retained for seven days.

## Triggering

Run `.github/workflows/production-e2e.yml` with GitHub Actions **Run workflow**, explicitly choosing `staging` or `production`. For local manual execution:

```powershell
cd frontend
$env:E2E_BASE_URL='https://dedicated-frontend.example'
$env:E2E_API_BASE_URL='https://dedicated-api.example'
$env:E2E_USERNAME='dedicated-account@example.com'
$env:E2E_PASSWORD='<environment-secret>'
$env:E2E_ACCOUNT_GROUP='lifeledger-e2e'
npm run test:e2e:deployed
```

Do not echo the environment or enable verbose HTTP/browser logging.

## Acceptance and cleanup

Each run uses a unique `PHASE13-<timestamp>-<random>` prefix. It signs in through Cognito, creates an item, normal and protected details, verifies ordinary responses/search exclude the protected value, creates and links a responsibility, completes it, verifies lifecycle history, uploads a small permitted PDF through quarantine and malware scanning, waits at most 120 seconds for clean availability, opens that exact document, verifies safe search and an unauthenticated 401, then cleans up.

Cleanup is in `finally`: documents/S3 objects through the document API, links, reminders/history under current deletion semantics, and items are removed; search disappearance is polled and verified. Cleanup errors fail the run and report only safe IDs. A failed run never silently leaves test data. Operators should inspect the failure screenshot/report, run the same dedicated account again after repair, and confirm no `PHASE13-` records remain.

Local deterministic Playwright remains the normal CI path. A repository implementation or local pass is not evidence that the real production scan ran; record the GitHub run URL and timestamp in the release record only after the dedicated-account workflow succeeds.
