# Dashboard Auth and Safer Actions

## Goal

Make the FastAPI dashboard safer before it can be left running locally or exposed through a tunnel.

## Scope

- Optional bearer-token auth via `SWITCHBOARD_DASHBOARD_TOKEN`.
- Public dashboard remains open if no token is configured for local dev.
- When token is configured, all HTML/API routes require `Authorization: Bearer ...`.
- Mutating API actions require explicit `confirm: true` in JSON body:
  - `POST /api/send`
  - `POST /api/tasks/{task_id}/move`
  - `POST /api/workflows/{name}/run`
- CLI `dashboard` supports `--require-token` to fail fast if env token is missing.
- Never print or store dashboard token.

## Out of scope

- Login forms/sessions.
- CSRF cookies.
- Multi-user auth.

## Verification

- FastAPI TestClient tests for protected/unprotected modes.
- Tests for confirmation requirement on mutating endpoints.
- CLI test for `--require-token` behavior.
- Full pytest suite.
