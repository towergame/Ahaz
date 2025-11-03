import json
import logging
import os
import time

import certmanager
import dboperator
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

# This file has `#type: ignore` comments to ignore type checking errors from the kubernetes client library,
# which has weird/bad type annotations.
# Woe.

logger = logging.getLogger()

PUBLIC_DOMAINNAME = os.getenv("PUBLIC_DOMAINNAME", "ahaz.lan")

# Quick heuristic to determine if the kube folder has a valid kubeconfig file
# or merely a service account token.


def is_valid_kubeconfig(kube_folder: str) -> bool:
    # Check for the presence of a valid kubeconfig file
    kubeconfig_path = os.path.join(kube_folder, "config")
    if os.path.exists(kubeconfig_path):
        return True

    # Check for the presence of a service account token
    token_path = os.path.join(kube_folder, "token")
    if os.path.exists(token_path):
        return True

    return False


def load_kube_config():
    # Load kube config based on environment
    if is_valid_kubeconfig("/.kube"):
        config.load_kube_config(config_file="/.kube/config")
    else:
        config.load_incluster_config()


def should_retry_request(exception):
    """Return True if the exception is an ApiException with a status worth retrying."""
    is_forbidden = (
        isinstance(exception, ApiException)
        and exception.status
        and (
            exception.status == 403  # Forbidden
            # theoretically a lost cause but in the case of the example deployment
            # the service account might not have the role yet
            or exception.status == 429  # Too Many Requests
            or exception.status >= 500  # Server errors
        )
    )
    return is_forbidden


retry_opts = {
    "retry": retry_if_exception(should_retry_request),  # type: ignore
    "stop": stop_after_attempt(5),  # Stop after 5 attempts
    "wait": wait_exponential(multiplier=1, min=2, max=10),  # Exponential backoff
}


@retry(**retry_opts)
def create_network_policy_deny_all(namespace: str) -> client.V1NetworkPolicy:
    # Load kube config (for local development)
    load_kube_config()

    try:
        policy = client.V1NetworkPolicy(
            api_version="networking.k8s.io/v1",
            kind="NetworkPolicy",
            metadata=client.V1ObjectMeta(name="deny-all"),
            spec=client.V1NetworkPolicySpec(
                pod_selector=client.V1LabelSelector(match_labels={}),
                policy_types=["Ingress", "Egress"],
                ingress=[],
                egress=[],
            ),
        )
        return policy
    except ApiException as e:
        if e.status != 403:
            logger.error(f"API Exception when creating deny-all network policy: {e}")
        raise e


@retry(**retry_opts)
def create_network_policy(namespace: str) -> client.V1NetworkPolicy:
    # Load kube config (for local development)
    # Te vajag consul sataisīt https://www.hashicorp.com/en/resources/service-discovery-with-consul-on-kubernetes
    load_kube_config()

    try:
        policy = client.V1NetworkPolicy(
            api_version="networking.k8s.io/v1",
            kind="NetworkPolicy",
            metadata=client.V1ObjectMeta(name="restrict-vpn-access"),
            spec=client.V1NetworkPolicySpec(
                pod_selector=client.V1LabelSelector(match_labels={"name": "vpn-container-pod"}),
                policy_types=["Ingress", "Egress"],
                ingress=[
                    client.V1NetworkPolicyIngressRule(
                        ports=[
                            client.V1NetworkPolicyPort(protocol="TCP", port=1194),
                            client.V1NetworkPolicyPort(protocol="UDP", port=1194),
                        ]
                    )
                ],
                egress=[
                    # Explicitly deny all egress traffic by default
                    # client.V1NetworkPolicyEgressRule(to=[]),
                    # Allow communication only within the same namespace
                    client.V1NetworkPolicyEgressRule(
                        to=[
                            client.V1NetworkPolicyPeer(
                                pod_selector=client.V1LabelSelector(match_labels={"team": namespace})
                            )
                        ]
                        # to=[client.V1NetworkPolicyPeer(pod_selector=client.V1LabelSelector(match_labels={}))]
                    )
                ],
            ),
        )
        return policy
    except ApiException as e:
        if e.status != 403:
            logger.error(f"API Exception when creating restrict-vpn-access network policy: {e}")
        raise e


