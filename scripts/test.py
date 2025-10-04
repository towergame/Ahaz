import generatecert
import controller
from flask import Flask, jsonify, request
import json
import dboperator
import cicd_dboperator
import cicd_controller
import cicd_config_reader
import cicd_cerserver
from threading import Thread
from os import path, environ 
import time
from kubernetes import client, config
#print(controller.start_container("testteam","httpd"))
#dboperator.insert_image_into_db("gitea.eztfsp.lv","auseklitis/jwt_none","latest","jwt_none")
#print(dboperator.get_image_from_db("jwt_none"))
#controller.start_challenge("testteam","jwt_none")
#controller.start_challenge("testteam","jwt_none")
#time.sleep(3)
#controller.delete_challenge("testteam","jwt_none")
#time.sleep(5)
#controller.get_container_parameters("testteam")
#dboperator.insert_image_into_db("gitea.eztfsp.lv","auseklitis/jwt_self_signed","latest","jwt_self_signed")
#print(dboperator.get_images_from_db())
#teamname="test12345678"
#dboperator.create_db()
#controller
#controller.create_team_namespace(teamname)
#controller.create_team_vpn_container(teamname)
#controller.expose_team_vpn_container(teamname,30904)

#podlist=cicd_dboperator.cicd_get_pods("JWT none")
#podlist_solo=cicd_dboperator.cicd_get_pods("test")
#print(podlist)

#cicd_dboperator.cicd_get_unique_networks("JWT some")
#cicd_dboperator.cicd_get_pods_in_network("JWT some","teamnet")
#cicd_dboperator.cicd_get_pods_in_network("JWT some","teamnet-some-connection")

#cicd_controller.create_challenge_network_policies("testteam","JWT some")

#cicd_controller.start_challenge("testteam","JWT test")
#cicd_controller.stop_challenge("testteam","JWT some")
#cicd_controller.cicd_config_reader()
#controller.get_container_parameters("3")
#cicd_config_reader.read_yaml_file("/home/lime/Desktop/ahaz/jwt_some.yaml")
#cicd_controller.create_network_policy_allow_teamnet_task("testteam","JWT some",["jwt-some-fe","jwt-some-be"])
#cicd_controller.create_challenge_network_policies("testteam","JWT some")
#podresult = cicd_controller.get_pods_namespace("testteam",0)
#print(podresult)
#podresult = cicd_controller.get_pods_namespace("testteam",1)
#print(podresult)
#cicd_controller.stop_challenge("zxcabcdefgh","JWT test")
#cicd_controller.start_challenge("zxcabcdefgh","JWT test")
#cicd_cerserver.get_pods_namespace("testteam")
#teamname="testteam"

#cicd_dboperator.delete_team_and_vpn("2");
#certdirlocationContainer=environ.get('CERT_DIR_CONTAINER','/home/lime/Desktop/ahaz/docker_experimenting/testCertDirs/')
#generatecert.del_team("2",certdirlocationContainer)
#cicd_controller.delete_namespace("2")
#cicd_dboperator.delete_team_and_vpn("2")
#policy = controller.create_network_policy(teamname)
#api = client.NetworkingV1Api()
#api_response_deny_all = api.create_namespaced_network_policy(namespace=teamname, body=policy_deny)
#api_response = api.create_namespaced_network_policy(namespace=teamname, body=policy)
generatecert.del_team("8","/home/lime/Desktop/ahaz/ahaz_from_env/ahaz_cicd_env_prod/certDirectory/")