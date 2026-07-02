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

## API flow

Reminder loading, creation, completion, and deletion all go through `src/api/remindersApi.ts`. The frontend sends and receives the backend field names directly, such as `due_date`, `completed_at`, and `next_due_date`; Python owns validation, persistence, status calculation, recurrence, and completion behavior.