container_registry_creds_name = "regcred"
certDirLocationContainer = os.getenv("CERT_DIR_CONTAINER", "/etc/ahaz/certdir")


# TODO: fix unused params
@retry(**retry_opts)
def start_challenge_pod(
    teamname: str,
    k8s_name: str,
    image: str,
    ram: str,
    cpu: str,
    storage: str,
    visible_to_user: bool,
    networklist: list[str],
    taskname: str,
) -> None:
    load_kube_config()
    try:
        k8s_client = client.CoreV1Api()
        taskname = taskname.replace(" ", "-")
        storage = storage.replace("Gb", "Gi")
        ram = ram.replace("Gb", "Gi")
        env_vars = dboperator.cicd_get_env_vars(k8s_name)
        pod_manifest = {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {
                "name": k8s_name,
                "labels": {
                    "team": teamname,
                    "visible": str(
                        visible_to_user
                    ),  # used to identify if this pods IP address will be shown to user.
                    "task": taskname,  # identifies the task this pod belongs to, necessary for network policies
                    "name": k8s_name,  # used for service selector
                },
            },
            "spec": {
                "containers": [
                    {
                        "image": image,
                        "name": "container",
                        "env": env_vars,
                        #'resources':{
                        #    'limits':{
                        #        'memory':ram,
                        #        'cpu':str(cpu),
                        #        'ephemeral-storage':storage
                        #    }
                        # }
                    }
                ],
                "imagePullSecrets": [{"name": container_registry_creds_name}],
            },
        }
        logger.debug(pod_manifest)
        k8s_client.create_namespaced_pod(namespace=teamname, body=pod_manifest)
        create_pod_service(teamname, taskname, k8s_name)
    except ApiException as e:
        if e.status != 403:
            logger.error(f"API Exception when starting challenge pod: {e}")
        raise e


@retry(**retry_opts)
def start_challenge(teamname: str, challengename: str) -> int:
    try:
        logger.debug(" a")
        db_pods_data = dboperator.cicd_get_pods(challengename)
        for i in db_pods_data:
            logger.debug(i)
            k8s_name, image, ram, cpu, visible_to_user = i[1:]
            # =
            storage = "2Gb"
            netnames = dboperator.cicd_get_k8s_name_networks(k8s_name)
            networklist = []
            for i in netnames:
                networklist.append(i.replace("teamnet", teamname))
            start_challenge_pod(
                teamname, k8s_name, image, ram, cpu, storage, visible_to_user, networklist, challengename
            )
        create_challenge_network_policies(teamname, challengename)
        return 0
    except ApiException as e:
        if e.status != 403:
            logger.error(f"API Exception when starting challenge: {e}")
        raise e


