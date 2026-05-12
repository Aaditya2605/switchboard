from typer.testing import CliRunner

from switchboard.cli import app


runner = CliRunner()


def test_dashboard_command_help():
    result = runner.invoke(app, ["dashboard", "--help"])

    assert result.exit_code == 0
    assert "--host" in result.output
    assert "--port" in result.output
