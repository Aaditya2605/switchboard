from typer.testing import CliRunner

import switchboard.cli as cli
from switchboard.cli import app


runner = CliRunner()


def test_dashboard_command_help():
    result = runner.invoke(app, ["dashboard", "--help"])

    assert result.exit_code == 0
    assert "--host" in result.output
    assert "--port" in result.output
    assert "--require-token" in result.output


def test_dashboard_require_token_fails_without_env(monkeypatch):
    monkeypatch.delenv("SWITCHBOARD_DASHBOARD_TOKEN", raising=False)

    result = runner.invoke(app, ["dashboard", "--require-token"])

    assert result.exit_code == 1
    assert "SWITCHBOARD_DASHBOARD_TOKEN is required" in result.output


def test_dashboard_passes_env_token_to_app(monkeypatch):
    captured = {}

    def fake_create_app(service, auth_token=None):
        captured["auth_token"] = auth_token
        return object()

    def fake_run(app, host, port):
        captured["host"] = host
        captured["port"] = port

    monkeypatch.setenv("SWITCHBOARD_DASHBOARD_TOKEN", "secret-token")
    monkeypatch.setattr(cli, "create_app", fake_create_app)
    monkeypatch.setattr(cli, "service", lambda: object())
    monkeypatch.setattr(cli.uvicorn, "run", fake_run)

    result = runner.invoke(app, ["dashboard", "--require-token", "--port", "9999"])

    assert result.exit_code == 0
    assert captured["auth_token"] == "secret-token"
    assert captured["port"] == 9999