# TODO: Split this function up to reduce complexity
# TODO: showInvisible should be a bool
@retry(**retry_opts)
def get_pods_namespace(teamname: str, showInvisible: int) -> str:
    load_kube_config()
    try:
        k8s_client = client.CoreV1Api()
        pod_list = k8s_client.list_namespaced_pod(teamname)
        pod_info = []
        pod_info_json = "["
        first = True
        try:
            for pod in pod_list.items:
                if pod.metadata.name == "vpn-container-pod":
                    if pod.metadata.deletion_timestamp is not None and pod.status.phase in (
                        "Pending",
                        "Running",
                    ):
                        state = "Terminating"
                    else:
                        state = str(pod.status.phase)
                    logger.debug("processing vpn container pod")
                    current_pod_info_json = (
                        '{"name":"'
                        + pod.metadata.name
                        + '","status":"'
                        + state
                        + '","ip":"'
                        + pod.status.pod_ip
                        + '"}'
                    )
                    if first:
                        pod_info_json += current_pod_info_json
                        first = False
                    else:
                        pod_info_json += "," + current_pod_info_json
                    continue
                logger.debug("%s\t%s\t%s" % (pod.metadata.name, pod.status.phase, pod.status.pod_ip))
                # because python k8s api does not show status terminating :/
                if pod.metadata.deletion_timestamp is not None and pod.status.phase in ("Pending", "Running"):
                    state = "Terminating"
                else:
                    state = str(pod.status.phase)
                pod_info.append([pod.metadata.name, state, pod.status.pod_ip])
                current_pod_info_json = (
                    '{"status":"'
                    + state
                    + '","ip":"'
                    + pod.status.pod_ip
                    + '","visibleIP":'
                    + pod.metadata.labels["visible"]
                    + ',"task":"'
                    + dboperator.cicd_get_challenge_from_k8s_name(pod.metadata.labels["name"])
                    + '","name":"'
                    + pod.metadata.labels["name"]
                    + '"'
                    + "}"
                )
                logger.debug(current_pod_info_json)
                if first:
                    if ('"visibleIP":1' in current_pod_info_json) or (showInvisible == 1):
                        pod_info_json += current_pod_info_json
                        first = False
                else:
                    if ('"visibleIP":1' in current_pod_info_json) or (showInvisible == 1):
                        pod_info_json += "," + current_pod_info_json
            pod_info_json += "]"
            return pod_info_json
        # TODO: Fix this, or find a better way to handle it \/
        # there is an issue that if I just start up a pod, and immediately request pod statuses
        # it doesn't have an IP assigned yet, and that requires re requesting all pods to be loaded.
        except Exception as e:
            logger.error(f"Failed to get pod info: {e}")
            time.sleep(3)
            pod_list = k8s_client.list_namespaced_pod(teamname)
            for pod in pod_list.items:
                if pod.metadata.name == "vpn-container-pod":
                    if pod.metadata.deletion_timestamp is not None and pod.status.phase in (
                        "Pending",
                        "Running",
                    ):
                        state = "Terminating"
                    else:
                        state = str(pod.status.phase)
                    logger.debug("processing vpn container pod")
                    current_pod_info_json = (
                        '{"name":"'
                        + pod.metadata.name
                        + '","status":"'
                        + state
                        + '","ip":"'
                        + pod.status.pod_ip
                        + '"}'
                    )
                    if first:
                        pod_info_json += current_pod_info_json
                        first = False
                    else:
                        pod_info_json += "," + current_pod_info_json
                    continue
                logger.debug(
                    "%s\t%s\t%s"
                    % (
                        pod.metadata.name,
                        pod.status.phase,
                        pod.status.pod_ip,
                    )
                )
                # because python k8s api does not show status terminating :/
                if pod.metadata.deletion_timestamp is not None and pod.status.phase in ("Pending", "Running"):
                    state = "Terminating"
                else:
                    state = str(pod.status.phase)
                pod_info.append([pod.metadata.name, state, pod.status.pod_ip])
                pod_data = {
                    "name": pod.metadata.labels["name"],
                    "status": state,
                    "ip": pod.status.pod_ip,
                    "visibleIP": int(pod.metadata.labels["visible"]),
                    "task": dboperator.cicd_get_challenge_from_k8s_name(pod.metadata.labels["name"]),
                }
                current_pod_info_json = json.dumps(pod_data)
                logger.debug(current_pod_info_json)
                if first:
                    if ('"visibleIP":1' in current_pod_info_json) or (showInvisible == 1):
                        pod_info_json += current_pod_info_json
                        first = False
                else:
                    if ('"visibleIP":1' in current_pod_info_json) or (showInvisible == 1):
                        pod_info_json += "," + current_pod_info_json
            pod_info_json += "]"
            return pod_info_json
    except ApiException as e:
        if e.status != 403:
            logger.error(f"API Exception when getting pods in namespace {teamname}: {e}")
        raise e


