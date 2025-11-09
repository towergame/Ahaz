import logging
from pathlib import Path
from typing import Annotated

import docker
import docker.errors
import typer
from rich.status import Status

from .lib.docker import cleanup_env, create_env, log_docker_logs, try_build_image
from .lib.file import test_for_file
from .lib.task import deserialise_task

log = logging.getLogger(__name__)
CWD = Path.cwd()


def test(
    build: Annotated[bool, typer.Option("--build", "-b", help="Always build Docker images")] = False,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Enable verbose logging")] = False,
    up: Annotated[bool, typer.Option("--up", "-u", help="Start the task environment after testing")] = False,
) -> None:
    if verbose:
        log.setLevel(logging.DEBUG)

    config = "task.yaml"
    if not test_for_file(config):
        config = "task.yml"
        if not test_for_file(config):
            log.error("No task configuration file found (task.yaml or task.yml)")
            log.error("Are you sure you are in the task directory?")
            raise FileNotFoundError("No task configuration file found (task.yaml or task.yml)")

    task = deserialise_task(Path(config).read_text())
    log.info(f"Loaded task: {task.name}")

    log.info("Testing Docker images for all pods...")
    client = docker.from_env()
    for pod in task.pods:
        with Status(f"Checking image for pod '{pod.k8s_name}'...", spinner="dots") as status:
            image_tag = f"{pod.image.image_name}:{task.version}"
            if not build:
                # See if we can find the image locally
                try:
                    client.images.get(image_tag)
                    status.update(f"Image '{image_tag}' found locally.")
                    log.info(f"Image '{image_tag}' found locally for pod '{pod.k8s_name}'.")
                    continue
                except docker.errors.ImageNotFound:
                    log.info(f"Image '{image_tag}' not found locally for pod '{pod.k8s_name}', building...")
            # Build the image
            status.update(f"Building image '{image_tag}'...")
            log.info(f"Building image '{image_tag}' for pod '{pod.k8s_name}'...")
            build_args = {arg.name: arg.value for arg in (pod.image.build_args or [])}
            try:
                try_build_image(image_tag, pod.image.build_context, build_args, verbose)
            except Exception as e:
                log.error(f"Failed to build image '{image_tag}' for pod '{pod.k8s_name}': {e}")
                raise e

    # Attempt to set up the entire task environment
    if up:
        log.info("Setting up the task environment...")
        containers = create_env(task)
        log_docker_logs(
            containers,
            lambda: cleanup_env(
                task.name, [pod.k8s_name for pod in task.pods], [net.netname for net in task.networks]
            ),
        )
    log.info("Task test completed.")


# Load bearing function, do not remove :3
def epic() -> None:
    log.info("[bold magenta]Epic function called![/bold magenta]")
