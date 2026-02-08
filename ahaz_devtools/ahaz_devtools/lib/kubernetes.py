import logging
import subprocess

from .config import REGISTRY_DIR, REGISTRY_NAME

logger = logging.getLogger(__name__)

def is_kind_installed():
    try:
        subprocess.run(["kind", "version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except subprocess.CalledProcessError:
        return False


def is_helm_installed():
    try:
        subprocess.run(["helm", "version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except subprocess.CalledProcessError:
        return False


def create_kind_cluster():
    try:
        subprocess.run(["kind", "create", "cluster", "--name", "ahaz-dev", "--config", f"{__import__('pathlib').Path(__file__).resolve().parent / 'assets' / 'kind-config.yml'}"], check=True)
        logger.info("Kind cluster 'ahaz-dev' created successfully.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to create kind cluster: {e}")
        raise


def delete_kind_cluster():
    try:
        subprocess.run(["kind", "delete", "cluster", "--name", "ahaz-dev"], check=True)
        logger.info("Kind cluster 'ahaz-dev' deleted successfully.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to delete kind cluster: {e}")
        raise


def setup_local_registry_in_kind():
    try:
        # Define the registry configuration for kind nodes
        for node in subprocess.run(["kind", "get", "nodes", "--name", "ahaz-dev"], check=True, stdout=subprocess.PIPE).stdout.decode().splitlines():
            subprocess.run(["docker", "exec", node, "mkdir", "-p", REGISTRY_DIR], check=True)
            registry_config = f"[host.\"http://{REGISTRY_NAME}:5000\"]\n"
            subprocess.run(["docker", "exec", "-i", node, "cp", "/dev/stdin", REGISTRY_DIR + "/hosts.toml"], input=registry_config.encode(), check=True)
            logger.info(f"Configured local registry for kind node: {node}")
        
        # Connect the local registry to the kind network
        subprocess.run(["docker", "network", "connect", "kind", REGISTRY_NAME], check=True)
        logger.info("Local registry connected to kind network successfully.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to connect local registry to kind network: {e}")
        raise


def install_cilium():
    try:
        subprocess.run(["helm", "repo", "add", "cilium", "https://helm.cilium.io/"], check=True)
        subprocess.run(["helm", "install", "cilium", "cilium/cilium", "--namespace", "kube-system",
                        "--set", "kubeProxyReplacement=strict",
                        "--set", "k8sServiceHost=localhost",
                        "--set", "k8sServicePort=6443"], check=True)
        subprocess.run(["kubectl", "rollout", "status", "ds/cilium-node", "-n", "kube-system"], check=True)
        logger.info("Cilium installed successfully.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to install Cilium: {e}")
        raise