@retry(**retry_opts)
def create_pod_service(teamname: str, taskname: str, k8s_name: str) -> None:
    try:
        load_kube_config()
        api_instance = client.CoreV1Api()

        service = client.V1Service(
            api_version="v1",
            kind="Service",
            metadata=client.V1ObjectMeta(
                name=k8s_name,  # could also be f"{challengename}-service"
                namespace=teamname,
                labels={"task": taskname},
            ),
            spec=client.V1ServiceSpec(
                cluster_ip="None",  # headless service
                selector={"name": k8s_name},
                # ports=[
                #    client.V1ServicePort(
                #        protocol="TCP",
                #        port=0,
                #        target_port=0
                #    )
                # ]
            ),
        )

        # Create the service in Kubernetes
        api_response = api_instance.create_namespaced_service(namespace=teamname, body=service)
        logger.debug(f"Service created. Status='{api_response.status}'")  # type: ignore
    except ApiException as e:
        if e.status != 403:
            logger.error(f"API Exception when creating service for pod {k8s_name}: {e}")
        raise e


@retry(**retry_opts)
def create_network_policy_deny_all_task(teamname: str, challengename: str) -> client.V1NetworkPolicy:
    try:
        sanitized_challengename = challengename.replace(" ", "-").lower()
        taskname = challengename.replace(" ", "-")
        load_kube_config()

        policy = client.V1NetworkPolicy(
            api_version="networking.k8s.io/v1",
            kind="NetworkPolicy",
            metadata=client.V1ObjectMeta(
                name="deny-all-" + sanitized_challengename, labels={"task": challengename.replace(" ", "-")}
            ),
            spec=client.V1NetworkPolicySpec(
                pod_selector=client.V1LabelSelector(match_labels={"task": taskname}),
                policy_types=["Ingress", "Egress"],
                ingress=[],
                egress=[],
            ),
        )
        return policy
    except ApiException as e:
        if e.status != 403:
            logger.error(f"API Exception when creating deny-all network policy for {challengename}: {e}")
        raise e


@retry(**retry_opts)
def create_network_policy_allow_task(
    teamname: str, challengename: str, network_pods: list[str], netname: str
) -> client.V1NetworkPolicy:
    try:
        # Explicitly allow DNS
        dns_peer = client.V1NetworkPolicyPeer(
            namespace_selector=client.V1LabelSelector(
                match_labels={"kubernetes.io/metadata.name": "kube-system"}
            ),
            pod_selector=client.V1LabelSelector(match_labels={"k8s-app": "kube-dns"}),
        )
        dns_egress_rule = client.V1NetworkPolicyEgressRule(
            to=[dns_peer],
            ports=[
                client.V1NetworkPolicyPort(protocol="UDP", port=53),
                client.V1NetworkPolicyPort(protocol="TCP", port=53),
            ],
        )
        # Explicitly allow the pods within the network
        pod_selector = client.V1LabelSelector(
            match_expressions=[
                client.V1LabelSelectorRequirement(key="name", operator="In", values=network_pods)
            ]
        )

        peer_selector = client.V1NetworkPolicyPeer(
            pod_selector=client.V1LabelSelector(
                match_expressions=[
                    client.V1LabelSelectorRequirement(key="name", operator="In", values=network_pods)
                ]
            )
        )

        ingress_rule = client.V1NetworkPolicyIngressRule(_from=[peer_selector])
        egress_rule = client.V1NetworkPolicyEgressRule(to=[peer_selector])

        pod_selector = client.V1LabelSelector(
            match_expressions=[
                client.V1LabelSelectorRequirement(
                    key="name",
                    operator="In",
                    values=network_pods,  # your array of pod names
                )
            ]
        )
        load_kube_config()
        policy = client.V1NetworkPolicy(
            api_version="networking.k8s.io/v1",
            kind="NetworkPolicy",
            metadata=client.V1ObjectMeta(
                name="allow-all-" + netname, labels={"task": challengename.replace(" ", "-")}
            ),
            spec=client.V1NetworkPolicySpec(
                pod_selector=pod_selector,
                policy_types=["Ingress", "Egress"],
                ingress=[ingress_rule],
                egress=[dns_egress_rule, egress_rule],
            ),
        )
        return policy
    except ApiException as e:
        if e.status != 403:
            logger.error(f"API Exception when creating allow-all network policy for network {netname}: {e}")
        raise e


