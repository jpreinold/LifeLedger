# Capture evaluation

`backend/evals/capture-v1.json` contains 50 versioned cases covering Person birthdays, pet vaccination, vehicle registration, passport expiration, subscriptions, home maintenance, reminders, completion, snooze, candidate/date ambiguity, conflicts, multi-action statements, unsupported requests, sensitive information, prompt injection, and destructive requests.

Each case declares input, timezone/current date, candidate fixtures, deterministic expectation, intent/actions, entity match, clarification, risk, confirmation, and prohibition.

Run free local evaluations:

```powershell
cd backend
.\.venv\Scripts\python.exe capture_eval.py --mode deterministic
.\.venv\Scripts\python.exe capture_eval.py --mode mock
```

The deterministic mode asserts the supported grammar cases. Mock mode validates provider plumbing for all 50 without network calls. Paid live evaluation is opt-in only:

```powershell
.\.venv\Scripts\python.exe capture_eval.py --mode live --allow-paid
```

The live command additionally requires explicit OpenAI configuration. Standard CI must never set `--allow-paid` or depend on provider availability. A live call is not considered verified unless command output is retained with environment/date/model metadata.
