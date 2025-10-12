import generatecert
import cicd_controller as controller
import cicd_dboperator as dboperator
from flask import Flask, jsonify, request
import json
from threading import Thread
from os import path, environ 
from time import sleep

verbose = environ.get("VERBOSE","True").lower() in ('true', '1', 't')
if(verbose):print("verbose set to true")
#certDirLocation="/home/lime/Desktop/ahaz/docker_experimenting/testCertDirs/"
#certdirlocationContainer="/certdir/"
certDirLocation=environ.get('CERT_DIR_HOST','/home/lime/Desktop/ahaz/ahaz_from_env/ahaz_cicd_env_prod/certDirectory/')
certdirlocationContainer=environ.get('CERT_DIR_CONTAINER','/home/lime/Desktop/ahaz/ahaz_from_env/ahaz_cicd_env_prod/certDirectory/')
app = Flask(__name__)
public_domainname=environ.get('PUBLIC_DOMAINNAME',"test.lan")
TeamPortRangeStart=int(environ.get('TEAM_PORT_RANGE_START',31200))




@app.route('/genteam',methods=['GET'])
def team_get():
    return 'genteamed'

@app.route('/start_challenge', methods=['POST','GET'])
def start_challenge():    
    request_data_json = request.get_json()
    if (verbose): print("1234567890")
    if (verbose): print(request_data_json)
    teamname=request_data_json["teamname"]
    challengename=request_data_json["challengename"]
    print("--starting challenge ",end="")
    print(teamname,challengename)
    status = controller.start_challenge(teamname,challengename)
    if status == 0:
        status = "successfully created challenge"
    return status

@app.route('/stop_challenge', methods=['POST','GET'])
def stop_challenge():
    request_data_json = request.get_json()
    teamname=request_data_json["teamname"]
    challengename=request_data_json["challengename"]
    print("--stopping challenge ",end="")
    print(teamname,challengename)
    status = controller.stop_challenge(teamname,challengename)
    return status        
# performed by CICD
# @app.route('/insert_image', methods=['POST'])
# def insert_image():
#     request_data_json = request.get_json()
#     repo=request_data_json["repo"]
#     name=request_data_json["name"]
#     tag=request_data_json["tag"]
#     challengename=request_data_json["challengename"]
#     dboperator.insert_image_into_db(repo,name,tag,challengename)
#     return "added image to db"
# @app.route('/get_image', methods=['GET'])
# def get_image():
#     request_data_json = request.get_json()
#     challengename=request_data_json["challengename"]
#     get_image_json=dboperator.get_image_from_db_json(challengename)
#     return get_image_json
@app.route('/get_images', methods=['GET'])
def get_images():
    get_images_json=dboperator.cicd_get_images_from_db()
    return get_images_json
@app.route('/get_challenges',methods=['GET'])
def get_challenges():
    get_challenges_json=dboperator.cicd_get_challenges_from_db()
    if (verbose): print(get_challenges_json)
    return str(get_challenges_json)
@app.route('/get_pods_namespace', methods=['GET'])
def get_pods_namespace():
    request_data_json = request.get_json()
    if (verbose): print(request_data_json)
    teamname=str(request_data_json["teamname"])
    podresult=controller.get_pods_namespace(teamname,0)
    if (verbose): print(podresult)
    return podresult
    
