# LifeLedger — Project Brief and Phase 1 Build Instructions

## App Name

**LifeLedger**

## High-Level Concept

LifeLedger is a personal life-admin hub built as an iPhone-friendly PWA with a React frontend and a Python backend.

The purpose of the app is to help me stay on top of important adult-life responsibilities that are easy to forget, such as:

* Car tag / vehicle registration renewals
* Oil changes
* Annual checkups
* Birthdays
* Insurance renewals
* Monthly subscriptions
* Home maintenance reminders
* Important personal records
* Future Google Calendar syncing
* Future secure vault storage
* Future AI-assisted updates and search

The app should eventually become my private command center for reminders, recurring life tasks, and important personal information.

However, we are not building everything at once. The immediate priority is to build a working full-stack MVP with a Python backend so I can get hands-on Python exposure and have something useful to discuss in an interview next week.

---

# Why I Am Building This

I have mostly built PWAs with React and Node so far. I now need to brush up on Python, especially in a backend context.

I want this project to help me learn and demonstrate:

* Python backend development
* API design
* Server-side business logic
* Data validation
* Clean backend architecture
* AWS Lambda-compatible backend structure
* Future serverless deployment
* Future DynamoDB persistence
* Future Google Calendar integration
* Future AI/RAG architecture with privacy boundaries

This should not just be another frontend project. The backend matters a lot.

The project should be built in a way that I can explain clearly in an interview.

---

# Final Product Vision

Long term, LifeLedger should have several major modules.

## 1. Reminder Hub

This is the first and most important module.

It should track important dates, renewals, and recurring adult responsibilities.

Examples:

* Renew car tag
* Oil change
* Annual physical
* Dentist appointment reminder
* Review monthly subscriptions
* Insurance renewal
* Home maintenance
* HVAC filter change
* Birthdays
* Credit card annual fee reminder
* Budget review
* Tax prep reminder

These reminders may eventually sync to Google Calendar.

## 2. Secure Personal Vault

This will eventually store sensitive or semi-sensitive personal records.

Examples:

* Car insurance info
* Home insurance info
* Vehicle information
* Credit card metadata
* Policy renewal details
* Important account notes
* Subscription details
* Warranty information
* Emergency information

Important: this should not be built in Phase 1.

Also important: do not store real credit card numbers, SSNs, passwords, or highly sensitive data until authentication and encryption are designed properly.

## 3. Google Calendar Sync

Eventually, certain reminders should be able to sync to Google Calendar.

Examples:

* Annual registration renewal
* Annual doctor checkup
* Birthday reminders
* Insurance renewal reminders
* Monthly subscription review
* Quarterly home maintenance

This should not be built in Phase 1.

For now, the app should be structured so that calendar sync can be added later.

## 4. AI Assistant / RAG Module

Eventually, I want an AI assistant that can help me manage my life-admin data.

Possible future use cases:

* “What do I need to handle this month?”
* “Add a reminder from this insurance renewal notice.”
* “What car-related tasks are coming up?”
* “What should I update after moving addresses?”
* “Summarize my upcoming adult responsibilities.”
* “Help me organize these reminders.”
* “Search my saved records.”

The AI module must be privacy-conscious.

Sensitive information should not automatically be sent to an LLM. The future app should support toggles or permissions like:

* AI access off
* AI can access reminder data only
* AI can access redacted vault summaries
* AI can access a specific record only after explicit user approval

This should not be built in Phase 1.

For now, only leave clean placeholders or architecture notes for future AI/RAG features.

---

# Current Sprint Goal

The current goal is to build a working full-stack reminder MVP.

The app should allow me to:

1. Open LifeLedger in the browser/mobile PWA.
2. Add a reminder from the React frontend.
3. Save that reminder through a Python backend.
4. Fetch reminders from the backend.
5. View reminders in a dashboard.
6. Mark reminders complete.
7. Delete reminders.
8. Refresh the app and still see saved reminders.
9. Understand the Python backend structure well enough to explain it in an interview.

The first vertical slice matters more than extra features.

---

# Tech Stack

Use this structure:

```text
/lifeledger
  /frontend
  /backend
```

## Frontend

Use:

* React
* TypeScript
* Vite
* Mobile-friendly PWA-style design

The frontend should call the Python API for reminder data.

Do not make localStorage the primary data source. The backend should own reminder persistence.

## Backend

Use:

