# Personal Assistant Calendar Service

This project provides a FastAPI-based backend that powers a personal assistant calendar.

## Features

- Bearer token authentication.
- Endpoints for checking availability, finding free slots, and creating, updating, or deleting events.
- SQLite storage via SQLModel with UTC timestamps.

## Getting started

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export API_BEARER_KEY="supersecret"
uvicorn app:app --host 0.0.0.0 --port 8080
```

With the server running, you can test the API:

```bash
curl -H "Authorization: Bearer supersecret" \
  "http://localhost:8080/availability.find_slots?duration_min=45&window_start=2025-11-12T09:00:00Z&window_end=2025-11-12T17:00:00Z"

curl -X POST -H "Content-Type: application/json" -H "Authorization: Bearer supersecret" \
  -d '{"title":"Deep work","start":"2025-11-12T13:00:00Z","end":"2025-11-12T13:30:00Z","idempotency_key":"abc123"}' \
  http://localhost:8080/events.create
```