@app.route('/add_user',methods=['POST'])
def adduser():
    if(verbose): print("---")
    request_data_json = request.get_json()
    teamname=request_data_json["teamname"]
    username=request_data_json["username"]
    if(verbose): print(teamname)
    if(verbose): print(username)
    userExists = dboperator.get_user_vpn_config(teamname=teamname,username=username)
    if(userExists != "null"):
        return "user already registered"
    def register_user_threaded():
        if(verbose): print("about to register user in docker")
        controller.docker_register_user(teamname,username)
        if(verbose): print("about to obtain config")
        config = controller.docker_obtain_user_vpn_config(teamname,username)
        if(verbose): print("about to insert config into db")
        dboperator.insert_user_vpn_config(teamname,username,config)
        if(verbose): print("successfully added a user to db")
        print("-- Registered user (teamname, username )",end="")
        print(teamname,username)
        return "successfully added a user to db"
    #except:
        #return "issues adding "+username
    
    Thread(target=register_user_threaded, daemon=True).start()
    return "Started user creation as a thread"
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
        if (verbose): print(request_data_json["teamname"])
        teamname=request_data_json["teamname"]
    except:
        error+=" teamname"
    try:
        if (verbose): print(request_data_json["domainname"])
        domainname=request_data_json["domainname"]
    except:
        error+=" domainname"
    try:
        if (verbose): print(request_data_json["port"])
        port=int(request_data_json["port"])
    except:
        error+=" port"
    try:
        if (verbose): print(request_data_json["protocol"])
        if(request_data_json["protocol"] != "tcp" and request_data_json["protocol"] != "udp"):
            return "protocol should be tcp or udp"
        else:
            protocol=request_data_json["protocol"]
    except:
        error+=" protocol"
    if(error == "please specify a"):
        def gen_team_from_flask_for_subprocess():
            try:
                if(verbose): print("doing except")
                generatecert.gen_team(teamname,domainname,port,protocol,certDirLocation,certdirlocationContainer)
                controller.create_team_namespace(teamname)
                if(verbose): print("=8", end="")
                controller.create_team_vpn_container(teamname)
                if(verbose): print("about to expose team vpn container")
                controller.expose_team_vpn_container(teamname,port)
                if(verbose): print("=9", end="")
                dboperator.insert_team_into_db(teamname)
                dboperator.insert_vpn_port_into_db(teamname,port)
                return "Successfuly made a team"
            except:
                return "Something went wrong"
        Thread(target=gen_team_from_flask_for_subprocess, daemon=True).start()
        print("started team creation as a thread ",end="")
        print(teamname)
        return "Started team creation as a thread"
    else:
        print("ERROR reigstering team ",end="")
        print(error)
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
    def team_post_lazy_subprocess():
        try:
            try:
                t1 = Thread(generatecert.gen_team,[teamname,domainname,port,protocol,certDirLocation])
                t1.start()
            except:
                if (verbose): print("doing except")
                generatecert.gen_team(teamname,domainname,port,protocol,certDirLocation,certdirlocationContainer)
                controller.create_team_namespace(teamname)
                if (verbose): print("=8", end="")
                controller.create_team_vpn_container(teamname)
                if (verbose): print("about to expose team vpn container")
                controller.expose_team_vpn_container(teamname,port)
                if (verbose): print("=9", end="")
                dboperator.insert_team_into_db(teamname)
                dboperator.insert_vpn_port_into_db(teamname,port)
            print("Successfully registered a team",end="")
            print(teamname)
            return "Successfuly made a team"
        except:
            print("ERROR registering a team ",end="")
            print(teamname)
            return "Something went wrong"
    Thread(target=team_post_lazy_subprocess, daemon=True).start()
    return "Started team creation as a thread"
