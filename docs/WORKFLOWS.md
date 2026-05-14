# Built-in Workflow Presets

Switchboard includes high-value workflow presets so a new repo is useful immediately.

Install them with:

```bash
switchboard workflow install-presets --agent builder --profile launch
```

Preset installation upserts by workflow name, so reinstalling a profile refreshes any built-in preset with the same name.

Profiles:

- `daily` — lightweight routines for daily agent ops.
- `launch` — fuller public-launch prep routines.

## Presets

### `daily-triage`

Reviews open tasks, agent statuses, inbox items, and workflow history. Returns the top next actions and blockers.

### `code-review`

Runs an independent review pass over the current repo diff. Looks for security issues, logic bugs, missing tests, and public-launch polish gaps.

### `bugfix-loop`

Finds a high-impact failing test or rough edge, reproduces it, writes or updates a regression test, fixes it, and summarizes changed files.

### `feature-build`

Takes one scoped feature from the task board through TDD, docs, verification, and handoff.

### `launch-audit`

Audits README clarity, install path, demo flow, CI, security/secrets, screenshots, licensing, and first-user value.

## Why presets matter

Without presets, Switchboard is an agent terminal manager. With presets, it becomes an operating system for repeated agent workflows: review, fix, build, audit, triage.
