# tests/test_cli_commands.py
import typer
import app.cli as cli

def test_all_commands_registered():
    group = typer.main.get_command(cli.app)
    names = set(group.commands.keys())
    assert {"validate-hardcover", "seed", "analyze", "sweep", "export"}.issubset(names)
