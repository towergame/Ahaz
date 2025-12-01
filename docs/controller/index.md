# Ahaz Controller

The Ahaz controller acts as the main service that manages the starting, monitoring and destruction of task containers. 

## VPN Management

Establishing a team VPN consists of the following steps:
- Generating the PKI for the team (generating the certificate authority).
- Create a team namespace in Kubernetes
- Create an OpenVPN pod in the team namespace configured to use the team's PKI.
- Generating the certificate for individual team members (certificate and private key).
- Using the generated user certificate to generate an OpenVPN config to provide to the user.

## REST API

The Ahaz controller is controlled through a REST API, which allows for starting and stopping tasks, creating teams and retrieving VPN configurations.

The REST API endpoints are as follows:
- `GET /ping` - Health check endpoint.
- `POST /start_challenge` - Start a challenge/task for a team, accepts a `ChallengeRequest` as the request body.
- `POST /stop_challenge` - Stop a challenge/task for a team, accepts a `ChallengeRequest` as the request body.
- `GET /get_challenges` - Retrieves a list of currently available challenges/tasks.
- `POST /add_user` - Generates a user's VPN configuration in a team, accepts a `UserRequest` as the request body.
- `GET /get_user` - Retrieves the VPN configuration for a user, accepts `UserRequest` as the request body.
- `POST /gen_team` - Generates a new team, accepts a `RegisterTeamRequest` as the request body.
- `POST /autogenerate` - Generate a user's VPN configuration in a team, generating a team if necessary, accepts `UserRequest` as the request body.
- `POST /regenerate` - Regenerates the user's VPN configuration in a team, accepts `UserRequest` as the request body.
- `POST /del_team` - Deletes a team and all associated resources, accepts a `TeamRequest` as the request body.
- `GET /events` - SSE endpoint providing real-time updates on task and team status.

### Request types
- `ChallengeRequest`
  - `team_id: str` - The ID of the team.
  - `challenge_id: str` - The ID of the challenge/task.
- `UserRequest`
  - `team_id: str` - The ID of the team.
  - `user_id: str` - The ID of the user.
- `RegisterTeamRequest`
    - `team_id: str` - The ID of the team.
    - `domain_name: str` - The domain name for the team's VPN.
    - `port: int` - The port for the team's VPN.
    - `protocol: str` - The protocol for the team's VPN (e.g., 'udp' or 'tcp').
- `TeamRequest`
  - `team_id: str` - The ID of the team. 