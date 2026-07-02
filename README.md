# LifeLedger

LifeLedger is a Phase 1 full-stack reminder MVP: a React/TypeScript PWA-style frontend backed by a Python FastAPI API.

## Run the backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

API docs are available at `http://localhost:8000/docs`.

## Run the frontend

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

The frontend runs at `http://localhost:5173` and calls `http://localhost:8000` by default. Set `VITE_API_BASE_URL` to point at a different backend.

## Routes

- `GET /health`
- `GET /reminders`
- `POST /reminders`
- `GET /reminders/{id}`
- `PUT /reminders/{id}`
- `DELETE /reminders/{id}`
- `POST /reminders/{id}/complete`

## Reminder flow

React components call `frontend/src/api/remindersApi.ts` for loading, creating, completing, and deleting reminders. That client sends JSON to the FastAPI routes in `backend/app/main.py`. The backend validates the request with Pydantic schemas, persists reminders through the repository layer, calculates response-only fields, and returns the updated reminder list data to React.

## Backend logic

Validation and API shapes live in `backend/app/schemas.py`. Persistence lives behind `backend/app/repository.py`, currently using `backend/data/reminders.json`, so reminders survive page refreshes and backend restarts. Status calculation, `next_due_date`, and recurrence helpers live in `backend/app/recurrence.py`; completion behavior is coordinated by the FastAPI route and those utilities.