@retry(**retry_opts)
def create_challenge_network_policies(teamname: str, challengename: str) -> None:
    try:
        load_kube_config()
        api = client.NetworkingV1Api()
        deny_policy = create_network_policy_deny_all_task(teamname, challengename)
        api.create_namespaced_network_policy(namespace=teamname, body=deny_policy)
        networklist = dboperator.cicd_get_unique_networks(challengename)
        for i in networklist:  # understand all networks that will need to be created
            # print(i[0])
            temp_network_pods = dboperator.cicd_get_pods_in_network(challengename, i[0])
            network_pods = []
            netname = i[0]
            for j in temp_network_pods:  # understand all pods that will be present in the network
                network_pods.append(j[0])
            if i[0] == "teamnet":  # if it is teamnet, include the vpn pod in whitelist
                network_pods.append("vpn-container-pod")
                netname = netname + "-" + "".join(char for char in challengename.lower())
                netname = netname.replace(" ", "-")
            logger.debug(network_pods)
            logger.debug(i[0] + "-" + "".join(char for char in challengename.lower() if char.isalpha()))
            allow_policy = create_network_policy_allow_task(teamname, challengename, network_pods, netname)
            api.create_namespaced_network_policy(namespace=teamname, body=allow_policy)
    except ApiException as e:
        if e.status != 403:
            logger.error(f"API Exception when creating challenge network policies for {challengename}: {e}")
        raise e


@retry(**retry_opts)
def stop_challenge(teamname: str, task: str) -> str:
    try:
        task = task.replace(" ", "-")
        load_kube_config()

        core_v1 = client.CoreV1Api()
        net_v1 = client.NetworkingV1Api()

        label_selector = f"task={task}"

        # Delete Pods
        pods = core_v1.list_namespaced_pod(namespace=teamname, label_selector=label_selector)
        for pod in pods.items:
            logger.debug(f"Deleting Pod: {pod.metadata.name}")
            core_v1.delete_namespaced_pod(name=pod.metadata.name, namespace=teamname)

        # Delete Services
        services = core_v1.list_namespaced_service(namespace=teamname, label_selector=label_selector)
        for svc in services.items:
            logger.debug(f"Deleting Service: {svc.metadata.name}")
            core_v1.delete_namespaced_service(name=svc.metadata.name, namespace=teamname)

        # Delete NetworkPolicies
        policies = net_v1.list_namespaced_network_policy(namespace=teamname, label_selector=label_selector)
        for policy in policies.items:
            logger.info(f"Deleting NetworkPolicy: {policy.metadata.name}")
            net_v1.delete_namespaced_network_policy(name=policy.metadata.name, namespace=teamname)
        logger.info(f"All resources with label task={task} deleted from namespace {teamname}")
        return f"All resources with label task={task} deleted from namespace {teamname}"
    except ApiException as e:
        if e.status != 403:
            logger.error(f"API Exception when stopping challenge {task} in namespace {teamname}: {e}")
        raise e


# old functions from old controller
@retry(**retry_opts)
def create_team_namespace(teamname: str) -> None:
    try:
        load_kube_config()
        k8s_client = client.CoreV1Api()
        try:
            k8s_client.create_namespace(client.V1Namespace(metadata=client.V1ObjectMeta(name=teamname)))
            logger.debug(f"moving regcred to namespace {teamname}")
            regcred = k8s_client.read_namespaced_secret(name="regcred", namespace="default")
            regcred.metadata.namespace = teamname  # type: ignore
            regcred.metadata.resource_version = None  # type: ignore
            k8s_client.create_namespaced_secret(namespace=teamname, body=regcred)
        except Exception as e:
            logger.error(f"Error creating namespace {teamname}: {e}")
    except ApiException as e:
        if e.status != 403:
            logger.error(f"API Exception when creating namespace {teamname}: {e}")
        raise e


