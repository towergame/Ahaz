from kubernetes import client, config
from kubernetes.stream import stream
from os import environ
import docker
import dboperator
import time
#certDirLocation="/home/lime/Desktop/ahaz/docker_experimenting/testCertDirs/"
certDirLocation=environ.get('CERT_DIR_HOST')
#for minikube
#certDirLocation="/home/docker/testCertDirs/"
def start_container(teamname,containername):
    config.load_kube_config()
    k8s_client = client.CoreV1Api()
    pod_manifest = {
            'apiVersion': 'v1',
            'kind': 'Pod',
            'metadata': {
                'name': containername
            },
            'spec': {
                'containers': [{
                    'image': containername,
                    'name': f'container'
                }],
                # 'imagePullSecrets': client.V1LocalObjectReference(name='regcred'), # together with a service-account, allows to access private repository docker image
            }
        }
    #body = client.V1Pod(spec)
    k8s_client.create_namespaced_pod(namespace=teamname,body=pod_manifest)

def start_challenge(teamname,challengename):
    challengeParams=dboperator.get_image_from_db(challengename)
    print(challengeParams)
    containername=challengeParams[0][0]+"/"+challengeParams[0][1]+":"+challengeParams[0][2]
    print(containername)
    config.load_kube_config()
    k8s_client = client.CoreV1Api()
    sanitizedChallengename=challengename.replace("_",'-')
    pod_manifest = {
            'apiVersion': 'v1',
            'kind': 'Pod',
            'metadata': {
                'name': sanitizedChallengename,
                'labels':{
                    'team':teamname      
                }
            },
            'spec': {
                'containers': [{
                    'image': containername,
                    'name': sanitizedChallengename
                }],
                'imagePullSecrets': [{
                    'name':'regcred'
                }] # together with a service-account, allows to access private repository docker image
            }
        }
    #body = client.V1Pod(spec)
    #try:
    k8s_client.create_namespaced_pod(namespace=teamname,body=pod_manifest)
    try:
        policy = create_network_policy(teamname)
        api = client.NetworkingV1Api()
        api_response = api.create_namespaced_network_policy(namespace=teamname, body=policy)
        print("Successfully applied network policy")
    except client.rest.ApiException as e:
        print("Exception when applying network policy: %s\n" % e)
    return "succeeded in creating a namespaced pod"
    #except:
    #    return str(Exception)
    #    return str(pod_manifest)
    #    return "failed to create namespaced pod"
def delete_challenge(namespace,challengename):
    config.load_kube_config()
    k8s_client = client.CoreV1Api()
    sanitizedChallengename=challengename.replace("_",'-')
    try:
        k8s_client.delete_namespaced_pod(sanitizedChallengename,namespace=namespace)
        return "successfuly stopped challenge "+challengename
    except:
        return "failed in stopping challenge "+challengename 

def get_container_parameters(teamname):
    config.load_kube_config()
    k8s_client = client.CoreV1Api()
    pod_list = k8s_client.list_namespaced_pod(teamname)
    pod_info=[]
    pod_info_json="["
    first=True
    try:
        for pod in pod_list.items:
            print("%s\t%s\t%s" % (pod.metadata.name,
                                pod.status.phase,
                                pod.status.pod_ip))
            #because python k8s api does not show status terminating :/
            if pod.metadata.deletion_timestamp is not None and pod.status.phase in ('Pending', 'Running'):
                state = 'Terminating'
            else:
                state = str(pod.status.phase) 
            pod_info.append([pod.metadata.name,state,pod.status.pod_ip])
            current_pod_info_json='{"name":"'+pod.metadata.name+'","status":"'+state+'","ip":"'+pod.status.pod_ip+'"}'
            if(first):
                pod_info_json+=current_pod_info_json
                first=False
            else:
                pod_info_json+=","+current_pod_info_json
        pod_info_json+="]"
        return pod_info_json
    except: #there is an issue that if I just start up a pod, and immediately request pod statuses, it doesn't have an IP assigned yet, and that requires re requesting all pods to be loaded.
        time.sleep(3)
        pod_list = k8s_client.list_namespaced_pod(teamname)
        for pod in pod_list.items:
            print("%s\t%s\t%s" % (pod.metadata.name,
                                pod.status.phase,
                                pod.status.pod_ip))
            #because python k8s api does not show status terminating :/
            if pod.metadata.deletion_timestamp is not None and pod.status.phase in ('Pending', 'Running'):
                state = 'Terminating'
            else:
                state = str(pod.status.phase) 
            pod_info.append([pod.metadata.name,state,pod.status.pod_ip])
            current_pod_info_json='{"name":"'+pod.metadata.name+'","status":"'+state+'","ip":"'+pod.status.pod_ip+'"}'
            if(first):
                pod_info_json+=current_pod_info_json
                first=False
            else:
                pod_info_json+=","+current_pod_info_json
        pod_info_json+="]"
        return pod_info_json        
def create_team_namespace(teamname):
    config.load_kube_config()
    k8s_client = client.CoreV1Api()
    try:
        k8s_client.create_namespace(client.V1Namespace(metadata=client.V1ObjectMeta(name=teamname)))
    except Exception as e:
        print(e)
        print("namespace already exists")

