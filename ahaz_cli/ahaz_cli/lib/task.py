import logging

import yaml

from ahaz_common import Task

log = logging.getLogger()


def deserialise_task(task_config: str) -> Task:
    try:
        config_dict = yaml.safe_load(task_config)
    except yaml.YAMLError as e:
        log.error(f"Error parsing YAML: {e}")
        raise ValueError("Invalid task configuration") from e

    try:
        return Task(**config_dict)
    except TypeError as e:
        log.error(f"Error constructing Task object: {e}")
        raise ValueError("Invalid task configuration structure") from e


def serialise_task(task: Task) -> str:
    config_dict = {
        "name": task.name,
        "description": task.description,
        "score": task.score,
        "scoring_type": task.scoring_type,
        "pods": [
            {
                "k8s_name": pod.k8s_name,
                "image": {
                    "image_name": pod.image.image_name,
                    "build_context": pod.image.build_context,
                    "build_args": [
                        {"name": arg.name, "value": arg.value} for arg in pod.image.build_args or []
                    ],
                },
                "limits_ram": pod.limits_ram,
                "limits_cpu": pod.limits_cpu,
                "visible_to_user": pod.visible_to_user,
                "testing": {"exposed_ports": pod.testing.exposed_ports if pod.testing is not None else []},
            }
            for pod in task.pods
        ],
        "networks": [{"netname": net.netname, "devices": net.devices} for net in task.networks],
        "env_vars": [
            {
                "k8s_name": env.k8s_name,
                "env_var_name": env.env_var_name,
                "env_var_value": env.env_var_value,
            }
            for env in task.env_vars or []
        ],
    }

    return yaml.dump(config_dict)


def normalise_task_name(name: str) -> str:
    # Make the task lowercase, replace spaces with hyphens, and remove special characters
    return name.lower().replace(" ", "-").replace(r"([^a-z0-9-])", "")
