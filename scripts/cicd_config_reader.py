from os import environ
import cicd_dboperator
import yaml

def read_yaml_file(filename):
    with open(filename, 'r') as file:
        config = yaml.safe_load(file)
    variable = cicd_dboperator.cicd_insert_challenge(config["name"],config["ctfd_desc"],config["ctfd_score"],config["ctfd_scoring_type"])
    print(variable)
    for i in config["pods"]:
        cicd_dboperator.cicd_insert_pod(config["name"],i["k8s_name"],i["image"],i["limits_ram"],i["limits_cpu"],i["visible_to_user"])
    for i in config["networking"]:
        for j in i["devices"]:
            cicd_dboperator.cicd_insert_net_rules(config["name"],i["netname"],j)
    if "env_vars" in config: #env vars are optional
        for i in config["env_vars"]:
            cicd_dboperator.cicd_insert_env_vars(config["name"],i["k8s_name"],i["env_var_name"],i["env_var_value"])
def check_yaml_file_format(filename):
    try:
        with open(filename, 'r') as file:
            config = yaml.safe_load(file)
        print("challenge parameters")
        print(config["name"],config["ctfd_desc"],config["ctfd_score"],config["ctfd_scoring_type"])
        print("pods")
        for i in config["pods"]:
            print(config["name"],i["k8s_name"],i["image"],i["limits_ram"],i["limits_cpu"],i["visible_to_user"])
        print("networking")
        for i in config["networking"]:
            for j in i["devices"]:
                print(config["name"],i["netname"],j)
        print("env vars if any")
        if "env_vars" in config: #env vars are optional
            for i in config["env_vars"]:
                print(config["name"],i["k8s_name"],i["env_var_name"],i["env_var_value"])    
        return True
    except:
        return False
#check_yaml_file_format("/home/lime/Desktop/ahaz/yamlPiemers.yaml")
#read_yaml_file("/home/lime/Desktop/ahaz/yamlPiemers.yaml")
    