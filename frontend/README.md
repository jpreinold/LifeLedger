# LifeLedger Frontend

React, TypeScript, Vite, and PWA frontend for the LifeLedger reminder MVP.

## Run Locally

Preferred root command:

```powershell
cd D:\CodingProjects\LifeLedger
npm run frontend
```

Manual frontend command:

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

For local testing, use `frontend/.env.local` with:

```text
VITE_AUTH_MODE=local
VITE_API_BASE_URL=http://localhost:8000
```

Restart `npm run frontend` after changing `.env.local`; Vite reads env values at startup. Use deployed API Gateway URLs only for Cloudflare production builds.

Use `npm.cmd run build` to verify the production bundle.

## Authentication

Local development uses `VITE_AUTH_MODE=local` by default, so the frontend does not show Cognito sign-in while calling a local backend.

Deployed mode uses Cognito:

- Set `VITE_AUTH_MODE=cognito`.
- Set the Cognito region, user pool id, and app client id from the SAM stack outputs.
- The app shows a minimal sign-in/sign-out flow.
- Public sign-up is hidden; users should be created by an admin in Cognito.
- API requests attach `Authorization: Bearer <access token>` from the Cognito session.

## Life Admin Templates

`src/templates/lifeAdminTemplates.ts` contains safe starter templates for common reminders. The app opens them in a searchable modal from the reminder form or empty state. Selecting a template fills the existing reminder form, and the user still chooses or confirms the due date before saving.

Templates create normal reminders through `src/api/remindersApi.ts`. They do not include sensitive fields, do not send `user_id`, and do not bypass Cognito-protected reminder APIs.

## Cloudflare Pages

Deploy this frontend to Cloudflare Pages with:

- Root directory: `frontend`
- Framework preset: `Vite`
- Build command: `npm run build`
- Build output directory: `dist`

Required Cloudflare Pages environment variables:

| Variable | Value |
| --- | --- |
| `VITE_API_BASE_URL` | `https://your-aws-api-gateway-url` |
| `VITE_AUTH_MODE` | `cognito` |
| `VITE_COGNITO_REGION` | `us-east-1` |
| `VITE_COGNITO_USER_POOL_ID` | SAM output `UserPoolId` |
| `VITE_COGNITO_USER_POOL_CLIENT_ID` | SAM output `UserPoolClientId` |

These values are public frontend configuration, not secrets. Do not store API keys, passwords, AWS credentials, private tokens, or secret access keys in Vite environment variables.

For local development, create `frontend/.env.local` from `.env.example` and point it at `http://localhost:8000` or SAM local at `http://127.0.0.1:3000`. Local env files are ignored by git.

## API Flow

Reminder loading, creation, completion, and deletion all go through `src/api/remindersApi.ts`. The frontend sends and receives the backend field names directly, such as `due_date`, `completed_at`, and `next_due_date`; Python owns validation, persistence, status calculation, recurrence, completion behavior, and user scoping.

When `VITE_AUTH_MODE=cognito`, `src/auth/session.ts` reads the Cognito session and adds the bearer token to API requests. The frontend does not send `user_id`; the backend assigns it from authenticated Cognito claims.
