import logging
import os
import sys
import threading
import time

import rich.logging
import watchdog.events
import watchdog.observers

from .lib.docker import (
    build_and_push_ahaz_image,
    create_local_registry,
    delete_local_registry,
    docker_is_available,
)
from .lib.kubernetes import (
    create_kind_cluster,
    delete_kind_cluster,
    forward_ahaz_port,
    install_ahaz,
    install_cilium,
    install_kyverno,
    is_helm_installed,
    is_kind_installed,
    restart_ahaz,
    setup_local_registry_in_kind,
)

logger = logging.getLogger()
logger.addHandler(rich.logging.RichHandler(markup=True))
logger.setLevel(logging.INFO)


def init_cluster():
    if not is_kind_installed():
        logger.error("Kind is not installed. Please install Kind to proceed.")
        sys.exit(1)

    if not is_helm_installed():
        logger.error("Helm is not installed. Please install Helm to proceed.")
        sys.exit(1)

    if not docker_is_available():
        logger.error("Docker is not available. Please ensure Docker is running and accessible to proceed.")
        sys.exit(1)

    create_kind_cluster()

    create_local_registry()

    setup_local_registry_in_kind()

    install_cilium()

    install_kyverno()

    build_and_push_ahaz_image()

    install_ahaz()


def delete_cluster():
    delete_kind_cluster()

    delete_local_registry()


def build(forward=True):
    if not docker_is_available():
        logger.error("Docker is not available. Please ensure Docker is running and accessible to proceed.")
        sys.exit(1)

    build_and_push_ahaz_image()
    restart_ahaz()
    if forward:
        logger.info("Forwarding Ahaz API to localhost:8080...")
        forward_ahaz_port()


def watch_forward():
    logger.info("Forwarding Ahaz API to localhost:8080...")
    while True:
        forward_ahaz_port()


# Watches root directory for changes and rebuilds and redeploys Ahaz on change
def watch():
    if not docker_is_available():
        logger.error("Docker is not available. Please ensure Docker is running and accessible to proceed.")
        sys.exit(1)

    root = __import__("pathlib").Path(__file__).resolve().parent.parent.parent
    logger.info("Building and deploying Ahaz to cluster...")
    build(forward=False)
    logger.info(f"Watching {root} for changes to Ahaz source code...")

    # Forward Ahaz port in a separate thread so it doesn't block the file watcher
    threading.Thread(target=watch_forward, daemon=True).start()

    class ChangeHandler(watchdog.events.FileSystemEventHandler):
        def on_modified(self, event):
            if event.is_directory:
                return
            path = os.fspath(event.src_path)
            if isinstance(path, (bytes, bytearray)):
                path = path.decode(errors="ignore")
            if path.endswith((".py", ".yaml", ".yml")) or "Dockerfile" in path.split(os.sep)[-1]:
                logger.info(f"Change detected in {event.src_path}, rebuilding and redeploying Ahaz...")
                build(forward=False)

    event_handler = ChangeHandler()
    observer = watchdog.observers.Observer()
    observer.schedule(event_handler, str(root), recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