def create_team_vpn_container(teamname):
    config.load_kube_config()
    k8s_client = client.CoreV1Api()
    teamCertDir=certDirLocation+teamname
    pod_manifest = {
            'apiVersion': 'v1',
            'kind': 'Pod',
            'metadata': {
                'name': 'vpn-container-pod',
                'labels':{
                    'name':'vpn-container-pod',
                    'team':teamname
                }
            },
            'spec': {
                'containers': [{
                    'image': 'kylemanna/openvpn',
                    'name': f'vpn-container',
                    'volumeMounts':[{
                        'mountPath':'/etc/openvpn',
                        'name':'vpn-volume',
                        'readonly':'false' #might need to be changed later
                    },{
                        'mountPath':'/dev/net/tun',
                        'name':'dev-net-tun',
                        'readonly':'false'
                    }],
                    'securityContext':{
                        'capabilities':{
                            'add':["NET_ADMIN"]
                        },
                        'privileged':True
                    },
                    'env':[{
                        'name':'DEBUG',
                        'value':'1'
                    }]
                }],
                'volumes':[{
                  'name':'vpn-volume',
                  'hostPath':{
                      'path':teamCertDir,
                      'type':'Directory'
                  }
                },{
                    'name':'dev-net-tun',
                    'hostPath':{
                        'path':'/dev/net/tun'
                    }
                }]
            }
        }
    k8s_client.create_namespaced_pod(body=pod_manifest,namespace=teamname)

def expose_team_vpn_container(teamname,externalport):
    k8s_client = client.CoreV1Api()
    service = client.V1Service(
        metadata=client.V1ObjectMeta(
            name="vpn-container-service",  # Name of the service
            namespace=teamname           # Namespace of the pod
        ),
        spec=client.V1ServiceSpec(
            selector={"name": "vpn-container-pod"},  # Selector to match the pod labels
            ports=[client.V1ServicePort(
                port=1194,                  # Port exposed by the service (VPN port)
                target_port=1194,           # Container's port
                node_port=externalport             # NodePort (external port); Kubernetes will allocate one if not specified
            )],
            type="NodePort"                 # Service type is NodePort
        )
    )
    try:
        api_response = k8s_client.create_namespaced_service(
            namespace=teamname,  # Namespace where the service should be created
            body=service
        )
        print("Service created. Status: '%s'" % str(api_response.status))
        try:
            #policy_deny= create_network_policy_deny_all(teamname)
            policy = create_network_policy(teamname)
            api = client.NetworkingV1Api()
            #api_response_deny_all = api.create_namespaced_network_policy(namespace=teamname, body=policy_deny)
            api_response = api.create_namespaced_network_policy(namespace=teamname, body=policy)
            print("Successfully applied network policy")
        except client.rest.ApiException as e:
            print("Exception when applying network policy: %s\n" % e)
    except client.rest.ApiException as e:
        print("Exception when creating service: %s\n" % e)
    
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
            egress=[]
        )
    )
    return policy
def create_network_policy(namespace):
# Load kube config (for local development)
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
                        client.V1NetworkPolicyPort(protocol="UDP", port=1194)
                    ]
                )
            ],
            egress=[
                # Explicitly deny all egress traffic by default
                #client.V1NetworkPolicyEgressRule(to=[]),
                # Allow communication only within the same namespace
                #client.V1NetworkPolicyEgressRule(
                    #to=[client.V1NetworkPolicyPeer(pod_selector=client.V1LabelSelector(match_labels={"team":namespace}))]
                    #to=[client.V1NetworkPolicyPeer(pod_selector=client.V1LabelSelector(match_labels={}))]
                #)
            ]
        )
    )
    return policy

def docker_register_user(teamname,username):
    client = docker.from_env()
    vpnDirLocation=certDirLocation+teamname
    client.containers.run("kylemanna/openvpn", volumes={vpnDirLocation:{"bind":"/etc/openvpn","mode":"rw"}},command=["easyrsa","build-client-full",username,"nopass"])
    result=client.containers.run("kylemanna/openvpn", volumes={vpnDirLocation:{"bind":"/etc/openvpn","mode":"rw"}},command=["ovpn_getclient",username])
    dboperator.insert_user_vpn_config(teamname,username,result)
    return "successfully registered"

def docker_obtain_user_vpn_config(teamname,username):
    client = docker.from_env()
    vpnDirLocation=certDirLocation+teamname
    result=client.containers.run("kylemanna/openvpn", volumes={vpnDirLocation:{"bind":"/etc/openvpn","mode":"rw"}},command=["ovpn_getclient",username])
    result=str(result).replace('\\n','\n')
    result=result[2:]
    result=result[:len(result)-2]
    return result


if __name__ == "__main__":
    # Configs can be set in Configuration class directly or using helper utility
    config.load_kube_config()

    v1 = client.CoreV1Api()
    core_v1 = client.api.core_v1_api.CoreV1Api()
    #teamname="testteam8"
    #username="testuser2"
    #create_team_namespace(teamname)
    #create_team_vpn_container(teamname)
    #expose_team_vpn_container(teamname,30005)
    #client = docker.from_env()
    #docker_register_user(teamname,username)
    #docker_obtain_user_vpn_config(teamname,username)