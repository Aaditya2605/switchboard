# Security Notes

Switchboard is local-first software. Treat it as a control plane that can send prompts into persistent agent sessions and move work forward.

## Dashboard exposure

Default dashboard usage binds to localhost:

```bash
switchboard dashboard --host 127.0.0.1 --port 8765
```

If you expose it through Tailscale, ngrok, a tunnel, or a non-localhost interface, require a token:

```bash
export SWITCHBOARD_DASHBOARD_TOKEN=replace-with-local-token
switchboard dashboard --require-token
```

Authenticated requests must include:

```http
Authorization: Bearer [REDACTED]
```

## Confirmed mutations

Mutating dashboard/API actions require explicit confirmation:

```json
{"confirm": true}
```

This applies to prompt sends, task moves, workflow creation, and workflow runs.

## Secrets

Do not commit:

- Telegram bot tokens
- GitHub tokens
- dashboard bearer tokens
- API keys
- private keys
- personal brain/private notes

Use environment variables instead.

## Responsible disclosure

If this repo becomes public and you find a vulnerability, open a private security advisory or contact the maintainer directly. Do not publish working exploits against exposed dashboards.
