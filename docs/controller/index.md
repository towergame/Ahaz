# Ahaz Controller

The Ahaz controller acts as the main service that manages the starting, monitoring and destruction of task containers. 

## VPN Management

Establishing a team VPN consists of the following steps:
- Generating the PKI for the team (generating the certificate authority).
- Create a team namespace in Kubernetes
- Create an OpenVPN pod in the team namespace configured to use the team's PKI.
- Generating the certificate for individual team members (certificate and private key).
- Using the generated user certificate to generate an OpenVPN config to provide to the user.