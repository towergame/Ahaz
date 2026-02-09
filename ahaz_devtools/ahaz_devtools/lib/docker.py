import logging
import subprocess

from .config import REGISTRY_NAME, REGISTRY_PORT

logger = logging.getLogger(__name__)


def create_local_registry():
    try:
        subprocess.run(
            [
                "docker",
                "run",
                "-d",
                "--restart=always",
                "--name",
                REGISTRY_NAME,
                "-p",
                f"127.0.0.1:{REGISTRY_PORT}:5000",
                "--network",
                "bridge",
                "registry:2",
            ],
            check=True,
        )
        logger.info("Local Docker registry created successfully.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to create local Docker registry: {e}")
        raise


def delete_local_registry():
    try:
        subprocess.run(["docker", "rm", "-f", REGISTRY_NAME], check=True)
        logger.info("Local Docker registry deleted successfully.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to delete local Docker registry: {e}")
        raise


def build_and_push_ahaz_image():
    try:
        # Build the Ahaz controller image
        subprocess.run(
            [
                "docker",
                "build",
                "-t",
                f"localhost:{REGISTRY_PORT}/ahaz:latest",
                ".",
                "-f",
                f"{
                    __import__('pathlib').Path(__file__).resolve().parent.parent.parent.parent
                    / 'Dockerfile.controller'
                }",
            ],
            check=True,
        )
        logger.info("Ahaz controller image built successfully.")

        # Push the image to the local registry
        subprocess.run(
            ["docker", "push", f"localhost:{REGISTRY_PORT}/ahaz:latest"],
            check=True,
        )
        logger.info("Ahaz controller image pushed to local registry successfully.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to build or push Ahaz controller image: {e}")
        raise
