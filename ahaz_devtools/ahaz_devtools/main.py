import sys

from .lib.docker import build_and_push_ahaz_image, create_local_registry, delete_local_registry
from .lib.kubernetes import (
    create_kind_cluster,
    delete_kind_cluster,
    install_ahaz,
    install_cilium,
    install_kyverno,
    is_helm_installed,
    is_kind_installed,
    setup_local_registry_in_kind,
)


def init_cluster():
    if not is_kind_installed():
        print("Kind is not installed. Please install Kind to proceed.")
        sys.exit(1)

    if not is_helm_installed():
        print("Helm is not installed. Please install Helm to proceed.")
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
