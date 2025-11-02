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
from pydantic import ValidationError

from ahaz_common import (
    ChallengeRequest,
    RegisterTeamRequest,
    TeamRequest,
    UserRequest,
)

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
    try:
        request_data = ChallengeRequest(**request.get_json())
    except ValidationError as e:
        logger.error(f"Validation error: {e}")
        return "Invalid request data", 400

    logger.info(
        f"Received start challenge request for challenge {request_data.challenge_id}",
        f" from {request_data.user_id}",
    )
    status = controller.start_challenge(request_data.user_id, request_data.challenge_id)
    if status == 0:
        status = "successfully created challenge"
    return status


@app.route("/stop_challenge", methods=["POST", "GET"])
def stop_challenge():
    try:
        request_data = ChallengeRequest(**request.get_json())
    except ValidationError as e:
        logger.error(f"Validation error: {e}")
        return "Invalid request data", 400

    logger.info(
        f"Received stop challenge request for challenge {request_data.challenge_id}",
        f" from {request_data.user_id}",
    )
    status = controller.stop_challenge(request_data.user_id, request_data.challenge_id)
    return status


@app.route("/get_images", methods=["GET"])
def get_images():
    get_images_json = dboperator.get_images_from_db()
    return get_images_json


@app.route("/get_challenges", methods=["GET"])
def get_challenges():
    get_challenges_json = dboperator.cicd_get_challenges_from_db()
    logger.debug(get_challenges_json)
    return str(get_challenges_json)


@app.route("/get_pods_namespace", methods=["GET"])
def get_pods_namespace():
    try:
        request_data = TeamRequest(**request.get_json())
    except ValidationError as e:
        logger.error(f"Validation error: {e}")
        return "Invalid request data", 400

    logger.info(f"Getting pods for team {request_data.team_id}")
    podresult = controller.get_pods_namespace(str(request_data.team_id), 0)
    logger.debug(f"Pods for team {request_data.team_id}:\n{podresult}")
    return podresult


def register_user_threaded(request_data: UserRequest):
    logger.info(f"Registering user {request_data.user_id} to team {request_data.team_id}...")
    logger.debug("About to register user in docker")
    controller.docker_register_user(teamname=request_data.team_id, username=request_data.user_id)
    logger.debug("About to obtain config")
    config = controller.docker_obtain_user_vpn_config(
        teamname=request_data.team_id, username=request_data.user_id
    )
    logger.debug("About to insert config into db")
    dboperator.insert_user_vpn_config(
        teamname=request_data.team_id, username=request_data.user_id, config=config
    )
    logger.debug("Successfully added a user to db")
    return "successfully added a user to db"


@app.route("/add_user", methods=["POST"])
def adduser():
    try:
        request_data = UserRequest(**request.get_json())
    except ValidationError as e:
        logger.error(f"Validation error: {e}")
        return "Invalid request data", 400

    userExists = dboperator.get_user_vpn_config(teamname=request_data.team_id, username=request_data.user_id)

    if userExists != "null":
        return "user already registered"

    Thread(target=register_user_threaded, args=(request_data,), daemon=True).start()
    return "Started user creation as a thread"


@app.route("/get_user", methods=["GET"])
def getuser():
    try:
        request_data = UserRequest(**request.get_json())
    except ValidationError as e:
        logger.error(f"Validation error: {e}")
        return "Invalid request data", 400

    return dboperator.get_user_vpn_config(teamname=request_data.team_id, username=request_data.user_id)


def gen_team_from_flask_for_subprocess(request_data: RegisterTeamRequest):
    try:
        logger.debug("doing except")
        generatecert.gen_team(
            request_data.team_id,
            request_data.domain_name,
            request_data.port,
            request_data.protocol,
            CERT_DIR_HOST,
            CERT_DIR_CONTAINER,
        )
        controller.create_team_namespace(request_data.team_id)
        logger.debug("=8")
        controller.create_team_vpn_container(request_data.team_id)
        logger.debug("about to expose team vpn container")
        controller.expose_team_vpn_container(request_data.team_id, request_data.port)
        logger.debug("=9")
        dboperator.insert_team_into_db(request_data.team_id)
        dboperator.insert_vpn_port_into_db(request_data.team_id, request_data.port)
        return "Successfully made a team"
    except Exception as e:
        logger.error(f"Error creating team: {e}")
        return "Something went wrong"


@app.route("/gen_team", methods=["POST"])
def team_post():
    try:
        request_data = RegisterTeamRequest(**request.get_json())
    except ValidationError as e:
        logger.error(f"Validation error: {e}")
        return "Invalid request data", 400

    Thread(target=gen_team_from_flask_for_subprocess, args=(request_data,), daemon=True).start()
    logger.info(f"Started team creation as a thread {request_data.team_id}")
    return "Started team creation as a thread"


