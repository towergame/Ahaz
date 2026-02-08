import logging
import subprocess
from .config import REGISTRY_NAME, REGISTRY_PORT

logger = logging.getLogger(__name__)

def create_local_registry():
    try:
        subprocess.run(["docker", "run", "-d", 
                         "--restart=always", 
                         "--name", REGISTRY_NAME, 
                         "-p", f"127.0.0.1:{REGISTRY_PORT}:5000", 
                         "--network", "bridge", 
                         "registry:2"], check=True)
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