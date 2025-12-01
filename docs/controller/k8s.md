# Kubernetes Interaction
 
The Ahaz controller interacts with a Kubernetes cluster to manage task containers and team VPNs. It uses the Kubernetes API to create namespaces, deploy pods, and manage resources.

## Team Namespaces

For each team, the Ahaz controller creates a dedicated namespace in the Kubernetes cluster. This namespace isolates the team's resources, including their VPN server and task pods. Network policies are applied to prevent the pods in a team's namespace from communicating with all pods in the cluster.

## Pod Deployment

When a team starts a task, the Ahaz controller deploys the task pods in the team's namespace. The pods are configured according to the specifications of the task in the database, applying resource limits and environment variables as defined. During the task deployment, network policies are applied to allow communication between individual pods as defined in the task specification. Only pods which are part of the `teamnet` network may be accessed via the team VPN.

## Pod Status

Pods are tracked using labels, where the `task` label indicates which task a given pod is part of, and the `team` label indicates which team the pod belongs to. The Ahaz controller periodically queries the Kubernetes API to retrieve the status of all pods in team namespaces, sending updates to connected clients using the API.

## Taints and Labels

To ensure that VPN and task pods are scheduled on appropriate nodes, the Ahaz controller relies on Kubernetes taints and labels. Nodes can be tainted to restrict scheduling of certain pod types, and labeled to indicate their role in the Ahaz deployment (e.g., `vpn`, `task`, `shared`, or `unmanaged`).

The following taints may be applied to nodes:
- `ahaz-controller/node-role` - role of the node in Ahaz; may be either `PreferNoSchedule`, `NoSchedule` or `NoExecute` depending on the threat model
  - `vpn` - This node is provisioned to host VPN pods.
  - `task` - This node is provisioned to host task pods.
  - `shared` - This node is shared between both task and VPN pods. 

The following labels may be applied to nodes:
- `ahaz-controller/node-role` - role of the node in Ahaz
  - `vpn` - This node may host VPN pods.
  - `task` - This node may host task pods.
  - `shared` - This node may host both task and VPN pods.
  - `unmanaged` - This node is not to be used by Ahaz.