#!/usr/bin/env python3

import argparse
import io
import logging
import re
import subprocess
import tarfile
import tempfile
from os import listdir, makedirs, path
from shutil import rmtree
from typing import Generator

import jinja2
import requests
import yaml

logger = logging.getLogger()
script_dir = path.dirname(path.realpath(__file__))
tools_dir = path.abspath(path.join(script_dir, "tools"))
verbose = True
wildcard = "*"
defaults = {
    "eve": False,
    "domain": None,
    "challenges_directory": "./challenges",
    "challenges": {"*": {"port": 1194, "openvpn_management_port": None, "ifconfig": None}},
    "registrar": {
        "port": 3960,
        "network": "default",
        "tls_enabled": False,
        "tls_verify_client": False,
        "tls_clients": [],
    },
}

GITHUB_RELEASE_API = "https://api.github.com/repos/OpenVPN/easy-rsa/releases/{:s}"
EASYRSA_TAG = "v3.1.0"
EASYRSA_VERSION_PATTERN = re.compile(r"(?:EasyRSA-)?v?((?:\d+\.)*\d+)")
REGISTRAR_CERT_DIR = path


def easyrsa_release(tag=None, timeout=5):
    """
    Get the EasyRSA release information from github at a tag or latest if tag is None
    Returns a dictionary parsed from the GitHub release API (https://developer.github.com/v3/repos/releases/)
    """
    name = "latest" if tag is None else "tags/" + tag
    with requests.get(GITHUB_RELEASE_API.format(name), timeout=timeout) as resp:
        resp.raise_for_status()
        return resp.json()


def easyrsa_installations(dir) -> Generator[tuple[str, str], None, None]:
    """Get the EasyRSA versions installed. Returns (version tag, path) tuples for each installed version"""
    if path.isdir(dir):
        subdirs = (subdir for subdir in (path.join(dir, name) for name in listdir(dir)) if path.isdir(subdir))
        for subdir in subdirs:
            m = EASYRSA_VERSION_PATTERN.fullmatch(path.basename(subdir))
            if m:
                yield (m.group(1), subdir)


def extract_release(release, dest):
    """Given a release object from the Github API, download and extract the .tgz archive"""
    for asset in release["assets"]:
        if asset["name"].endswith(".tgz"):
            download_url = asset["browser_download_url"]
            break
    else:
        raise ValueError("no .tgz asset in release")

    if not path.exists(dest):
        makedirs(dest)

    with requests.get(download_url, stream=True) as resp:
        resp.raise_for_status()
        tarball = tarfile.open(fileobj=io.BytesIO(resp.content), mode="r:gz")
        tarball.extractall(path=dest)


def obtain_easyrsa(update=True):
    """Returns the path to the default EasyRSA binary after checking for,
    and possibly installing, the latest version"""
    installed = tuple(easyrsa_installations(tools_dir))
    latest_install = max([(str(v[0]), str(v[1])) for v in installed]) if installed else ("", "")

    if update:
        try:
            latest_release = easyrsa_release(EASYRSA_TAG)
            version_matches = EASYRSA_VERSION_PATTERN.fullmatch(latest_release["tag_name"])
            if not version_matches:
                latest_version = ""
            else:
                latest_version = str(version_matches.group(1))

            if latest_install is None or latest_version > latest_install[0]:
                extract_release(latest_release, tools_dir)
                latest_install = max(easyrsa_installations(tools_dir))
                logger.info("Installed EasyRSA %s", latest_version)
        except OSError:
            logger.warning("Failed to update EasyRSA")

    if latest_install is not None:
        return path.join(latest_install[1], "easyrsa")
    else:
        return None


def apply_defaults(config, defaults):
    # Expand the wildcard
    # Wildcard only makes sense when the value is a dict
    if wildcard in defaults:
        default = defaults[wildcard]
        defaults.update({k: default for k in config if k not in defaults})
        defaults.pop(wildcard)

    for key, default in defaults.items():
        # Handle the case where the key is not in config
        if key not in config:
            config[key] = default

        # Recurisly apply defaults to found dicts if the default is a dict
        elif isinstance(default, dict) and isinstance(config[key], dict):
            apply_defaults(config[key], default)