* Python
* FastAPI preferred
* Pydantic models/schemas
* Clean route organization
* Repository abstraction
* Lambda-compatible structure
* Mangum preferred if wrapping FastAPI for AWS Lambda later

The backend should be organized enough that I can learn from it.

Do not put all backend logic into one messy file.

---

# Phase 1: Build This First

## Phase 1 Objective

Build the full-stack reminder MVP.

This is the only thing to focus on first.

A user should be able to create, view, complete, and delete reminders using the React frontend backed by the Python API.

## Phase 1 Backend Requirements

Create a backend with these routes:

```text
GET    /health
GET    /reminders
POST   /reminders
GET    /reminders/{id}
PUT    /reminders/{id}
DELETE /reminders/{id}
POST   /reminders/{id}/complete
```

The backend should handle:

* Creating reminders
* Listing reminders
* Getting one reminder
* Updating reminders
* Deleting reminders
* Completing reminders
* Calculating reminder status
* Handling recurrence basics
* Validating request data

## Phase 1 Reminder Data Model

A reminder should include:

```text
id
title
category
due_date
repeat
priority
notes
completed
status
created_at
updated_at
completed_at
next_due_date
```

## Categories

Use these reminder categories:

```text
Car
Health
Finance
Home
Family
Subscriptions
Other
```

## Repeat Options

Use these repeat options:

```text
None
Weekly
Monthly
Quarterly
Yearly
```

## Priority Options

Use:

```text
Low
Medium
High
```

## Reminder Status Logic

The backend should calculate status.

Possible statuses:

```text
Completed
Overdue
Due today
Due this week
Due this month
Upcoming
```

The frontend should display the status, but the backend should own the status logic.

This is important because I want the backend to contain real business logic instead of the React app doing everything.

## Recurrence Logic

For Phase 1, keep recurrence simple.

When a reminder is completed:

* If repeat is `None`, mark it completed.
* If repeat is recurring, either:

  * update the due date to the next due date, or
  * mark the current reminder complete and create the next reminder.

Choose the simplest clean MVP approach and keep the code easy to explain.

The backend should include a small recurrence utility/module so this logic is not buried directly in the route handler.

---

# Phase 1 Frontend Requirements

The frontend should include:

```text
Dashboard
ReminderForm
ReminderList
ReminderCard
API client
```

## Dashboard

Show:

* Active reminders count
* Overdue reminders count
* Due this week count
* Due this month count

## Add Reminder Form

Fields:

* Title
* Category
* Due date
* Repeat
* Priority
* Notes

## Reminder List

Each reminder card should show:

* Title
* Category
* Due date
* Status
* Repeat
* Priority
* Notes, if present
* Complete button
* Delete button

## API Client

Create a frontend API layer, for example:

```text
src/api/remindersApi.ts
```

All frontend reminder actions should go through this API client.

The frontend should not directly own the main reminder data logic.

---

# Phase 1 Suggested Backend Structure

Use a clean structure like this:

```text
/backend
  /app
    main.py
    schemas.py
    models.py
    repository.py
    recurrence.py
  requirements.txt
  lambda_handler.py
  README.md
```

## File Responsibilities

### main.py

Owns the FastAPI app and routes.

### schemas.py

Owns Pydantic request/response schemas.

### models.py

Owns internal reminder model definitions if needed.

### repository.py

Owns persistence logic.

Start with a local repository implementation first so the app works immediately.

The repository should be structured so a DynamoDB repository can be added later without rewriting the route logic.

### recurrence.py

Owns date/status/recurrence calculations.

### lambda_handler.py

Provides a future AWS Lambda-compatible entrypoint.

If using FastAPI, wrap the app with Mangum.

### README.md

Explain how to run the backend locally.

---

# Phase 1 Suggested Frontend Structure

Use a structure like this:

```text
/frontend
  /src
    /api
      remindersApi.ts
    /components
      Dashboard.tsx
      ReminderForm.tsx
      ReminderList.tsx
      ReminderCard.tsx
    /types
      reminder.ts
    App.tsx
    main.tsx
    styles.css
```

---

# Phase 1 Definition of Done

Phase 1 is done when:

* The backend runs locally.
* The frontend runs locally.
* The frontend successfully calls the Python backend.
* I can create a reminder from the frontend.
* I can view reminders from the frontend.
* I can refresh and still fetch reminders from the backend.
* I can mark a reminder complete.
* I can delete a reminder.
* Backend validation works.
* Backend status logic works.
* Backend recurrence logic exists in a clean utility/module.
* The code is organized enough to explain in an interview.

