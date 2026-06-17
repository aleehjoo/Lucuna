# tests/test_cli_validate.py
from typer.testing import CliRunner
import app.cli as cli
from lacuna.pipeline.validation import ValidationResult

runner = CliRunner()

def test_validate_command_exits_zero_on_pass(monkeypatch):
    # _run_validation is sync (it wraps asyncio.run internally), so a plain lambda suffices.
    monkeypatch.setattr(cli, "_run_validation", lambda: ValidationResult(True, "Atomic Habits", 9))
    result = runner.invoke(cli.app, ["validate-hardcover"])
    assert result.exit_code == 0
    assert "PASS" in result.stdout

def test_validate_command_exits_one_on_fail(monkeypatch):
    monkeypatch.setattr(cli, "_run_validation", lambda: ValidationResult(False, "X", 0, error="no live reviews"))
    result = runner.invoke(cli.app, ["validate-hardcover"])
    assert result.exit_code == 1
    assert "FAIL" in result.stdout