@retry(**retry_opts)
def create_team_vpn_configmap(teamname):
    try:
        load_kube_config()
        k8s_client = client.CoreV1Api()
        teamCertDir = certDirLocationContainer + teamname

        ovpn_config = certmanager.get_server_ovpn_config(teamCertDir)
        server_key = certmanager.get_server_key(teamCertDir)
        server_cert = certmanager.get_server_cert(teamCertDir)
        server_ca = certmanager.get_server_ca(teamCertDir)
        server_ta = certmanager.get_server_ta(teamCertDir)
        ovpn_env = certmanager.get_openvpn_env(teamCertDir)
        up_script = certmanager.get_up_script(teamCertDir)
        down_script = certmanager.get_down_script(teamCertDir)

        config_map = client.V1ConfigMap(
            api_version="v1",
            kind="ConfigMap",
            metadata=client.V1ObjectMeta(name=f"vpn-config-{teamname}"),
            data={
                "ovpn.conf": ovpn_config,
                "server.key": server_key,
                "server.crt": server_cert,
                "ca.crt": server_ca,
                "ta.key": server_ta,
                "ovpn.env": ovpn_env,
                "up.sh": up_script,
                "down.sh": down_script,
            },
        )

        k8s_client.create_namespaced_config_map(namespace=teamname, body=config_map)
        logger.debug(f"Created ConfigMap vpn-config-{teamname} in namespace {teamname}")
    except ApiException as e:
        if e.status != 403:
            logger.error(f"API Exception when creating VPN ConfigMap for team {teamname}: {e}")
        raise e


@retry(**retry_opts)
def create_team_vpn_container(teamname: str) -> None:
    try:
        create_team_vpn_configmap(teamname)
        load_kube_config()
        k8s_client = client.CoreV1Api()
        pod_manifest = {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {
                "name": "vpn-container-pod",
                "labels": {"name": "vpn-container-pod", "team": teamname},
            },
            "spec": {
                "containers": [
                    {
                        "image": "kylemanna/openvpn",
                        "name": "vpn-container",
                        "volumeMounts": [
                            {
                                "mountPath": "/etc/openvpn",
                                "name": "vpn-volume",
                                "readonly": "false",  # might need to be changed later
                            },
                            {"mountPath": "/dev/net/tun", "name": "dev-net-tun", "readonly": "false"},
                        ],
                        # NOTE: NET_ADMIN is required for OpenVPN function
                        "securityContext": {"capabilities": {"add": ["NET_ADMIN"]}},
                        "env": [{"name": "DEBUG", "value": "1"}],
                    }
                ],
                "volumes": [
                    {
                        "name": "vpn-volume",
                        "configMap": {
                            "name": f"vpn-config-{teamname}",
                            "items": [
                                {"key": "ovpn.conf", "path": "openvpn.conf"},
                                {"key": "server.key", "path": f"pki/private/{PUBLIC_DOMAINNAME}.key"},
                                {"key": "server.crt", "path": f"pki/issued/{PUBLIC_DOMAINNAME}.crt"},
                                {"key": "ca.crt", "path": "pki/ca.crt"},
                                {"key": "ta.key", "path": "pki/ta.key"},
                                {"key": "ovpn.env", "path": "ovpn_env.sh"},
                                {"key": "up.sh", "path": "up.sh"},
                                {"key": "down.sh", "path": "down.sh"},
                            ],
                        },
                    },
                    {"name": "dev-net-tun", "hostPath": {"path": "/dev/net/tun"}},
                ],
            },
        }
        k8s_client.create_namespaced_pod(body=pod_manifest, namespace=teamname)
    except ApiException as e:
        if e.status != 403:
            logger.error(f"API Exception when creating VPN container for team {teamname}: {e}")
        raise e


