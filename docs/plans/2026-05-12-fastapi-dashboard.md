# FastAPI Dashboard

## Goal

Add a lightweight web dashboard for Switchboard so agents, tasks, workflows, messages, and scheduler status can be viewed from a browser.

## Scope

- FastAPI app factory with injectable `SwitchboardService`.
- JSON API endpoints:
  - `GET /api/agents`
  - `GET /api/tasks`
  - `GET /api/workflows`
  - `GET /api/inbox/{agent}`
  - `POST /api/send`
  - `POST /api/tasks/{task_id}/move`
  - `POST /api/workflows/{name}/run`
- HTML dashboard at `/` showing agents, tasks, workflows, and usage hints.
- CLI command: `switchboard dashboard --host 127.0.0.1 --port 8765`.

## Out of scope

- Auth/login.
- WebSockets/live streaming.
- Mutating every Switchboard operation from UI.

## Verification

- FastAPI TestClient tests for API and root HTML.
- CLI help smoke test.
- Full pytest suite.
