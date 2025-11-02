import json
import logging
from os import getenv
from threading import Thread
from time import sleep

import cicd_controller as controller
import cicd_dboperator as dboperator
import generatecert
import uvicorn
from asgiref.wsgi import WsgiToAsgi
from flask import Flask, request

CERT_DIR_HOST = getenv("CERT_DIR_HOST", "/etc/ahaz/certs/")
CERT_DIR_CONTAINER = getenv("CERT_DIR_CONTAINER", "/etc/ahaz/certs/")
PUBLIC_DOMAINNAME = getenv("PUBLIC_DOMAINNAME", "ahaz.lan")
TEAM_PORT_RANGE_START = int(getenv("TEAM_PORT_RANGE_START", 31200))

app = Flask(__name__)

LOGLEVEL = getenv("LOGLEVEL", "INFO").upper()
logging.basicConfig(
    level=LOGLEVEL,
    format="[%(asctime)s | %(levelname)s | %(filename)s:%(lineno)d] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger()


@app.route("/genteam", methods=["GET"])
def team_get():
    return "genteamed"


@app.route("/start_challenge", methods=["POST", "GET"])
def start_challenge():
    request_data_json = request.get_json()

    logger.debug(
        f"Received start challenge request for challenge {request_data_json['challengename']}",
        f" from {request_data_json['teamname']}",
    )
    teamname = request_data_json["teamname"]
    challengename = request_data_json["challengename"]
    logger.info("--starting challenge ")
    logger.info(f" {teamname} {challengename}")
    status = controller.start_challenge(teamname, challengename)
    if status == 0:
        status = "successfully created challenge"
    return status


@app.route("/stop_challenge", methods=["POST", "GET"])
def stop_challenge():
    request_data_json = request.get_json()
    teamname = request_data_json["teamname"]
    challengename = request_data_json["challengename"]
    logger.info("--stopping challenge ")
    logger.info(f" {teamname} {challengename}")
    status = controller.stop_challenge(teamname, challengename)
    return status


@app.route("/get_images", methods=["GET"])
def get_images():
    get_images_json = dboperator.cicd_get_images_from_db()
    return get_images_json


@app.route("/get_challenges", methods=["GET"])
def get_challenges():
    get_challenges_json = dboperator.cicd_get_challenges_from_db()
    logger.debug(get_challenges_json)
    return str(get_challenges_json)


@app.route("/get_pods_namespace", methods=["GET"])
def get_pods_namespace():
    request_data_json = request.get_json()
    logger.debug(request_data_json)
    teamname = str(request_data_json["teamname"])
    podresult = controller.get_pods_namespace(teamname, 0)
    logger.debug(podresult)
    return podresult


@app.route("/add_user", methods=["POST"])
def adduser():
    logger.debug("---")
    request_data_json = request.get_json()
    teamname = request_data_json["teamname"]
    username = request_data_json["username"]
    logger.debug(teamname)
    logger.debug(username)
    userExists = dboperator.get_user_vpn_config(teamname=teamname, username=username)
    if userExists != "null":
        return "user already registered"

    def register_user_threaded():
        logger.debug("about to register user in docker")
        controller.docker_register_user(teamname, username)
        logger.debug("about to obtain config")
        config = controller.docker_obtain_user_vpn_config(teamname, username)
        logger.debug("about to insert config into db")
        dboperator.insert_user_vpn_config(teamname, username, config)
        logger.debug("successfully added a user to db")
        logger.info("-- Registered user (teamname, username )")
        logger.info(teamname, username)
        return "successfully added a user to db"

    # except:
    # return "issues adding "+username

    Thread(target=register_user_threaded, daemon=True).start()
    return "Started user creation as a thread"


@app.route("/get_user", methods=["GET"])
def getuser():
    request_data_json = request.get_json()
    teamname = request_data_json["teamname"]
    username = request_data_json["username"]
    return dboperator.get_user_vpn_config(teamname, username)


@app.route("/gen_team", methods=["POST"])
def team_post():
    logger.debug(request.get_json())
    request_data_json = request.get_json()
    request_data = json.dumps(request_data_json)
    error = "please specify a"
    teamname = ""
    domainname = ""
    port = -1
    protocol = "tcp"
    try:
        logger.debug(request_data_json["teamname"])
        teamname = request_data_json["teamname"]
    except:
        error += " teamname"
    try:
        logger.debug(request_data_json["domainname"])
        domainname = request_data_json["domainname"]
    except:
        error += " domainname"
    try:
        logger.debug(request_data_json["port"])
        port = int(request_data_json["port"])
    except:
        error += " port"
    try:
        logger.debug(request_data_json["protocol"])
        if request_data_json["protocol"] != "tcp" and request_data_json["protocol"] != "udp":
            return "protocol should be tcp or udp"
        else:
            protocol = request_data_json["protocol"]
    except:
        error += " protocol"
    if error == "please specify a":

        def gen_team_from_flask_for_subprocess():
            try:
                logger.debug("doing except")
                generatecert.gen_team(teamname, domainname, port, protocol, CERT_DIR_HOST, CERT_DIR_CONTAINER)
                controller.create_team_namespace(teamname)
                logger.debug("=8")
                controller.create_team_vpn_container(teamname)
                logger.debug("about to expose team vpn container")
                controller.expose_team_vpn_container(teamname, port)
                logger.debug("=9")
                dboperator.insert_team_into_db(teamname)
                dboperator.insert_vpn_port_into_db(teamname, port)
                return "Successfuly made a team"
            except:
                return "Something went wrong"

        Thread(target=gen_team_from_flask_for_subprocess, daemon=True).start()
        logger.info("started team creation as a thread %s", teamname)
        return "Started team creation as a thread"
    else:
        print("ERROR reigstering team ")
        print(error)
        return error


@app.route("/gen_team_lazy", methods=["POST"])
def team_post_lazy():
    logger.info(request.get_json())
    request_data_json = request.get_json()
    request_data = json.dumps(request_data_json)
    error = "please specify a"
    domainname = PUBLIC_DOMAINNAME
    port = int(dboperator.get_last_port()) + 1
    protocol = "tcp"
    teamname = request_data_json["teamname"]
    teamExists = dboperator.get_team_id(teamname)
    if teamExists != "null":
        return "team already exists"

    def team_post_lazy_subprocess():
        try:
            try:
                t1 = Thread(
                    generatecert.gen_team,
                    [teamname, domainname, port, protocol, CERT_DIR_HOST, CERT_DIR_CONTAINER],
                )
                t1.start()
            except:
                logger.debug("doing except")
                generatecert.gen_team(teamname, domainname, port, protocol, CERT_DIR_HOST, CERT_DIR_CONTAINER)
                controller.create_team_namespace(teamname)
                logger.debug("=8")
                controller.create_team_vpn_container(teamname)
                logger.debug("about to expose team vpn container")
                controller.expose_team_vpn_container(teamname, port)
                logger.debug("=9")
                dboperator.insert_team_into_db(teamname)
                dboperator.insert_vpn_port_into_db(teamname, port)
            logger.info("Successfully registered a team %s", teamname)
            return "Successfuly made a team"
        except:
            logger.error("ERROR registering a team %s", teamname)
            return "Something went wrong"

    Thread(target=team_post_lazy_subprocess, daemon=True).start()
    return "Started team creation as a thread"


@app.route("/autogenerate", methods=["POST", "GET"])
def autogenerate():
    logger.debug(request.get_json())
    request_data_json = request.get_json()
    request_data = json.dumps(request_data_json)
    domainname = PUBLIC_DOMAINNAME
    teamPortOffset_str = request_data_json["teamname"].replace(
        "a", ""
    )  # admin teams start with "a" and then contain the number
    logger.debug(teamPortOffset_str)
    port = TEAM_PORT_RANGE_START + int(
        teamPortOffset_str
    )  # use start + teamID for port, so that no two teams have the same port
    protocol = "tcp"
    teamname = request_data_json["teamname"]
    username = request_data_json["username"]
    logger.debug(port)
    logger.debug(teamname)
    logger.debug(username)

    # teamExists=dboperator.get_team_id(teamname)
    # if(teamExists != "null"):
    #    return "team already exists"
    def autogenerate_subprocess():
        try:
            if dboperator.get_registration_progress_team(teamname) == 10:
                return "team is being reregistered"
            logger.debug(dboperator.get_registration_progress_team(teamname))
            if (
                dboperator.get_registration_progress_team(teamname) == "null"
            ):  # if no team has been registered, register it
                dboperator.set_registration_progress_team(teamname, username, 1)
                logger.debug("started registration proces for a team")
                generatecert.gen_team(teamname, domainname, port, protocol, CERT_DIR_HOST, CERT_DIR_CONTAINER)
                dboperator.set_registration_progress_team(teamname, username, 2)
                logger.debug("generated certificates for team " + teamname)
                controller.create_team_namespace(teamname)
                logger.debug("created namespace for team " + teamname)
                dboperator.set_registration_progress_team(teamname, username, 3)
                controller.create_team_vpn_container(teamname)
                logger.debug("created VPN Container for team " + teamname)
                dboperator.set_registration_progress_team(teamname, username, 4)
                controller.expose_team_vpn_container(teamname, port)
                logger.debug("exposed VPN Container for team " + teamname)
                dboperator.set_registration_progress_team(teamname, username, 5)
                logger.debug("=9")
                dboperator.insert_team_into_db(teamname)
                dboperator.insert_vpn_port_into_db(teamname, port)
                logger.debug("inserted data into db for team " + teamname)
                dboperator.set_registration_progress_team(teamname, username, 6)
                logger.info("Successfully registered a team " + teamname)
            elif (
                dboperator.get_registration_progress_team(teamname) < 6
            ):  # status is less than 6, means that team is being registered, so wait while it is being done
                dboperator.set_registration_progress_team(teamname, username, 0)
                while dboperator.get_registration_progress_team(teamname) < 6:
                    logger.info("waiting for team " + teamname + " user " + username)
                    sleep(5)
                dboperator.set_registration_progress_team(teamname, username, 6)
            elif (
                dboperator.get_registration_progress_team(teamname) >= 6
            ):  # if team is already registered, then
                dboperator.set_registration_progress_team(teamname, username, 6)
            teststatus = dboperator.get_registration_progress_user(teamname, username)
            logger.debug(teststatus)
            sleep(
                2
            )  # in case the docker container for ovpn file creation is still running and doing something
            if dboperator.get_registration_progress_team(teamname) == 10:
                return "team is being reregistered"
            if (dboperator.get_registration_progress_user(teamname, username) == "null") or (
                dboperator.get_registration_progress_user(teamname, username) == 6
            ):  # if user isn't registered or this was the user that first called the team registration
                logger.debug("about to register user in docker")
                dboperator.set_registration_progress_team(teamname, username, 7)
                controller.docker_register_user(teamname, username)
                dboperator.set_registration_progress_team(teamname, username, 8)
                logger.debug("about to obtain config")
                config = controller.docker_obtain_user_vpn_config(teamname, username)
                logger.debug("about to insert config into db")
                dboperator.insert_user_vpn_config(teamname, username, config)
                dboperator.set_registration_progress_team(teamname, username, 9)
                logger.debug("successfully added a user to db")
                logger.info("-- Registered user (teamname, username )" + teamname + " " + username)
                return "successfully added a user to db"
            return "Successfuly made a team and registered a user"
        except Exception as e:
            logger.error(e)
            logger.error("ERROR registering a team " + teamname)
            return "Something went wrong"

    status_user = dboperator.get_registration_progress_user(teamname, username)
    if (
        status_user == "null"
    ):  # if progress is null, only then start the thread, otherwise give info about progress
        Thread(target=autogenerate_subprocess, daemon=True).start()
        sleep(1)
        status_user = dboperator.get_registration_progress_user(teamname, username)
        status_team = dboperator.get_registration_progress_team(teamname)
        return (
            '{ "message":"Started team and user creation as a thread","team_status":"'
            + str(status_team)
            + '", "user_status":"'
            + str(status_user)
            + '"}'
        )
    status_team = dboperator.get_registration_progress_team(teamname)
    return (
        '{ "message":"team creation thread is already running", "team_status":"'
        + str(status_team)
        + '", "user_status":"'
        + str(status_user)
        + '"}'
    )


@app.route("/regenerate", methods=["POST"])
def regenerate():
    request_data_json = request.get_json()
    domainname = PUBLIC_DOMAINNAME
    teamPortOffset_str = request_data_json["teamname"].replace(
        "a", ""
    )  # admin teams start with "a" and then contain the number
    logger.debug(teamPortOffset_str)
    teamPortOffset = int(teamPortOffset_str)
    logger.debug(teamPortOffset)
    port = (
        TEAM_PORT_RANGE_START + teamPortOffset
    )  # use start + teamID for port, so that no two teams have the same port
    protocol = "tcp"
    teamname = request_data_json["teamname"]
    username = request_data_json["username"]
    logger.debug(port)
    logger.debug(teamname)
    logger.debug(username)

    # teamExists=dboperator.get_team_id(teamname)
    # if(teamExists != "null"):
    #    return "team already exists"
    def autogenerate_subprocess():
        try:
            logger.debug(dboperator.get_registration_progress_team(teamname))
            if (
                dboperator.get_registration_progress_team(teamname) == "null"
            ):  # if no team has been registered, register it
                dboperator.set_registration_progress_team(teamname, username, 1)
                logger.debug("started registration proces for a team")
                generatecert.gen_team(teamname, domainname, port, protocol, CERT_DIR_HOST, CERT_DIR_CONTAINER)
                dboperator.set_registration_progress_team(teamname, username, 2)
                logger.debug("generated certificates for team " + teamname)
                controller.create_team_namespace(teamname)
                logger.debug("created namespace for team " + teamname)
                dboperator.set_registration_progress_team(teamname, username, 3)
                controller.create_team_vpn_container(teamname)
                logger.debug("created VPN Container for team " + teamname)
                dboperator.set_registration_progress_team(teamname, username, 4)
                controller.expose_team_vpn_container(teamname, port)
                logger.debug("exposed VPN Container for team " + teamname)
                dboperator.set_registration_progress_team(teamname, username, 5)
                logger.debug("=9")
                dboperator.insert_team_into_db(teamname)
                dboperator.insert_vpn_port_into_db(teamname, port)
                logger.debug("inserted data into db for team " + teamname)
                dboperator.set_registration_progress_team(teamname, username, 6)
                logger.info("Successfully registered a team " + teamname)
            elif (
                dboperator.get_registration_progress_team(teamname) < 6
            ):  # status is less than 6, means that team is being registered, so wait while it is being done
                dboperator.set_registration_progress_team(teamname, username, 0)
                while dboperator.get_registration_progress_team(teamname) < 6:
                    logger.info("waiting for team " + teamname + " user " + username)
                    sleep(5)
                dboperator.set_registration_progress_team(teamname, username, 6)
            elif (
                dboperator.get_registration_progress_team(teamname) >= 6
            ):  # if team is already registered, then
                dboperator.set_registration_progress_team(teamname, username, 6)
            teststatus = dboperator.get_registration_progress_user(teamname, username)
            logger.debug(teststatus)
            sleep(
                2
            )  # in case the docker container for ovpn file creation is still running and doing something
            if (dboperator.get_registration_progress_user(teamname, username) == "null") or (
                dboperator.get_registration_progress_user(teamname, username) == 6
            ):  # if user isn't registered or this was the user that first called the team registration
                logger.debug("about to register user in docker")
                dboperator.set_registration_progress_team(teamname, username, 7)
                controller.docker_register_user(teamname, username)
                dboperator.set_registration_progress_team(teamname, username, 8)
                logger.debug("about to obtain config")
                config = controller.docker_obtain_user_vpn_config(teamname, username)
                logger.debug("about to insert config into db")
                dboperator.insert_user_vpn_config(teamname, username, config)
                dboperator.set_registration_progress_team(teamname, username, 9)
                logger.debug("successfully added a user to db")
                logger.info("-- Registered user (teamname, username ) " + teamname + " " + username)
                return "successfully added a user to db"
            return "Successfully made a team and registered a user"
        except Exception as e:
            logger.error(e)
            logger.error("ERROR registering a team " + teamname)
            return "Something went wrong"

    def del_team_subprocess():
        logger.debug(str(teamname) + " called del_team_subprocess, about to delete namespace")
        controller.delete_namespace(teamname)
        logger.debug(str(teamname) + " namespace deleted, about to delete team VPN directory for team")
        generatecert.del_team(teamname, CERT_DIR_CONTAINER)
        logger.debug(str(teamname) + " cert Directory deleted, about to remove entries of team from db")
        dboperator.delete_team_and_vpn(teamname)
        logger.debug(str(teamname) + " entries of team removed from db")
        Thread(target=autogenerate_subprocess, daemon=True).start()

    Thread(target=del_team_subprocess, daemon=True).start()
    return "Started a thread for reregistration of team " + teamname


@app.route("/get_last_port", methods=["GET"])
def get_last_port():
    logger.debug("trying to run dboperator.get_last_port()")
    return str(dboperator.get_last_port())


@app.route("/del_team", methods=["POST"])
def del_team():
    request_data_json = request.get_json()
    request_data = json.dumps(request_data_json)
    teamname = request_data_json["teamname"]

    def del_team_subprocess():
        logger.debug(str(teamname) + " called del_team_subprocess, about to delete namespace")
        controller.delete_namespace(teamname)
        logger.debug(str(teamname) + " namespace deleted, about to delete team VPN directory for team")
        generatecert.del_team(teamname, CERT_DIR_CONTAINER)
        logger.debug(str(teamname) + " cert Directory deleted, about to remove entries of team from db")
        dboperator.delete_team_and_vpn(teamname)
        logger.debug(str(teamname) + " entries of team removed from db")

    Thread(target=del_team_subprocess(), daemon=True).start()
    return "Started a thread for deletion of team " + teamname


asgi = WsgiToAsgi(app)

if __name__ == "__main__":
    uvicorn.run("cicd_cerserver:asgi", host="0.0.0.0", port=5000, workers=4)
