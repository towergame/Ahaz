import logging
import time
from os import environ

import cicd_dboperator
import docker
from kubernetes import client, config
from kubernetes.client.rest import ApiException

logger = logging.getLogger()


def create_network_policy_deny_all(namespace):
    # Load kube config (for local development)
    config.load_kube_config()
    api_instance = client.NetworkingV1Api()

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


def create_network_policy(namespace):
    # Load kube config (for local development)
    # Te vajag consul sataisīt https://www.hashicorp.com/en/resources/service-discovery-with-consul-on-kubernetes
    config.load_kube_config()
    api_instance = client.NetworkingV1Api()

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


container_registry_creds_name = "regcred"
certDirLocation = environ.get(
    "CERT_DIR_HOST", "/home/lime/Desktop/ahaz/ahaz_from_env/ahaz_cicd_env_prod/certDirectory/"
)


def start_challenge_pod(teamname, k8s_name, image, ram, cpu, storage, visible_to_user, networklist, taskname):
    config.load_kube_config()
    k8s_client = client.CoreV1Api()
    taskname = taskname.replace(" ", "-")
    storage = storage.replace("Gb", "Gi")
    ram = ram.replace("Gb", "Gi")
    env_vars = cicd_dboperator.cicd_get_env_vars(k8s_name)
    pod_manifest = {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {
            "name": k8s_name,
            "labels": {
                "team": str(teamname),
                #'networks':",".join(networklist),  # used to indentify which networks does this pod have access to
                "visible": str(
                    visible_to_user
                ),  # used to identify if this pods IP address will be shown to user.
                "task": taskname,  # used to identify what task does this pod belong to, necessary for network policies.
                "name": k8s_name,  # used for service selector
            },
        },
        "spec": {
            "containers": [
                {
                    "image": image,
                    "name": f"container",
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
            # 'imagePullSecrets': client.V1LocalObjectReference(name='regcred'), # together with a service-account, allows to access private repository docker image
        },
    }
    logger.debug(pod_manifest)
    k8s_client.create_namespaced_pod(namespace=teamname, body=pod_manifest)
    create_pod_service(teamname, taskname, k8s_name)


def start_challenge(teamname, challengename):
    logger.debug(" a")
    db_pods_data = cicd_dboperator.cicd_get_pods(challengename)
    for i in db_pods_data:
        logger.debug(i)
        k8s_name, image, ram, cpu, visible_to_user = i[1:]
        # =
        storage = "2Gb"
        netnames = cicd_dboperator.cicd_get_k8s_name_networks(k8s_name)
        networklist = []
        for i in netnames:
            networklist.append(i.replace("teamnet", teamname))
        start_challenge_pod(
            teamname, k8s_name, image, ram, cpu, storage, visible_to_user, networklist, challengename
        )
    create_challenge_network_policies(teamname, challengename)
    return 0


def get_pods_namespace(teamname, showInvisible):
    config.load_kube_config()
    k8s_client = client.CoreV1Api()
    pod_list = k8s_client.list_namespaced_pod(teamname)
    pod_info = []
    pod_info_json = "["
    first = True
    try:
        for pod in pod_list.items:
            if pod.metadata.name == "vpn-container-pod":
                if pod.metadata.deletion_timestamp is not None and pod.status.phase in ("Pending", "Running"):
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
                + cicd_dboperator.cicd_get_challenge_from_k8s_name(pod.metadata.labels["name"])
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
    except:  # there is an issue that if I just start up a pod, and immediately request pod statuses, it doesn't have an IP assigned yet, and that requires re requesting all pods to be loaded.
        time.sleep(3)
        pod_list = k8s_client.list_namespaced_pod(teamname)
        for pod in pod_list.items:
            if pod.metadata.name == "vpn-container-pod":
                if pod.metadata.deletion_timestamp is not None and pod.status.phase in ("Pending", "Running"):
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
            current_pod_info_json = (
                '{"name":"'
                + pod.metadata.name
                + '","status":"'
                + state
                + '","ip":"'
                + pod.status.pod_ip
                + '","visibleIP":'
                + pod.metadata.labels["visible"]
                + ',"task":"'
                + cicd_dboperator.cicd_get_challenge_from_k8s_name(pod.metadata.labels["name"])
                + ',"name":"'
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


def create_pod_service(teamname, taskname, k8s_name):
    config.load_kube_config()
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
    logger.debug("Service created. Status='%s'" % str(api_response.status))


def create_network_policy_deny_all_task(teamname, challengename):
    sanitized_challengename = challengename.replace(" ", "-").lower()
    taskname = challengename.replace(" ", "-")
    config.load_kube_config()
    api_instance = client.NetworkingV1Api()

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


def create_network_policy_allow_task(teamname, challengename, network_pods, netname):
    sanitized_challengename = challengename.replace(" ", "-").lower()
    # label_selector='label in ('
    # for i in network_pods:
    #    label_selector+=i
    #    label_selector+=', '
    # label_selector = label_selector[:-2] + ")"

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
        match_expressions=[client.V1LabelSelectorRequirement(key="name", operator="In", values=network_pods)]
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
    config.load_kube_config()
    api_instance = client.NetworkingV1Api()
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


def create_challenge_network_policies(teamname, challengename):
    config.load_kube_config()
    api = client.NetworkingV1Api()
    deny_policy = create_network_policy_deny_all_task(teamname, challengename)
    api_response = api.create_namespaced_network_policy(namespace=teamname, body=deny_policy)
    networklist = cicd_dboperator.cicd_get_unique_networks(challengename)
    for i in networklist:  # understand all networks that will need to be created
        # print(i[0])
        temp_network_pods = cicd_dboperator.cicd_get_pods_in_network(challengename, i[0])
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
        api_response = api.create_namespaced_network_policy(namespace=teamname, body=allow_policy)


def stop_challenge(teamname, task):
    task = task.replace(" ", "-")
    config.load_kube_config()

    core_v1 = client.CoreV1Api()
    net_v1 = client.NetworkingV1Api()

    label_selector = f"task={task}"

    # Delete Pods
    try:
        pods = core_v1.list_namespaced_pod(namespace=teamname, label_selector=label_selector)
        for pod in pods.items:
            logger.debug(f"Deleting Pod: {pod.metadata.name}")
            core_v1.delete_namespaced_pod(name=pod.metadata.name, namespace=teamname)
    except ApiException as e:
        logger.error(f"Error deleting pods: {e}")
        return f"Error deleting pods: {e}"

    # Delete Services
    try:
        services = core_v1.list_namespaced_service(namespace=teamname, label_selector=label_selector)
        for svc in services.items:
            logger.debug(f"Deleting Service: {svc.metadata.name}")
            core_v1.delete_namespaced_service(name=svc.metadata.name, namespace=teamname)
    except ApiException as e:
        logger.error(f"Error deleting services: {e}")
        return f"Error deleting services: {e}"

    # Delete NetworkPolicies
    try:
        policies = net_v1.list_namespaced_network_policy(namespace=teamname, label_selector=label_selector)
        for policy in policies.items:
            logger.info(f"Deleting NetworkPolicy: {policy.metadata.name}")
            net_v1.delete_namespaced_network_policy(name=policy.metadata.name, namespace=teamname)
    except ApiException as e:
        logger.error(f"Error deleting network policies: {e}")
        return f"Error deleting network policies: {e}"
    logger.info(f"All resources with label task={task} deleted from namespace {teamname}")
    return f"All resources with label task={task} deleted from namespace {teamname}"


# old functions from old controller
def create_team_namespace(teamname):
    config.load_kube_config()
    k8s_client = client.CoreV1Api()
    try:
        k8s_client.create_namespace(client.V1Namespace(metadata=client.V1ObjectMeta(name=teamname)))
        logger.debug(f"moving regcred to namespace {teamname}")
        regcred = k8s_client.read_namespaced_secret(name="regcred", namespace="default")
        regcred.metadata.namespace = teamname
        regcred.metadata.resource_version = None  # Clear resource version to allow creation
        k8s_client.create_namespaced_secret(namespace=teamname, body=regcred)
    except Exception as e:
        logger.error(f"Error creating namespace {teamname}: {e}")


def create_team_vpn_container(teamname):
    config.load_kube_config()
    k8s_client = client.CoreV1Api()
    teamCertDir = certDirLocation + teamname
    pod_manifest = {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {"name": "vpn-container-pod", "labels": {"name": "vpn-container-pod", "team": teamname}},
        "spec": {
            "containers": [
                {
                    "image": "kylemanna/openvpn",
                    "name": f"vpn-container",
                    "volumeMounts": [
                        {
                            "mountPath": "/etc/openvpn",
                            "name": "vpn-volume",
                            "readonly": "false",  # might need to be changed later
                        },
                        {"mountPath": "/dev/net/tun", "name": "dev-net-tun", "readonly": "false"},
                    ],
                    "securityContext": {"capabilities": {"add": ["NET_ADMIN"]}, "privileged": True},
                    "env": [{"name": "DEBUG", "value": "1"}],
                }
            ],
            "volumes": [
                {"name": "vpn-volume", "hostPath": {"path": teamCertDir, "type": "Directory"}},
                {"name": "dev-net-tun", "hostPath": {"path": "/dev/net/tun"}},
            ],
        },
    }
    k8s_client.create_namespaced_pod(body=pod_manifest, namespace=teamname)


def expose_team_vpn_container(teamname, externalport):
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
                    node_port=externalport,  # NodePort (external port); Kubernetes will allocate one if not specified
                )
            ],
            type="NodePort",  # Service type is NodePort
        ),
    )
    try:
        api_response = k8s_client.create_namespaced_service(
            namespace=teamname,  # Namespace where the service should be created
            body=service,
        )
        logger.debug("Service created. Status: '%s'" % str(api_response.status))
        try:
            # policy_deny= create_network_policy_deny_all(teamname)
            logger.debug("a")
            policy = create_network_policy(teamname)
            logger.debug("a")
            api = client.NetworkingV1Api()
            logger.debug("a")
            api_response = api.create_namespaced_network_policy(namespace=teamname, body=policy)
            logger.debug("a")
            logger.debug("Successfully applied network policy")
        except client.rest.ApiException as e:
            logger.error("Exception when applying network policy: %s\n" % e)
    except client.rest.ApiException as e:
        logger.error("Exception when creating service: %s\n" % e)