def team_post_lazy_subprocess(request_data: TeamRequest):
    port = int(dboperator.get_last_port()) + 1
    try:
        try:
            t1 = Thread(
                target=generatecert.gen_team,
                args=[
                    request_data.team_id,
                    PUBLIC_DOMAINNAME,
                    port,
                    "tcp",
                    CERT_DIR_HOST,
                    CERT_DIR_CONTAINER,
                ],
            )
            t1.start()
        except Exception as e:
            logger.error(f"Error starting certificate generation thread: {e}")
            logger.debug("doing except")
            generatecert.gen_team(
                request_data.team_id, PUBLIC_DOMAINNAME, port, "tcp", CERT_DIR_HOST, CERT_DIR_CONTAINER
            )
            controller.create_team_namespace(request_data.team_id)
            logger.debug("=8")
            controller.create_team_vpn_container(request_data.team_id)
            logger.debug("about to expose team vpn container")
            controller.expose_team_vpn_container(request_data.team_id, port)
            logger.debug("=9")
            dboperator.insert_team_into_db(request_data.team_id)
            dboperator.insert_vpn_port_into_db(request_data.team_id, port)
        logger.info("Successfully registered a team %s", request_data.team_id)
        return "Successfully made a team"
    except Exception as e:
        logger.error("ERROR registering a team %s: %s", request_data.team_id, e)
        return "Something went wrong"


@app.route("/gen_team_lazy", methods=["POST"])
def team_post_lazy():
    try:
        request_data = TeamRequest(**request.get_json())
    except ValidationError as e:
        logger.error(f"Validation error: {e}")
        return "Invalid request data", 400

    teamExists = dboperator.get_team_id(request_data.team_id)
    if teamExists != "null":
        return "Team already exists"

    Thread(target=team_post_lazy_subprocess, args=(request_data,), daemon=True).start()
    return "Started team creation as a thread"


def autogenerate_subprocess(request_data: UserRequest, port=-1):
    if port == -1:
        port = int(dboperator.get_last_port()) + 1
    try:
        if dboperator.get_registration_progress_team(request_data.team_id) == 10:
            return "team is being reregistered"
        logger.debug(dboperator.get_registration_progress_team(request_data.team_id))
        if (
            dboperator.get_registration_progress_team(request_data.team_id) == -999
        ):  # if no team has been registered, register it
            dboperator.set_registration_progress_team(request_data.team_id, request_data.user_id, 1)
            logger.debug("started registration proces for a team")

            generatecert.gen_team(
                request_data.team_id, PUBLIC_DOMAINNAME, port, "tcp", CERT_DIR_HOST, CERT_DIR_CONTAINER
            )
            dboperator.set_registration_progress_team(request_data.team_id, request_data.user_id, 2)
            logger.debug(f"generated certificates for team {request_data.team_id}")

            controller.create_team_namespace(request_data.team_id)
            logger.debug(f"created namespace for team {request_data.team_id}")

            dboperator.set_registration_progress_team(request_data.team_id, request_data.user_id, 3)
            controller.create_team_vpn_container(request_data.team_id)
            logger.debug(f"created VPN Container for team {request_data.team_id}")

            dboperator.set_registration_progress_team(request_data.team_id, request_data.user_id, 4)
            controller.expose_team_vpn_container(request_data.team_id, port)
            logger.debug(f"exposed VPN Container for team {request_data.team_id}")

            dboperator.set_registration_progress_team(request_data.team_id, request_data.user_id, 5)
            logger.debug("mystical 5th step performed")

            dboperator.insert_team_into_db(request_data.team_id)
            dboperator.insert_vpn_port_into_db(request_data.team_id, port)
            logger.debug(f"inserted data into db for team {request_data.team_id}")

            dboperator.set_registration_progress_team(request_data.team_id, request_data.user_id, 6)
            logger.info(f"Successfully registered a team {request_data.team_id}")
        elif (
            dboperator.get_registration_progress_team(request_data.team_id) < 6
        ):  # status is less than 6, means that team is being registered, so wait while it is being done
            dboperator.set_registration_progress_team(request_data.team_id, request_data.user_id, 0)

            while dboperator.get_registration_progress_team(request_data.team_id) < 6:
                logger.info(f"waiting for team {request_data.team_id} user {request_data.user_id}")
                sleep(5)

            dboperator.set_registration_progress_team(request_data.team_id, request_data.user_id, 6)
        elif (
            dboperator.get_registration_progress_team(request_data.team_id) >= 6
        ):  # if team is already registered, then
            dboperator.set_registration_progress_team(request_data.team_id, request_data.user_id, 6)

        teststatus = dboperator.get_registration_progress_user(request_data.team_id, request_data.user_id)
        logger.debug(teststatus)
        sleep(2)  # in case the docker container for ovpn file creation is still running and doing something

        if dboperator.get_registration_progress_team(request_data.team_id) == 10:
            return "team is being reregistered"
        if (
            dboperator.get_registration_progress_user(request_data.team_id, request_data.user_id) == "null"
        ) or (
            dboperator.get_registration_progress_user(request_data.team_id, request_data.user_id) == 6
        ):  # if user isn't registered or this was the user that first called the team registration
            logger.debug("about to register user in docker")
            dboperator.set_registration_progress_team(request_data.team_id, request_data.user_id, 7)
            controller.docker_register_user(request_data.team_id, request_data.user_id)

            dboperator.set_registration_progress_team(request_data.team_id, request_data.user_id, 8)
            logger.debug("about to obtain config")
            config = controller.docker_obtain_user_vpn_config(request_data.team_id, request_data.user_id)
            logger.debug("about to insert config into db")
            dboperator.insert_user_vpn_config(request_data.team_id, request_data.user_id, config)

            dboperator.set_registration_progress_team(request_data.team_id, request_data.user_id, 9)
            logger.debug("successfully added a user to db")
            logger.info(f"Registered user {request_data.user_id} to team {request_data.team_id}")
            return "successfully added a user to db"
        return "Successfuly made a team and registered a user"
    except Exception as e:
        logger.error(e)
        logger.error(f"ERROR registering a team {request_data.team_id}")
        return "Something went wrong"