---

# What Not To Build In Phase 1

Do not build these yet:

```text
AI assistant
RAG
Google Calendar sync
OAuth
Authentication
Secure vault
Credit card storage
Insurance document storage
File uploads
Push notifications
Complex recurrence rules
Multiple users
Password reset
Advanced animations
Complex design system
```

Keep the first version focused.

The goal is a working full-stack Python-backed reminder app, not a bloated unfinished product.

---

# Phase 2: After Phase 1 Works

After the Phase 1 vertical slice is working, the next focus is making the backend more credible and deployment-ready.

## Phase 2 Priorities

### 1. Lambda-Ready Backend

Make sure the backend can be deployed as a Python Lambda API.

Add or clean up:

```text
lambda_handler.py
template.yaml
requirements.txt
README.md
```

Use Mangum if using FastAPI.

The goal is to explain:

* How FastAPI handles local API routes
* How Mangum adapts the app to AWS Lambda
* How API Gateway or a Lambda Function URL could call the Lambda
* How the React frontend talks to the deployed backend

### 2. Persistence Upgrade Path

Add a clean persistence path.

Start with local persistence, but prepare for DynamoDB.

Use a repository pattern:

```text
LocalReminderRepository
DynamoReminderRepository
```

Repository selection should be environment-based.

For example:

```text
APP_ENV=local
APP_ENV=production
REMINDERS_TABLE_NAME=lifeledger-reminders
```

The local app should continue working even if DynamoDB is not configured.

### 3. README and Interview Notes

Add a README that explains:

* What LifeLedger is
* How to run the frontend
* How to run the backend
* API routes
* Data model
* Backend architecture
* Future roadmap
* How Lambda deployment would work
* How DynamoDB would fit in later

This project should be easy to demo and easy to talk through.

### 4. Reminder Templates

Add preset reminder templates after the core app works.

Examples:

```text
Renew car tag — Car — Yearly
Oil change — Car — Quarterly
Annual physical — Health — Yearly
Review subscriptions — Finance — Monthly
Change HVAC filter — Home — Quarterly
Insurance renewal — Finance — Yearly
Birthday reminder — Family — Yearly
```

These should help me quickly seed useful real-life reminders.

### 5. UI Polish

Improve the mobile layout, but do not over-focus on design.

The app should feel:

* Clean
* Calm
* Practical
* Mobile-friendly
* iPhone PWA-friendly

---

# Phase 3: Future Features After Backend MVP

Do not start these until the reminder MVP and backend structure are solid.

## Google Calendar Sync

Future work:

* Connect Google Calendar
* Sync selected reminders
* Create calendar events
* Update synced events
* Remove synced events
* Store calendar event IDs

## Secure Vault

Future work:

* Add a vault section
* Store personal records
* Encrypt sensitive fields
* Redact sensitive values in the UI
* Add user confirmation before showing sensitive info
* Keep vault data separate from reminders

Potential vault record types:

```text
Insurance
Credit Card Metadata
Vehicle
Home
Medical
Subscription
Warranty
Other
```

Do not store real sensitive data until auth/encryption are implemented.

## AI/RAG Module

Future work:

* Add an AI assistant
* Add a safe context layer
* Allow AI to read reminder data
* Keep vault data excluded by default
* Add redacted summaries
* Add explicit user permission before exposing sensitive record data
* Build RAG over safe reminders and summaries

Example AI questions:

```text
What do I need to handle this month?
What car-related reminders are coming up?
What adult-life tasks am I missing?
Create a reminder from this pasted text.
Summarize my upcoming responsibilities.
```

---

# Important Product Principle

LifeLedger should be practical before it is impressive.

Build the smallest real version first:

```text
React PWA + Python backend + reminder CRUD + recurrence/status logic
```

Then make it deployable.

Then make it secure.

Then make it smart.

Do not chase AI, calendar sync, or vault storage before the backend reminder MVP works.

---

# Interview Framing

The project should be built so I can eventually explain it like this:

“I built LifeLedger, a personal life-admin PWA with a React frontend and Python backend. The backend exposes reminder CRUD endpoints, validates data with Pydantic, calculates reminder status and recurrence server-side, and uses a repository layer so persistence can move from local storage to DynamoDB. The app is structured to run locally during development and later deploy as an AWS Lambda-backed API. I intentionally scoped Google Calendar sync, secure vault storage, and AI/RAG features as future modules so the MVP stayed usable and security boundaries stayed clear.”

That is the target.
