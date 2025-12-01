# VPN setup

The Ahaz controller provisions a team VPN for each team that is created. Each team VPN is implemented as an OpenVPN server running in a dedicated Kubernetes namespace for the team.

When a team is created, the Ahaz controller performs the following steps to set up the VPN:
1. Generate a Public Key Infrastructure (PKI) for the team, including a Certificate Authority (CA).
2. Create a Kubernetes namespace for the team.
3. Deploy an OpenVPN server pod in the team's namespace, configured to use the generated PKI.
4. Expose the OpenVPN server via a Service, allowing team members to connect to it.

When a user is added to a team, the Ahaz controller generates a client certificate for the user and creates an OpenVPN configuration file that includes the user's certificate and the necessary connection settings. This configuration file is then provided to the user for connecting to the team VPN.

## Cryptographic setup
The PKI for the VPN is generated using the `easy-rsa` toolkit. The Ahaz controller manages the lifecycle of the PKI, including generating the CA, server certificates, and client certificates.

The certificates use the elliptic curve cryptosystem, utlising the `secp384r1` curve for key generation and the `SHA-512` hashing algorithm for generating signatures. This ensures that the VPN connections are secured with strong cryptographic primitives, while also maintaining performance able to generate a large number of certificates per second.

OpenVPN is configured to utilise the ECDH key exchange mechanism, further improving performance in certificate generation as it allows for DH-equivalent security without the need for expensive DH parameter generation.

The cryptographic generation is handled inside the `certmanager.py` module of the Ahaz controller, utilising the `easy-rsa` toolkit for certificate generation and management.