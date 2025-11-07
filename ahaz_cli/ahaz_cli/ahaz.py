import logging
from pathlib import Path
from typing import Annotated, Optional

import docker
import docker.errors
import rich
import rich.json
import typer
from rich.status import Status

log = logging.getLogger(__name__)
CWD = Path.cwd()


def test():
    pass
