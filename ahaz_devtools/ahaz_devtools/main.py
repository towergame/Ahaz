import sys

from .lib.kubernetes import create_kind_cluster, delete_kind_cluster, install_cilium, is_helm_installed, is_kind_installed
from .lib.docker import create_local_registry, delete_local_registry

def init_cluster():
    # Test for kind
    if not is_kind_installed():
        print("Kind is not installed. Please install Kind to proceed.")
        sys.exit(1)

    if not is_helm_installed():
        print("Helm is not installed. Please install Helm to proceed.")
        sys.exit(1)

    # Create a kind cluster
    create_kind_cluster()

    # Create local Docker registry
    create_local_registry()

    # Install Cilium
    install_cilium()


def delete_cluster():
    delete_kind_cluster()

    delete_local_registry()