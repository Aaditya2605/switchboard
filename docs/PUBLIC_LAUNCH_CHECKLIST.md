# Public Launch Checklist

Use this before making the repository public.

## Must pass

- [ ] `uv run --with-editable . --with pytest --with httpx pytest -q`
- [ ] `uv run --with-editable . switchboard --help`
- [ ] GitHub Actions CI passes on Python 3.11 and 3.12
- [ ] README explains the product in one sentence
- [ ] README has install, quick demo, dashboard, safety, and workflow preset sections
- [ ] `docs/DEMO.md` works from a clean checkout
- [ ] `docs/WORKFLOWS.md` explains presets
- [ ] `docs/SECURITY.md` explains token handling and dashboard exposure limits

## Secrets/private-info audit

Run before public visibility:

```bash
git grep -n -I -E "(api[_-]?key|secret|password|token|BEGIN PRIVATE KEY|ghp_|xoxb-|sk-[A-Za-z0-9])" -- . \
  ':!.git' ':!.venv' ':!*.pyc'
```

Expected result: only placeholder or environment-variable references, never real values.

Any example credential must be written as `[REDACTED]` or an obvious placeholder.

## Demo assets

- [ ] Add a dashboard screenshot
- [ ] Add a 30-60 second GIF/video showing:
  1. spawn/register two agents
  2. install workflow presets
  3. create/move a task
  4. send a dashboard prompt
  5. run a workflow

## Public repo polish

- [ ] Add `LICENSE`
- [ ] Add issue templates if desired
- [ ] Add release tag after CI passes
- [ ] Decide whether default branch should be `main` or stay `master`
