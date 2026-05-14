# Public Launch Checklist

Use this before making the repository public.

## Must pass

- [x] `uv run --with-editable . --with pytest --with httpx pytest -q` (137 passing as of 2026-05-14)
- [x] `uv run --with-editable . switchboard --help`
- [ ] GitHub Actions CI passes on Python 3.11 and 3.12 (verify before flipping public)
- [x] README explains the product in one sentence
- [x] README has install, quick demo, dashboard, safety, and workflow preset sections
- [x] README documents worktrees, agent kinds, `switchboard run`, and the multi-page dashboard
- [x] `docs/DEMO.md` works from a clean checkout
- [x] `docs/DOGFOOD.md` shows a real end-to-end claude + codex run
- [x] `docs/WORKFLOWS.md` explains presets
- [x] `docs/SECURITY.md` explains token handling and dashboard exposure limits
- [x] CHANGELOG covers the Unreleased work shipped in the v0.2 batch

## Secrets/private-info audit

Run before public visibility:

```bash
git grep -n -I -E "(api[_-]?key|secret|password|token|BEGIN PRIVATE KEY|ghp_|xoxb-|sk-[A-Za-z0-9])" -- . \
  ':!.git' ':!.venv' ':!*.pyc'
```

Expected result: only placeholder or environment-variable references, never real values.

Any example credential must be written as `[REDACTED]` or an obvious placeholder.

## Demo assets

- [x] Dashboard screenshot — see `docs/assets/dashboard-preview.png` and 9 page-level captures under `docs/assets/screenshots/`
- [ ] 30-60 second GIF/video showing:
  1. spawn/register two agents (`--worktree`)
  2. install workflow presets
  3. create a task, dispatch with `switchboard run`
  4. open the task detail page to see the captured response
  5. flip the Live toggle and watch the next state change reload the page

## Public repo polish

- [x] `LICENSE` present (MIT)
- [ ] Add issue templates if desired
- [ ] Add release tag once CI is green and one human has eyeballed the README
- [ ] Decide whether default branch should be `main` or stay `master`