def read_config(filename):
    with open(filename, "r") as config_file:
        config = yaml.safe_load(config_file)

    logger.debug("Read from file: %s", config)
    apply_defaults(config, defaults)

    registrar_settings = config["registrar"]
    if "commonname" not in registrar_settings:
        registrar_settings["commonname"] = append_domain("registrar", config["domain"])

    for chal_name, chal_settings in config["challenges"].items():
        if "commonname" not in chal_settings:
            chal_settings["commonname"] = append_domain(chal_name, config["domain"])

        if "files" not in chal_settings:
            chal_settings["files"] = [path.join(chal_name, "docker-compose.yml")]

        # Backwards compatibility for clients before ifconfig_push was replaced with ifconfig.
        if "ifconfig_push" in chal_settings and chal_settings["ifconfig"] is None:
            logger.warning("Setting ifconfig_push is deprectaed. Please use ifconfig instead.")
            chal_settings["ifconfig"] = chal_settings["ifconfig_push"]
            del chal_settings["ifconfig_push"]

    logger.debug("Modified: %s", config)

    return config


def parse_args():
    parser = argparse.ArgumentParser(
        description="Parse the Naumachia config file and set up the environment",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--verbosity",
        "-v",
        metavar="LEVEL",
        default="info",
        choices=("critical", "error", "warning", "info", "debug"),
        help="logging level to use",
    )
    parser.add_argument(
        "--config",
        metavar="PATH",
        default=path.join(script_dir, "config.yml"),
        help="path to Naumachia config file",
    )
    parser.add_argument(
        "--templates",
        metavar="PATH",
        default=path.join(script_dir, "templates"),
        help="path to the configuration templates",
    )
    parser.add_argument(
        "--registrar_certs",
        metavar="PATH",
        default=path.join(script_dir, "registrar/certs"),
        help="path to the issued certs for registrar TLS",
    )
    parser.add_argument(
        "--compose",
        metavar="PATH",
        default=path.join(script_dir, "docker-compose.yml"),
        help="path to the rendered docker-compose output",
    )
    parser.add_argument(
        "--ovpn_configs",
        metavar="PATH",
        default=path.join(script_dir, "openvpn", "config"),
        help="path to openvpn configurations",
    )
    parser.add_argument(
        "--easyrsa",
        metavar="PATH",
        default=None,
        help="location of easyrsa executable. If the path does not exist, easyrsa will be installed",
    )

    return parser.parse_args()


def init_pki(easyrsa, directory, cn):
    easyrsa = path.abspath(easyrsa)
    debug = logger.isEnabledFor(logging.DEBUG)
    common_args = {
        "check": True,
        "cwd": directory,
        "stdout": subprocess.PIPE if not debug else None,
        "stderr": subprocess.PIPE if not debug else None,
        "universal_newlines": True,
    }

    try:
        logger.info("Initializing public key infrastructure (PKI)")
        subprocess.run([easyrsa, "init-pki"], **common_args)
        logger.info("Building certificiate authority (CA)")
        subprocess.run([easyrsa, "build-ca", "nopass"], input=f"ca.{cn}\n", **common_args)
        logger.info("Generating Diffie-Hellman (DH) parameters")
        subprocess.run([easyrsa, "gen-dh"], **common_args)
        logger.info("Building server certificiate")
        subprocess.run([easyrsa, "build-server-full", cn, "nopass"], **common_args)
    except subprocess.CalledProcessError as e:
        logger.error(f"Command '{e.cmd}' failed with exit code {e.returncode}")
        if e.output:
            logger.error(e.output)


def _render(tpl_path, context):
    dirname, filename = path.split(tpl_path)
    return (
        jinja2.Environment(loader=jinja2.FileSystemLoader(dirname or "./"))
        .get_template(filename)
        .render(context)
    )


def render(tpl_path, dst_path, context):
    with open(dst_path, "w") as f:
        f.write(_render(tpl_path, context))
    logger.info(f"Rendered {dst_path} from {tpl_path} ")


def rendertmp(tpl_path, context):
    f = tempfile.NamedTemporaryFile(mode="w+")
    f.write(_render(tpl_path, context))
    f.flush()
    return f


def append_domain(name, domain):
    if domain:
        return ".".join((name, domain))
    else:
        return name