def docker_register_user(teamname, username):
    client = docker.from_env()
    vpnDirLocation = certDirLocation + teamname
    client.containers.run(
        "kylemanna/openvpn",
        volumes={vpnDirLocation: {"bind": "/etc/openvpn", "mode": "rw"}},
        command=["easyrsa", "build-client-full", username, "nopass"],
    )
    result = client.containers.run(
        "kylemanna/openvpn",
        volumes={vpnDirLocation: {"bind": "/etc/openvpn", "mode": "rw"}},
        command=["ovpn_getclient", username],
    )
    cicd_dboperator.insert_user_vpn_config(teamname, username, result)
    return "successfully registered"


def docker_obtain_user_vpn_config(teamname, username):
    client = docker.from_env()
    vpnDirLocation = certDirLocation + teamname
    result = client.containers.run(
        "kylemanna/openvpn",
        volumes={vpnDirLocation: {"bind": "/etc/openvpn", "mode": "rw"}},
        command=["ovpn_getclient", username],
    )
    result = str(result).replace("\\n", "\n")
    result = result[2:]
    result = result[: len(result) - 2]
    return result


def delete_namespace(teamname, timeout=300, interval=5):
    config.load_kube_config()
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
            if ns.metadata.deletion_timestamp and ns.spec.finalizers:
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
