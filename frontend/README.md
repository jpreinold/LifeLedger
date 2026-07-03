# LifeLedger Frontend

React, TypeScript, and Vite frontend for the LifeLedger Phase 1 reminder MVP.

## Run locally

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

The app expects the API at `http://localhost:8000` by default. Override with `VITE_API_BASE_URL` when needed.

Use `npm.cmd run build` to verify the production bundle.

## Cloudflare Pages

Deploy this frontend to Cloudflare Pages with:

- Root directory: `frontend`
- Framework preset: `Vite`
- Build command: `npm run build`
- Build output directory: `dist`
- Environment variable: `VITE_API_BASE_URL=https://your-aws-api-gateway-url`

`VITE_API_BASE_URL` is public frontend configuration, not a secret. Do not store API keys, tokens, passwords, AWS credentials, or private values in Vite environment variables.

For local development, create `frontend/.env.local` from `.env.example` and point it at `http://localhost:8000` or SAM local at `http://127.0.0.1:3000`. Local env files are ignored by git.

## API flow

Reminder loading, creation, completion, and deletion all go through `src/api/remindersApi.ts`. The frontend sends and receives the backend field names directly, such as `due_date`, `completed_at`, and `next_due_date`; Python owns validation, persistence, status calculation, recurrence, and completion behavior.

Phase 2 does not change the frontend workflow. The backend still defaults to local JSON persistence, and the React app continues calling the same FastAPI routes.