def gen_configs_ovpn(directory, domainname, port, proto):
    ovpn_env = open(directory + "/ovpn_env.sh", "x")
    ovpn_env.write(f"""declare -x OVPN_AUTH=
declare -x OVPN_CIPHER=
declare -x OVPN_CLIENT_TO_CLIENT=
declare -x OVPN_CN={domainname}
declare -x OVPN_COMP_LZO=0
declare -x OVPN_DEFROUTE=1
declare -x OVPN_DEVICE=tun
declare -x OVPN_DEVICEN=0
declare -x OVPN_DISABLE_PUSH_BLOCK_DNS=0
declare -x OVPN_DNS=1
declare -x OVPN_DNS_SERVERS=([0]="8.8.8.8" [1]="8.8.4.4")
declare -x OVPN_ENV=/etc/openvpn/ovpn_env.sh
declare -x OVPN_EXTRA_CLIENT_CONFIG=()
declare -x OVPN_EXTRA_SERVER_CONFIG=()
declare -x OVPN_FRAGMENT=
declare -x OVPN_KEEPALIVE='10 60'
declare -x OVPN_MTU=
declare -x OVPN_NAT=0
declare -x OVPN_PORT={port}
declare -x OVPN_PROTO={proto}
declare -x OVPN_PUSH=()
declare -x OVPN_ROUTES=([0]="192.168.254.0/24")
declare -x OVPN_SERVER=192.168.255.0/24
declare -x OVPN_SERVER_URL={proto}://{domainname}:{port}
declare -x OVPN_TLS_CIPHER=
""")
    openvpn_conf = open(directory + "/openvpn.conf", "x")
    openvpn_conf.write(f"""server 192.168.255.0 255.255.255.0
verb 3
key /etc/openvpn/pki/private/{domainname}.key
ca /etc/openvpn/pki/ca.crt
cert /etc/openvpn/pki/issued/{domainname}.crt
dh /etc/openvpn/pki/dh.pem
# commented out for testing purposes
tls-auth /etc/openvpn/pki/ta.key
key-direction 0
keepalive 10 60
persist-key
persist-tun

proto {proto}
# Rely on Docker to do port mapping, internally always 1194
port 1194
dev tun0
status /tmp/openvpn-status.log

user nobody
group nogroup
comp-lzo no

### Route Configurations Below
route 192.168.254.0 255.255.255.0

### Push Configurations Below
push "block-outside-dns"
push "dhcp-option DNS 8.8.8.8"
push "dhcp-option DNS 8.8.4.4"
push "comp-lzo no"
""")
    up_sh = open(directory + "/up.sh", "x")
    up_sh.write("""#!/bin/sh
# Copyright (c) 2006-2007 Gentoo Foundation
# Distributed under the terms of the GNU General Public License v2
# Contributed by Roy Marples (uberlord@gentoo.org)

# Setup our resolv.conf
# Vitally important that we use the domain entry in resolv.conf so we
# can setup the nameservers are for the domain ONLY in resolvconf if
# we're using a decent dns cache/forwarder like dnsmasq and NOT nscd/libc.
# nscd/libc users will get the VPN nameservers before their other ones
# and will use the first one that responds - maybe the LAN ones?
# non resolvconf users just the the VPN resolv.conf

# FIXME:- if we have >1 domain, then we have to use search :/
# We need to add a flag to resolvconf to say
# "these nameservers should only be used for the listed search domains
#  if other global nameservers are present on other interfaces"
# This however, will break compatibility with Debians resolvconf
# A possible workaround would be to just list multiple domain lines
# and try and let resolvconf handle it

if [ "${PEER_DNS}" != "no" ]; then
	NS=
	DOMAIN=
	SEARCH=
	i=1
	while true ; do
		eval opt=\\$foreign_option_${i}
		[ -z "${opt}" ] && break
		if [ "${opt}" != "${opt#dhcp-option DOMAIN *}" ] ; then
			if [ -z "${DOMAIN}" ] ; then
				DOMAIN="${opt#dhcp-option DOMAIN *}"
			else
				SEARCH="${SEARCH}${SEARCH:+ }${opt#dhcp-option DOMAIN *}"
			fi
		elif [ "${opt}" != "${opt#dhcp-option DNS *}" ] ; then
			NS="${NS}nameserver ${opt#dhcp-option DNS *}\\n"
		fi
		i=$((${i} + 1))
	done

	if [ -n "${NS}" ] ; then
		DNS="# Generated by openvpn for interface ${dev}\\n"
		if [ -n "${SEARCH}" ] ; then
			DNS="${DNS}search ${DOMAIN} ${SEARCH}\\n"
		elif [ -n "${DOMAIN}" ]; then
			DNS="${DNS}domain ${DOMAIN}\\n"
		fi
		DNS="${DNS}${NS}"
		if [ -x /sbin/resolvconf ] ; then
			printf "${DNS}" | /sbin/resolvconf -a "${dev}"
		else
			# Preserve the existing resolv.conf
			if [ -e /etc/resolv.conf ] ; then
				cp /etc/resolv.conf /etc/resolv.conf-"${dev}".sv
			fi
			printf "${DNS}" > /etc/resolv.conf
			chmod 644 /etc/resolv.conf
		fi
	fi
fi

# Below section is Gentoo specific
# Quick summary - our init scripts are re-entrant and set the RC_SVCNAME env var
# as we could have >1 openvpn service

if [ -n "${RC_SVCNAME}" ]; then
	# If we have a service specific script, run this now
	if [ -x /etc/openvpn/"${RC_SVCNAME}"-up.sh ] ; then
		/etc/openvpn/"${RC_SVCNAME}"-up.sh "$@"
	fi

	# Re-enter the init script to start any dependant services
	if ! /etc/init.d/"${RC_SVCNAME}" --quiet status ; then
		export IN_BACKGROUND=true
		/etc/init.d/${RC_SVCNAME} --quiet start
	fi
fi

exit 0

# vim: ts=4 :
""")
    down_sh = open(directory + "/down.sh", "x")
    down_sh.write("""#!/bin/sh
# Copyright (c) 2006-2007 Gentoo Foundation
# Distributed under the terms of the GNU General Public License v2
# Contributed by Roy Marples (uberlord@gentoo.org)

# If we have a service specific script, run this now
if [ -x /etc/openvpn/"${RC_SVCNAME}"-down.sh ] ; then
	/etc/openvpn/"${RC_SVCNAME}"-down.sh "$@"
fi

# Restore resolv.conf to how it was
if [ "${PEER_DNS}" != "no" ]; then
	if [ -x /sbin/resolvconf ] ; then
		/sbin/resolvconf -d "${dev}"
	elif [ -e /etc/resolv.conf-"${dev}".sv ] ; then
		# Important that we cat instead of move incase resolv.conf is
		# a symlink and not an actual file
		cat /etc/resolv.conf-"${dev}".sv > /etc/resolv.conf
		rm -f /etc/resolv.conf-"${dev}".sv
	fi
fi

if [ -n "${RC_SVCNAME}" ]; then
	# Re-enter the init script to start any dependant services
	if /etc/init.d/"${RC_SVCNAME}" --quiet status ; then
		export IN_BACKGROUND=true
		/etc/init.d/"${RC_SVCNAME}" --quiet stop
	fi
fi

exit 0

# vim: ts=4 :

""")


