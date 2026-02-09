import logging
import subprocess

from .config import REGISTRY_DIR, REGISTRY_NAME, REGISTRY_PORT
from .subprocess import execute_into_logger

logger = logging.getLogger(__name__)


def get_k8s_api_ip():
    # Get IP address of the controller node
    result = subprocess.run(
        [
            "kubectl",
            "get",
            "nodes",
            "-o",
            "jsonpath={.items[0].status.addresses[?(@.type=='InternalIP')].address}",
        ],
        check=True,
        stdout=subprocess.PIPE,
    )
    controller_ip = result.stdout.decode().strip()
    return controller_ip


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
        logger.info("Creating kind cluster 'ahaz-dev'...")
        # Run kind create cluster and stream its output to the logger as it runs
        execute_into_logger(
            [
                "kind",
                "create",
                "cluster",
                "--name",
                "ahaz-dev",
                "--config",
                f"{
                    __import__('pathlib').Path(__file__).resolve().parent.parent
                    / 'assets'
                    / 'kind-config.yml'
                }",
            ],
            logger,
        )
        logger.info("Kind cluster 'ahaz-dev' created successfully.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to create kind cluster: {e}")
        raise


def delete_kind_cluster():
    try:
        logger.info("Deleting kind cluster 'ahaz-dev'...")
        execute_into_logger(["kind", "delete", "cluster", "--name", "ahaz-dev"], logger)
        logger.info("Kind cluster 'ahaz-dev' deleted successfully.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to delete kind cluster: {e}")
        raise


def setup_local_registry_in_kind(cluster_name="ahaz-dev"):
    try:
        logger.info(f"Setting up local registry in kind cluster '{cluster_name}'...")
        # Get kind nodes
        result = subprocess.run(
            ["kind", "get", "nodes", "--name", cluster_name],
            check=True,
            stdout=subprocess.PIPE,
            text=True,
        )
        nodes = result.stdout.splitlines()

        registry_host = f"{REGISTRY_NAME}:5000"
        certs_dir = f"/etc/containerd/certs.d/{registry_host}"

        for node in nodes:
            logger.info(f"Configuring local registry for kind node: {node}")

            # Create registry config directory inside node
            execute_into_logger(
                ["docker", "exec", node, "mkdir", "-p", certs_dir],
                logger,
            )

            # Proper containerd hosts.toml format
            registry_config = f"""
server = "http://{registry_host}"

[host."http://{registry_host}"]
  capabilities = ["pull", "resolve"]
  skip_verify = true
"""

            execute_into_logger(
                ["docker", "exec", "-i", node, "cp", "/dev/stdin", f"{certs_dir}/hosts.toml"],
                logger,
                input=registry_config,
            )

        # Connect registry container to kind network (ignore if already connected)
        execute_into_logger(["docker", "network", "connect", "kind", REGISTRY_NAME], logger)

        logger.info("Local registry successfully configured for kind cluster.")

    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to configure local registry for kind: {e}")
        raise


def install_cilium():
    try:
        logger.info("Installing Cilium CNI...")
        execute_into_logger(["helm", "repo", "add", "cilium", "https://helm.cilium.io/"], logger)

        execute_into_logger(
            [
                "helm",
                "install",
                "cilium",
                "cilium/cilium",
                "--namespace",
                "kube-system",
                "--set",
                "kubeProxyReplacement=true",
                "--set",
                f"k8sServiceHost={get_k8s_api_ip()}",
                "--set",
                "k8sServicePort=6443",
                "--set",
                "ipam.mode=kubernetes",
            ],
            logger,
        )
        execute_into_logger(["kubectl", "rollout", "status", "ds/cilium", "-n", "kube-system"], logger)
        logger.info("Cilium installed successfully.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to install Cilium: {e}")
        raise


def install_kyverno():
    try:
        logger.info("Installing Kyverno...")
        execute_into_logger(
            [
                "helm",
                "repo",
                "add",
                "kyverno",
                "https://kyverno.github.io/kyverno/",
            ],
            logger,
        )
        execute_into_logger(
            [
                "helm",
                "install",
                "kyverno",
                "kyverno/kyverno",
                "--namespace",
                "kyverno",
                "--create-namespace",
            ],
            logger,
        )
        execute_into_logger(
            ["kubectl", "rollout", "status", "deploy/kyverno-admission-controller", "-n", "kyverno"],
            logger,
        )
        logger.info("Kyverno installed successfully.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to install Kyverno: {e}")
        raise


def install_ahaz():
    try:
        logger.info("Installing Ahaz...")
        execute_into_logger(
            [
                "helm",
                "install",
                "ahaz",
                "oci://ghcr.io/martina-ctf/helm-charts/ahaz",
                "--namespace",
                "ahaz",
                "--create-namespace",
                "--values",
                f"{
                    __import__('pathlib').Path(__file__).resolve().parent.parent
                    / 'assets'
                    / 'ahaz-values.yml'
                }",
                "--set",
                f"controller.image.repository={REGISTRY_NAME}:5000/ahaz",
                "--set",
                f"kubernetes.k8sApiServiceCidr={get_k8s_api_ip()}/32",
            ],
            logger,
        )
        execute_into_logger(["kubectl", "rollout", "status", "deploy/ahaz", "-n", "ahaz"], logger)
        logger.info("Ahaz installed successfully.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to install Ahaz: {e}")
        raise


def is_ahaz_forwarded():
    try:
        result = subprocess.run(
            ["kubectl", "get", "svc/ahaz", "-n", "ahaz", "-o", "jsonpath={.spec.ports[0].nodePort}"],
            check=True,
            stdout=subprocess.PIPE,
            text=True,
        )
        node_port = result.stdout.strip()
        return node_port == "8080"
    except subprocess.CalledProcessError:
        return False


def forward_ahaz_port():
    if is_ahaz_forwarded():
        logger.info("Ahaz API is already forwarded to localhost:8080")
        return

    try:
        execute_into_logger(
            ["kubectl", "port-forward", "svc/ahaz", "8080:5000", "-n", "ahaz"],
            logger,
        )
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to forward Ahaz API: {e}")
        raise


def restart_ahaz():
    try:
        logger.info("Restarting Ahaz deployment...")
        execute_into_logger(["kubectl", "rollout", "restart", "deploy/ahaz", "-n", "ahaz"], logger)
        execute_into_logger(["kubectl", "rollout", "status", "deploy/ahaz", "-n", "ahaz"], logger)
        logger.info("Ahaz restarted successfully!")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to restart Ahaz: {e}")
        raise
