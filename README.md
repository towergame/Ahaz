# ahaz_cicd
ahaz cicd (legacy name) - supports multi container tasks with custom network rules and environment variables.

#SETUP
all env vars are located in docker-compose.yaml

`CERT_DIR_HOST`= directory where users/teams vpn configs will be stored on the ahaz host machine

`CERT_DIR_CONTAINER`= directory within the VPN container where the certificates will be located
`DB_IP` = IP address of ahaz challenge/task db it contains templates for challenges,pods,pod networkpolicies, env vars etc. is used for starting challenges within ahaz
`DB_DBNAME`,`DB_USERNAME`,`DB_PASSWORD` used for connecting to said db

`PUBLIC_DOMAINNAME` = domain with or without subdomain that can be used for obtaining the IP address of the system running ahaz, will be written in .ovpn configs served to users

`K8S_IP_RANGE` = used for IP route in .ovpn files, should be matching with the freely used IP range in your cluster or basicly, the IPs of pods started by ahaz.

`VERBOSE` = "True" or "false" as a string, not as boolean, useful for when first setting up the ahaz, basicly shows random print statements of ahaz running functions. errors will still be printed, and some info, like registration of teams and registration of users will still be printed to terminal running the ahaz through docker-compose. 