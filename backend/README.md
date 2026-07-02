# LifeLedger Backend

FastAPI backend for the LifeLedger Phase 1 reminder MVP.

## Run locally

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

Open the API docs at `http://localhost:8000/docs`.

## Routes

- `GET /health`
- `GET /reminders`
- `POST /reminders`
- `GET /reminders/{id}`
- `PUT /reminders/{id}`
- `DELETE /reminders/{id}`
- `POST /reminders/{id}/complete`

## React to Python flow

The React app calls the API through `frontend/src/api/remindersApi.ts`. Create, complete, delete, and refresh actions all go through FastAPI instead of local browser storage. FastAPI validates incoming JSON, writes reminders through the repository layer, calculates server-owned fields, and returns the reminder response shape used by the frontend.

## Architecture

- `app/main.py` owns the FastAPI app and route handlers.
- `app/schemas.py` owns request and response validation.
- `app/models.py` owns the internal reminder model.
- `app/repository.py` owns persistence through a repository abstraction.
- `app/recurrence.py` owns status and recurrence calculations.
- `lambda_handler.py` wraps FastAPI with Mangum for future AWS Lambda deployment.

Phase 1 uses a JSON file at `backend/data/reminders.json` for persistence, so reminders survive page refreshes and backend restarts. Status calculation, `next_due_date`, and recurrence helpers live in `app/recurrence.py`; complete behavior is coordinated in `app/main.py` and uses those helpers.
