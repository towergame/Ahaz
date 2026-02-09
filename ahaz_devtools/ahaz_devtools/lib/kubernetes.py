import logging
import subprocess

from .config import REGISTRY_DIR, REGISTRY_NAME, REGISTRY_PORT

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
        subprocess.run(
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
            check=True,
        )
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


def setup_local_registry_in_kind(cluster_name="ahaz-dev"):
    try:
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
            subprocess.run(
                ["docker", "exec", node, "mkdir", "-p", certs_dir],
                check=True,
            )

            # Proper containerd hosts.toml format
            registry_config = f"""
server = "http://{registry_host}"

[host."http://{registry_host}"]
  capabilities = ["pull", "resolve"]
  skip_verify = true
"""

            subprocess.run(
                ["docker", "exec", "-i", node, "cp", "/dev/stdin", f"{certs_dir}/hosts.toml"],
                input=registry_config.encode(),
                check=True,
            )

        # Connect registry container to kind network (ignore if already connected)
        subprocess.run(
            ["docker", "network", "connect", "kind", REGISTRY_NAME],
            check=False,
        )

        logger.info("Local registry successfully configured for kind cluster.")

    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to configure local registry for kind: {e}")
        raise


def install_cilium():
    try:
        subprocess.run(["helm", "repo", "add", "cilium", "https://helm.cilium.io/"], check=True)

        subprocess.run(
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
            check=True,
        )
        subprocess.run(["kubectl", "rollout", "status", "ds/cilium", "-n", "kube-system"], check=True)
        logger.info("Cilium installed successfully.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to install Cilium: {e}")
        raise


def install_kyverno():
    try:
        subprocess.run(
            [
                "helm",
                "repo",
                "add",
                "kyverno",
                "https://kyverno.github.io/kyverno/",
            ],
            check=True,
        )
        subprocess.run(
            [
                "helm",
                "install",
                "kyverno",
                "kyverno/kyverno",
                "--namespace",
                "kyverno",
                "--create-namespace",
            ],
            check=True,
        )
        subprocess.run(
            ["kubectl", "rollout", "status", "deploy/kyverno-admission-controller", "-n", "kyverno"],
            check=True,
        )
        logger.info("Kyverno installed successfully.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to install Kyverno: {e}")
        raise


def install_ahaz():
    try:
        subprocess.run(
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
            check=True,
        )
        subprocess.run(["kubectl", "rollout", "status", "deploy/ahaz", "-n", "ahaz"], check=True)
        logger.info("Ahaz installed successfully.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to install Ahaz: {e}")
        raise
