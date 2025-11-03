# Ahaz Kubernetes Deployment
This chart deploys the Ahaz Kubernetes Controller along with its necessary RBAC configurations and namespace management capabilities, while ensuring the principle of least privilege.

## Requirements
This chart assumes you have Kyverno installed in your cluster for policy management.

## Notable Features
Alongside deploying the Ahaz kubernetes controller into the specified namespace, this also sets up Kyverno policies to ensure that the service account used by the controller may only interact with the namespaces it has created. Similarly, it contains some basic sanity checks to prevent the controller from creating pods with elevated privileges.
Current security policies enforced:
- Automatically label namespaces created by Ahaz
- Prevent privileged containers
- Use Kyverno to create the roles and role bindings for object creation in the namespaces created by Ahaz

## TODO
- [ ] Limit the capabilities of pods deployed by Ahaz
- [ ] Add default resource limits/requests for pods created by Ahaz
- [ ] Create a default network policy for namespaces created by Ahaz
- [ ] Add option to insert secrets that may be copied into created namespaces