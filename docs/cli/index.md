# Ahaz CLI

The Ahaz CLI is a command-line interface for interacting with the Ahaz controller. It allows maintainers and task makers to test tasks and push them to the controller.

NB! The Ahaz CLI is currently still WIP and lacks many features.

## Installation

The Ahaz CLI can be installed via pip:

```bash
pip install --extra-index-url https://git.0x10.lv/api/packages/towergame/pypi/simple ahaz-cli
```

If you wish to update an existing installation, you may run:

```bash
pip install -U --extra-index-url https://git.0x10.lv/api/packages/towergame/pypi/simple ahaz-cli
```

The CLI may also be installed from source by cloning the repository and running:

```bash
pip install -e ahaz_cli/
```

## Usage

The Ahaz CLI provides several commands for interacting with the Ahaz controller. The basic usage is as follows:

```bash
ahaz <command> [options]
```

Currently available commands are:
- `epic` - a "hello world"-esque command to verify that the CLI is installed correctly.
- `test` - test a challenge/task locally using Docker.
- `init` - initialize a new challenge/task directory with the necessary files.

### Testing a Challenge

To test a challenge locally, navigate to the challenge directory and run:

```bash
ahaz test
```

This will validate the `task.yaml` file and attempt to build the Docker images.
If you wish to also run the challenge, you may add the flag `-u`:
```bash
ahaz test -u
```

This will start the challenge containers and connect them in the same networking setup as they would be in the Ahaz controller.
Press `Ctrl+C` to stop the challenge and clean up the containers.

If you wish to force a rebuild of the Docker images, you may add the `-b` flag:
```bash
ahaz test -b
```

### Initializing a Challenge
To initialize a new challenge directory, run:

```bash
ahaz init <challenge-name>
```

This will create a new directory with the necessary files for a challenge, including a sample `task.yaml` file and a `Dockerfile`.

## Task YAML Specification
The `task.yaml` file is used to define the specifications of a challenge/task. It includes information such as the challenge name, description, Docker images, and networking setup.

Example `task.yaml` file:
```yaml
name: "My Very Cool Task" # Name of the task; shown to the user
version: "1.0.0" # Version of the task; used for image tagging, increment when making changes to already-pushed tasks
description: "Very cool description UwU" # Description of the task; shown to the user
score: 150 # Maximum score for the task
scoring_type: "dynamic" # Scoring type; can be "static" or "dynamic"

# Definition of the pods that will be created for the task
pods:
- name: "hello-world" # Name of the pod; used for referencing in networks and env_vars
  visible_to_user: true # Whether the user can see this pod
  # Definition of the container image for the pod
  image:
    image_name: "hello-world" # Name of the image; used for pulling/building the image
    build_context: "./hello-world" # Context path for building the image, needs to at least contain a Dockerfile
  limits_ram: "128Mi" # RAM limit for the pod
  limits_cpu: 1 # CPU limit for the pod
  # Testing configuration for the pod; used for `ahaz test` command
  testing:
    # Defines ports that will be exposed on the host machine via Docker
    exposed_ports:
    - 1337:80

# Network definitions for the task
networks:
# Teamnet will always contain the VPN pod - use for user-accessible services
- name: "teamnet" # Name of the network
  devices: [ "hello-world" ] # Pods connected to this network
# Other networks are inaccessible to the players
- name: "super-secret-internal-network"
  devices: [ "hello-world" ]

# Environment variables to be set in the pods
env_vars:
- pod_name: "hello-world" # Pod to which the environment variable will be set
  name: "COOL_ENV_VAR" # Name of the environment variable
  value: "hello-world" # Value of the environment variable
```