@app.route('/autogenerate',methods=['POST','GET'])
def autogenerate():
    if(verbose):print(request.get_json())
    request_data_json = request.get_json()
    request_data = json.dumps(request_data_json)
    domainname=public_domainname
    teamPortOffset_str=request_data_json["teamname"].replace("a","")#admin teams start with "a" and then contain the number
    if(verbose):print(teamPortOffset_str)
    teamPortOffset=int(teamPortOffset_str)
    if(verbose):print(teamPortOffset)
    port=TeamPortRangeStart+teamPortOffset # use start + teamID for port, so that no two teams have the same port
    protocol="tcp"
    teamname=request_data_json["teamname"]
    username=request_data_json["username"]
    if(verbose):print(port)
    if(verbose):print(teamname)
    if(verbose):print(username)
    #teamExists=dboperator.get_team_id(teamname)
    #if(teamExists != "null"):
    #    return "team already exists"
    def autogenerate_subprocess():
        try:
            if dboperator.get_registration_progress_team(teamname) == 10:
                return "team is being reregistered"
            if(verbose):print(dboperator.get_registration_progress_team(teamname))
            if dboperator.get_registration_progress_team(teamname) == "null": #if no team has been registered, register it
                dboperator.set_registration_progress_team(teamname,username,1)
                if (verbose): print("started registration proces for a team")
                generatecert.gen_team(teamname,domainname,port,protocol,certDirLocation,certdirlocationContainer)
                dboperator.set_registration_progress_team(teamname,username,2)
                if (verbose): print("generated certificates for team "+teamname)
                controller.create_team_namespace(teamname)
                if (verbose): print("created namespace for team "+teamname)
                dboperator.set_registration_progress_team(teamname,username,3)
                controller.create_team_vpn_container(teamname)
                if (verbose): print("created VPN Container for team "+teamname)
                dboperator.set_registration_progress_team(teamname,username,4)
                controller.expose_team_vpn_container(teamname,port)
                if (verbose): print("exposed VPN Container for team "+teamname)
                dboperator.set_registration_progress_team(teamname,username,5)
                if (verbose): print("=9", end="")
                dboperator.insert_team_into_db(teamname)
                dboperator.insert_vpn_port_into_db(teamname,port)
                if (verbose): print("inserted data into db for team "+teamname)
                dboperator.set_registration_progress_team(teamname,username,6)
                print("Successfully registered a team ",end="")
                print(teamname)
            elif dboperator.get_registration_progress_team(teamname)<6: #status is less than 6, means that team is being registered, so wait while it is being done
                dboperator.set_registration_progress_team(teamname,username,0)
                while (dboperator.get_registration_progress_team(teamname)<6):
                    print("waiting for team "+teamname+" user "+username)
                    sleep(5)
                dboperator.set_registration_progress_team(teamname,username,6)
            elif dboperator.get_registration_progress_team(teamname)>=6: # if team is already registered, then 
                dboperator.set_registration_progress_team(teamname,username,6)
            teststatus=dboperator.get_registration_progress_user(teamname,username)
            if(verbose):print(teststatus)
            sleep(2) # in case the docker container for ovpn file creation is still running and doing something
            if dboperator.get_registration_progress_team(teamname) == 10:
                return "team is being reregistered"
            if (dboperator.get_registration_progress_user(teamname,username)=="null") or (dboperator.get_registration_progress_user(teamname,username)==6): #if user isn't registered or this was the user that first called the team registration
                if(verbose): print("about to register user in docker")
                dboperator.set_registration_progress_team(teamname,username,7)
                controller.docker_register_user(teamname,username)
                dboperator.set_registration_progress_team(teamname,username,8)
                if(verbose): print("about to obtain config")
                config = controller.docker_obtain_user_vpn_config(teamname,username)
                if(verbose): print("about to insert config into db")
                dboperator.insert_user_vpn_config(teamname,username,config)
                dboperator.set_registration_progress_team(teamname,username,9)
                if(verbose): print("successfully added a user to db")
                print("-- Registered user (teamname, username )",end="")
                print(teamname,username)
                return "successfully added a user to db"
            return "Successfuly made a team and registered a user"
        except Exception as e:
            print(e)
            print("ERROR registering a team ",end="")
            print(teamname)
            return "Something went wrong"
    
    status_user = dboperator.get_registration_progress_user(teamname,username)
    if status_user=="null": #if progress is null, only then start the thread, otherwise give info about progress
        Thread(target=autogenerate_subprocess, daemon=True).start()
        sleep(1)
        status_user = dboperator.get_registration_progress_user(teamname,username)
        status_team = dboperator.get_registration_progress_team(teamname)
        return '{ "message":"Started team and user creation as a thread","team_status":"'+str(status_team)+'", "user_status":"'+str(status_user)+'"}'
    status_team = dboperator.get_registration_progress_team(teamname)
    return '{ "message":"team creation thread is already running", "team_status":"'+str(status_team)+'", "user_status":"'+str(status_user)+'"}'
