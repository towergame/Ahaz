import generatecert
import controller
from flask import Flask, jsonify, request
import json
import dboperator
from threading import Thread
from os import path, environ 

#certDirLocation="/home/lime/Desktop/ahaz/docker_experimenting/testCertDirs/"
#certdirlocationContainer="/certdir/"
certDirLocation=environ.get('CERT_DIR_HOST')
certdirlocationContainer=environ.get('CERT_DIR_CONTAINER')
app = Flask(__name__)
public_domainname=environ.get('PUBLIC_DOMAINNAME',"test.lan")

@app.route('/genteam',methods=['GET'])
def team_get():
    return 'genteamed'

@app.route('/start_challenge', methods=['POST'])
def start_challenge():    
    request_data_json = request.get_json()
    teamname=request_data_json["teamname"]
    challengename=request_data_json["challengename"]
    print(teamname,challengename)
    status = controller.start_challenge(teamname,challengename)
    return status

@app.route('/stop_challenge', methods=['POST'])
def stop_challenge():
    request_data_json = request.get_json()
    teamname=request_data_json["teamname"]
    challengename=request_data_json["challengename"]
    print(teamname,challengename)
    status = controller.delete_challenge(teamname,challengename)
    return status        

@app.route('/insert_image', methods=['POST'])
def insert_image():
    request_data_json = request.get_json()
    repo=request_data_json["repo"]
    name=request_data_json["name"]
    tag=request_data_json["tag"]
    challengename=request_data_json["challengename"]
    dboperator.insert_image_into_db(repo,name,tag,challengename)
    return "added image to db"
@app.route('/get_image', methods=['GET'])
def get_image():
    request_data_json = request.get_json()
    challengename=request_data_json["challengename"]
    get_image_json=dboperator.get_image_from_db_json(challengename)
    return get_image_json
@app.route('/get_images', methods=['GET'])
def get_images():
    get_images_json=dboperator.get_images_from_db()
    return get_images_json
@app.route('/get_pods_namespace', methods=['GET'])
def get_pods_namespace():
    request_data_json = request.get_json()
    print(request_data_json)
    teamname=str(request_data_json["teamname"])
    podresult=controller.get_container_parameters(teamname)
    return podresult
    
@app.route('/add_user',methods=['POST'])
def adduser():
    print("---")
    request_data_json = request.get_json()
    teamname=request_data_json["teamname"]
    username=request_data_json["username"]
    print(teamname)
    print(username)
    userExists = dboperator.get_user_vpn_config(teamname=teamname,username=username)
    if(userExists != "null"):
        return "user already registered"
    try:
        #print("about to register user in docker")
        controller.docker_register_user(teamname,username)
        #print("about to obtain config")
        config = controller.docker_obtain_user_vpn_config(teamname,username)
        #print("about to insert config into db")
        dboperator.insert_user_vpn_config(teamname,username,config)
        return "successfully added a user to db"
    except:
        return "issues adding "+username
@app.route('/get_user',methods=['GET'])
def getuser():
    request_data_json = request.get_json()
    teamname=request_data_json["teamname"]
    username=request_data_json["username"]
    return dboperator.get_user_vpn_config(teamname,username)
    return controller.docker_obtain_user_vpn_config(teamname,username)
    
@app.route('/gen_team',methods=['POST'])
def team_post():
    print(request.get_json())
    request_data_json = request.get_json()
    request_data = json.dumps(request_data_json)
    error="please specify a"
    teamname=""
    domainname=""
    port=-1
    protocol="tcp"
    try:
        print(request_data_json["teamname"])
        teamname=request_data_json["teamname"]
    except:
        error+=" teamname"
    try:
        print(request_data_json["domainname"])
        domainname=request_data_json["domainname"]
    except:
        error+=" domainname"
    try:
        print(request_data_json["port"])
        port=int(request_data_json["port"])
    except:
        error+=" port"
    try:
        print(request_data_json["protocol"])
        if(request_data_json["protocol"] != "tcp" and request_data_json["protocol"] != "udp"):
            return "protocol should be tcp or udp"
        else:
            protocol=request_data_json["protocol"]
    except:
        error+=" protocol"
    if(error == "please specify a"):
        #certegen_result=generatecert.gen_team(teamname,domainname,port,protocol)
        
        try:
            #if(path.isdir(certDirLocation+teamname)):
            #    return "team already exists"
            try:
                t1 = Thread(generatecert.gen_team,[teamname,domainname,port,protocol,certDirLocation])
                t1.start()

            except:
                print("doing except")
                generatecert.gen_team(teamname,domainname,port,protocol,certDirLocation,certdirlocationContainer)
                controller.create_team_namespace(teamname)
                print("=8", end="")
                controller.create_team_vpn_container(teamname)
                print("about to expose team vpn container")
                controller.expose_team_vpn_container(teamname,port)
                print("=9", end="")
                dboperator.insert_team_into_db(teamname)
                dboperator.insert_vpn_port_into_db(teamname,port)
            return "Successfuly made a team"
        except:
            return "Something went wrong"
    else:
        return error

@app.route('/gen_team_lazy',methods=['POST'])
def team_post_lazy():
    print(request.get_json())
    request_data_json = request.get_json()
    request_data = json.dumps(request_data_json)
    error="please specify a"
    domainname=public_domainname
    port=int(dboperator.get_last_port())+1
    protocol="tcp"
    teamname=request_data_json["teamname"]
    teamExists=dboperator.get_team_id(teamname)
    if(teamExists != "null"):
        return "team already exists"
    try:
        try:
            t1 = Thread(generatecert.gen_team,[teamname,domainname,port,protocol,certDirLocation])
            t1.start()
        except:
            print("doing except")
            generatecert.gen_team(teamname,domainname,port,protocol,certDirLocation,certdirlocationContainer)
            controller.create_team_namespace(teamname)
            print("=8", end="")
            controller.create_team_vpn_container(teamname)
            print("about to expose team vpn container")
            controller.expose_team_vpn_container(teamname,port)
            print("=9", end="")
            dboperator.insert_team_into_db(teamname)
            dboperator.insert_vpn_port_into_db(teamname,port)
        return "Successfuly made a team"
    except:
        return "Something went wrong"
@app.route('/get_last_port',methods=['GET'])
def get_last_port():
    print("trying to run dboperator.get_last_port()")
    return str(dboperator.get_last_port())
#if __name__ == "__main__":
    #app.run(host="0.0.0.0")