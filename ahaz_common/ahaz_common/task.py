from typing import Optional

from pydantic import BaseModel


class BuildArg(BaseModel):
    name: str
    value: str

    def __str__(self):
        return f"BuildArgs(name={self.name}, value={self.value})"


class Image(BaseModel):
    image_name: str
    build_context: str
    build_args: Optional[list[BuildArg]] = None

    def __str__(self):
        return (
            f"Image(image_name={self.image_name}, build_context={self.build_context}, "
            f"build_args={self.build_args})"
        )


class TestEnv(BaseModel):
    exposed_ports: list[str]  # Mapping of container port to host port

    def __str__(self):
        return f"TestEnv(exposed_ports={self.exposed_ports})"


class Pod(BaseModel):
    k8s_name: str
    # TODO: Support multi-image pods
    image: Image
    limits_ram: str
    limits_cpu: int
    visible_to_user: bool
    testing: Optional[TestEnv] = None

    def __str__(self):
        return (
            f"Pod(k8s_name={self.k8s_name}, image={self.image}, limits_ram={self.limits_ram}, "
            f"limits_cpu={self.limits_cpu}, visible_to_user={self.visible_to_user}, testing={self.testing})"
        )


class Network(BaseModel):
    netname: str
    devices: list[str]

    def __str__(self):
        return f"Networks(netname={self.netname}, devices={self.devices})"


class EnvVar(BaseModel):
    k8s_name: str
    env_var_name: str
    env_var_value: str

    def __str__(self):
        return (
            f"EnvVars(k8s_name={self.k8s_name}, env_var_name={self.env_var_name}, "
            f"env_var_value={self.env_var_value})"
        )


class Task(BaseModel):
    name: str
    version: str
    description: str
    score: int
    scoring_type: str
    pods: list[Pod]
    networks: list[Network]
    env_vars: Optional[list[EnvVar]] = None

    def __str__(self):
        return (
            f"Task(name={self.name}, description={self.description}, score={self.score}, "
            f"scoring_type={self.scoring_type}, pods={self.pods}, networks={self.networks}, "
            f"env_vars={self.env_vars})"
        )
