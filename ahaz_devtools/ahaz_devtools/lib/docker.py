import logging
from datetime import datetime
from pathlib import Path

import docker
from ahaz_devtools.lib.subprocess import execute_into_logger

from .config import REGISTRY_NAME, REGISTRY_PORT

logger = logging.getLogger(__name__)


def create_local_registry():
    logger.info("Creating local Docker registry...")
    client = docker.from_env()
    run_logs = client.containers.run(
        image="registry:2",
        name=REGISTRY_NAME,
        detach=True,
        restart_policy={"Name": "always"},
        ports={"5000/tcp": ("127.0.0.1", REGISTRY_PORT)},
    )
    while run_logs.status != "running":
        run_logs.reload()
    logger.debug(run_logs.logs(since=datetime.fromtimestamp(0)).decode())
    logger.info("Local Docker registry created successfully.")


def delete_local_registry():
    logger.info("Deleting local Docker registry...")
    client = docker.from_env()
    client.containers.get(REGISTRY_NAME).remove(force=True)
    logger.info("Local Docker registry deleted successfully.")


def build_and_push_ahaz_image():
    logger.info("Building Ahaz controller image...")

    dockerfile_path = Path(__file__).resolve().parent.parent.parent.parent / "Dockerfile.controller"

    execute_into_logger(
        [
            "docker",
            "build",
            "-t",
            f"localhost:{REGISTRY_PORT}/ahaz:latest",
            "-f",
            str(dockerfile_path),
            ".",
        ],
        logger,
        log_level=logging.INFO,
    )

    logger.info("Pushing image...")

    execute_into_logger(
        [
            "docker",
            "push",
            f"localhost:{REGISTRY_PORT}/ahaz:latest",
        ],
        logger,
    )

    logger.info("Push complete.")