@retry(**retry_opts)
def expose_team_vpn_container(teamname: str, externalport: int) -> None:
    try:
        logger.debug("about to expose team vpn container")
        k8s_client = client.CoreV1Api()
        service = client.V1Service(
            metadata=client.V1ObjectMeta(
                name="vpn-container-service",  # Name of the service
                namespace=teamname,  # Namespace of the pod
            ),
            spec=client.V1ServiceSpec(
                selector={"name": "vpn-container-pod"},  # Selector to match the pod labels
                ports=[
                    client.V1ServicePort(
                        port=1194,  # Port exposed by the service (VPN port)
                        target_port=1194,  # Container's port
                        node_port=externalport,  # NodePort; k8s will allocate one if not specified
                    )
                ],
                type="NodePort",  # Service type is NodePort
            ),
        )
        api_response = k8s_client.create_namespaced_service(
            namespace=teamname,  # Namespace where the service should be created
            body=service,
        )
        logger.debug(f"Service created. Status: '{api_response.status}'")  # type: ignore
        # policy_deny= create_network_policy_deny_all(teamname)
        logger.debug("a")
        policy = create_network_policy(teamname)
        logger.debug("a")
        api = client.NetworkingV1Api()
        logger.debug("a")
        api_response = api.create_namespaced_network_policy(namespace=teamname, body=policy)
        logger.debug("a")
        logger.debug("Successfully applied network policy")
    except ApiException as e:
        if e.status != 403:
            logger.error(f"API Exception when exposing VPN container for team {teamname}: {e}")
        raise e


def register_user_ovpn(teamname: str, username: str) -> str:
    vpnDirLocation = certDirLocationContainer + teamname
    result = certmanager.generate_user(teamname, username, vpnDirLocation)
    dboperator.insert_user_vpn_config(teamname, username, result)
    return "successfully registered"


def obtain_user_ovpn_config(teamname: str, username: str) -> str:
    vpnDirLocation = certDirLocationContainer + teamname
    result = certmanager.get_user(teamname, username, vpnDirLocation)
    result = str(result).replace("\\n", "\n")
    return result


def delete_namespace(teamname: str, timeout: int = 300, interval: int = 5) -> int:
    load_kube_config()
    try:
        k8s_client = client.CoreV1Api()
        try:
            logger.info(f"Deleting namespace: {teamname}")
            k8s_client.delete_namespace(name=teamname)
        except ApiException as e:
            if e.status == 404:
                logger.info(f"Namespace {teamname} does not exist.")
                return 0
            else:
                logger.error(f"Error deleting namespace: {e}")
                return 1

        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                ns = k8s_client.read_namespace(name=teamname)

                # If namespace is stuck terminating → remove finalizers
                if ns.metadata.deletion_timestamp and ns.spec.finalizers:  # type: ignore
                    logger.debug(f"Namespace {teamname} stuck in Terminating, removing finalizers...")
                    body = {"metadata": {"finalizers": []}}
                    try:
                        k8s_client.patch_namespace(name=teamname, body=body)
                    except ApiException as e:
                        logger.error(f"Failed to patch namespace finalizers: {e}")
                        return 1

                logger.debug(f"Namespace {teamname} still exists. Waiting {interval}s...")

            except ApiException as e:
                if e.status == 404:
                    logger.info(f"Namespace {teamname} successfully deleted.")
                    return 0
                else:
                    logger.error(f"Unexpected error while checking namespace: {e}")
                    return 1

            time.sleep(interval)

        logger.error(f"Timeout: Namespace {teamname} not deleted after {timeout} seconds.")
        return 1
    except ApiException as e:
        if e.status != 403:
            logger.error(f"API Exception when deleting namespace {teamname}: {e}")
        raise e
