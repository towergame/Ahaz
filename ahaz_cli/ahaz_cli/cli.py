import logging
from pathlib import Path

import rich.logging
import typer

log = logging.getLogger()
log.addHandler(rich.logging.RichHandler())
log.setLevel(logging.INFO)

SCRIPTS_ROOT = Path(__file__).parent.parent.resolve()

app = typer.Typer(
    no_args_is_help=True,
    help="""\
CLI for interacting with the Ahaz CTF task manager.
""",
)


if __name__ == "__main__":
    app()