@app.route('/regenerate',methods=['POST'])
def regenerate():
    request_data_json = request.get_json()
    domainname=public_domainname
    teamPortOffset_str=request_data_json["teamname"].replace("a","")#admin teams start with "a" and then contain the number
    if(verbose):print(teamPortOffset_str)
    teamPortOffset=int(teamPortOffset_str)
    if(verbose):print(teamPortOffset)
    port=TeamPortRangeStart+teamPortOffset # use start + teamID for port, so that no two teams have the same port
    protocol="tcp"
    teamname=request_data_json["teamname"]
    username=request_data_json["username"]
    if(verbose):print(port)
    if(verbose):print(teamname)
    if(verbose):print(username)
    #teamExists=dboperator.get_team_id(teamname)
    #if(teamExists != "null"):
    #    return "team already exists"
    def autogenerate_subprocess():
        try:
            if(verbose):print(dboperator.get_registration_progress_team(teamname))
            if dboperator.get_registration_progress_team(teamname) == "null": #if no team has been registered, register it
                dboperator.set_registration_progress_team(teamname,username,1)
                if (verbose): print("started registration proces for a team")
                generatecert.gen_team(teamname,domainname,port,protocol,certDirLocation,certdirlocationContainer)
                dboperator.set_registration_progress_team(teamname,username,2)
                if (verbose): print("generated certificates for team "+teamname)
                controller.create_team_namespace(teamname)
                if (verbose): print("created namespace for team "+teamname)
                dboperator.set_registration_progress_team(teamname,username,3)
                controller.create_team_vpn_container(teamname)
                if (verbose): print("created VPN Container for team "+teamname)
                dboperator.set_registration_progress_team(teamname,username,4)
                controller.expose_team_vpn_container(teamname,port)
                if (verbose): print("exposed VPN Container for team "+teamname)
                dboperator.set_registration_progress_team(teamname,username,5)
                if (verbose): print("=9", end="")
                dboperator.insert_team_into_db(teamname)
                dboperator.insert_vpn_port_into_db(teamname,port)
                if (verbose): print("inserted data into db for team "+teamname)
                dboperator.set_registration_progress_team(teamname,username,6)
                print("Successfully registered a team ",end="")
                print(teamname)
            elif dboperator.get_registration_progress_team(teamname)<6: #status is less than 6, means that team is being registered, so wait while it is being done
                dboperator.set_registration_progress_team(teamname,username,0)
                while (dboperator.get_registration_progress_team(teamname)<6):
                    print("waiting for team "+teamname+" user "+username)
                    sleep(5)
                dboperator.set_registration_progress_team(teamname,username,6)
            elif dboperator.get_registration_progress_team(teamname)>=6: # if team is already registered, then 
                dboperator.set_registration_progress_team(teamname,username,6)
            teststatus=dboperator.get_registration_progress_user(teamname,username)
            if(verbose):print(teststatus)
            sleep(2) # in case the docker container for ovpn file creation is still running and doing something
            if (dboperator.get_registration_progress_user(teamname,username)=="null") or (dboperator.get_registration_progress_user(teamname,username)==6): #if user isn't registered or this was the user that first called the team registration
                if(verbose): print("about to register user in docker")
                dboperator.set_registration_progress_team(teamname,username,7)
                controller.docker_register_user(teamname,username)
                dboperator.set_registration_progress_team(teamname,username,8)
                if(verbose): print("about to obtain config")
                config = controller.docker_obtain_user_vpn_config(teamname,username)
                if(verbose): print("about to insert config into db")
                dboperator.insert_user_vpn_config(teamname,username,config)
                dboperator.set_registration_progress_team(teamname,username,9)
                if(verbose): print("successfully added a user to db")
                print("-- Registered user (teamname, username )",end="")
                print(teamname,username)
                return "successfully added a user to db"
            return "Successfuly made a team and registered a user"
        except Exception as e:
            print(e)
            print("ERROR registering a team ",end="")
            print(teamname)
            return "Something went wrong"

    def del_team_subprocess():
        if(verbose):str(teamname)+" called del_team_subprocess, about to delete namespace"
        controller.delete_namespace(teamname)
        if(verbose):str(teamname)+" namespace deleted, about to delete team VPN directory for team"
        generatecert.del_team(teamname,certdirlocationContainer)
        if(verbose):str(teamname)+" cert Directory deleted, about to remove entries of team from db"
        dboperator.delete_team_and_vpn(teamname)
        if(verbose):str(teamname)+" entries of team removed from db"
        Thread(target=autogenerate_subprocess,daemon=True).start()

    Thread(target=del_team_subprocess,daemon=True).start()
    return "Started a thread for reregistration of team "+teamname

@app.route('/get_last_port',methods=['GET'])
def get_last_port():
    if (verbose): print("trying to run dboperator.get_last_port()")
    return str(dboperator.get_last_port())

@app.route('/del_team',methods=['POST'])
def del_team():
    request_data_json = request.get_json()
    request_data = json.dumps(request_data_json)
    teamname = request_data_json["teamname"]
    def del_team_subprocess():
        if(verbose):str(teamname)+" called del_team_subprocess, about to delete namespace"
        controller.delete_namespace(teamname)
        if(verbose):str(teamname)+" namespace deleted, about to delete team VPN directory for team"
        generatecert.del_team(teamname,certdirlocationContainer)
        if(verbose):str(teamname)+" cert Directory deleted, about to remove entries of team from db"
        dboperator.delete_team_and_vpn(teamname)
        if(verbose):str(teamname)+" entries of team removed from db"
    Thread(target=del_team_subprocess(),daemon=True).start()
    return "Started a thread for deletion of team "+teamname

if __name__ == "__main__":
    app.run(host="0.0.0.0")
#if __name__ == "__main__":
#    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)