def gen_ta_key(directory):
    pkidirectory = directory + "/pki"
    logger.debug("running openvpn --genkey --secret ta.key in " + pkidirectory)
    subprocess.run("/usr/sbin/openvpn --genkey --secret ta.key", cwd=pkidirectory, shell=True)


def gen_team(teamname, domainname, port, protocol, certdirlocation, certdirlocationContainer):
    try:
        # Cert Generation
        # print("=1", end="")
        teamdirContainer = certdirlocationContainer + teamname
        logger.debug("=2")
        makedirs(teamdirContainer)
        logger.debug("=3")
        easyrsa = obtain_easyrsa()
        logger.debug("=4")
        init_pki(easyrsa, teamdirContainer, domainname)
        logger.debug("=5")
        gen_configs_ovpn(teamdirContainer, domainname, port, protocol)
        logger.debug("=6")
        gen_ta_key(teamdirContainer)
        logger.debug("=7")
        # namespace creation
        return 0
    except Exception as e:
        logger.error("failed to create team " + teamname + " VPN directory: " + str(e))
        raise e


def del_team(teamname, certdirlocationContainer):
    try:
        logger.debug("called del_team function")
        teamdirContainer = certdirlocationContainer + teamname
        logger.debug("about to delete team " + teamname + " VPN directory")
        rmtree(teamdirContainer)
        logger.debug("deleted team " + teamname + " VPN directory")
    except Exception as e:
        logger.error("failed to delete container directory for team " + teamname + ": " + str(e))