@app.route("/autogenerate", methods=["POST", "GET"])
def autogenerate():
    try:
        request_data = UserRequest(**request.get_json())
    except ValidationError as e:
        logger.error(f"Validation error: {e}")
        return "Invalid request data", 400

    # teamExists=dboperator.get_team_id(teamname)
    # if(teamExists != "null"):
    #    return "team already exists"

    status_user = dboperator.get_registration_progress_user(request_data.team_id, request_data.user_id)
    if (
        status_user == "null"
    ):  # if progress is null, only then start the thread, otherwise give info about progress
        Thread(target=autogenerate_subprocess, args=(request_data,), daemon=True).start()
        sleep(1)
        status_user = dboperator.get_registration_progress_user(request_data.team_id, request_data.user_id)
        status_team = dboperator.get_registration_progress_team(request_data.team_id)
        return (
            '{ "message":"Started team and user creation as a thread","team_status":"'
            + str(status_team)
            + '", "user_status":"'
            + str(status_user)
            + '"}'
        )

    status_team = dboperator.get_registration_progress_team(request_data.team_id)
    return (
        '{ "message":"team creation thread is already running", "team_status":"'
        + str(status_team)
        + '", "user_status":"'
        + str(status_user)
        + '"}'
    )


def del_team_subprocess(request_data: UserRequest | TeamRequest, reregister=False):
    logger.debug(str(request_data.team_id) + " called del_team_subprocess, about to delete namespace")
    controller.delete_namespace(request_data.team_id)
    logger.debug(
        str(request_data.team_id) + " namespace deleted, about to delete team VPN directory for team"
    )
    generatecert.del_team(request_data.team_id, CERT_DIR_CONTAINER)
    logger.debug(
        str(request_data.team_id) + " cert Directory deleted, about to remove entries of team from db"
    )
    dboperator.delete_team_and_vpn(request_data.team_id)
    logger.debug(str(request_data.team_id) + " entries of team removed from db")

    if reregister:
        if not isinstance(request_data, UserRequest):
            logger.error("Reregister flag set but request_data is not UserRequest")
            return
        Thread(
            target=autogenerate_subprocess,
            args=(request_data, TEAM_PORT_RANGE_START + int(request_data.team_id.replace("a", ""))),
            daemon=True,
        ).start()


@app.route("/regenerate", methods=["POST"])
def regenerate():
    try:
        request_data = UserRequest(**request.get_json())
    except ValidationError as e:
        logger.error(f"Validation error: {e}")
        return "Invalid request data", 400

    # teamExists=dboperator.get_team_id(teamname)
    # if(teamExists != "null"):
    #    return "team already exists"

    Thread(target=del_team_subprocess, args=(request_data,), daemon=True).start()
    return f"Started a thread for reregistration of team {request_data.team_id}"


@app.route("/get_last_port", methods=["GET"])
def get_last_port():
    logger.debug("trying to run dboperator.get_last_port()")
    return str(dboperator.get_last_port())


@app.route("/del_team", methods=["POST"])
def del_team():
    request_data_json = request.get_json()
    request_data = json.dumps(request_data_json)
    teamname = request_data_json["teamname"]

    try:
        request_data = TeamRequest(**request.get_json())
    except ValidationError as e:
        logger.error(f"Validation error: {e}")
        return "Invalid request data", 400

    Thread(target=del_team_subprocess, args=(request_data,), daemon=True).start()
    return f"Started a thread for deletion of team {teamname}"


asgi = WsgiToAsgi(app)

if __name__ == "__main__":
    uvicorn.run("cicd_cerserver:asgi", host="0.0.0.0", port=5000, workers=4)
