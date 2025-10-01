import pymysql
from os import environ

verbose=environ.get("VERBOSE","True").lower() in ('true', '1', 't')

#serverIP="10.13.0.3"
#databasename="ahaz"
#user="dbeaver"
#password="dbeaver"

serverIP=environ.get("DB_IP","10.13.0.3")
databasename=environ.get("DB_DBNAME","ahaz")
user=environ.get("DB_USERNAME","dbeaver")
password=environ.get("DB_PASSWORD","dbeaver")
k8s_ip_range=environ.get("K8S_IP_RANGE","10.42.0.0 255.255.0.0")
#print("testtext")
#print(serverIP)
#print(databasename)
#print(user)
#print(password)


def cicd_insert_challenge(name,ctfd_desc,ctfd_score,ctfd_type):
    try:
        conn = pymysql.connect(host=serverIP,port=3306,user=user,passwd=password,database=databasename)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO challenges(name,ctfd_desc,ctfd_score,ctfd_type) VALUES ('"+name+"','"+ctfd_desc+"',"+str(ctfd_score)+",'"+ctfd_type+"');")
        conn.commit()
        conn.close()
        return "success"
    except Exception as e:
        print(e)
        return e
def cicd_insert_pod(name,k8s_name,image,limits_ram,limits_cpu,visible_to_user):
    try:
        conn = pymysql.connect(host=serverIP,port=3306,user=user,passwd=password,database=databasename)
        cursor = conn.cursor()
        if visible_to_user:
            visible_to_user="TRUE"
        else:
            visible_to_user="FALSE"
        cursor.execute("INSERT INTO pods(name,k8s_name,image,ram,cpu,visible_to_user) VALUES ('"+name+"','"+k8s_name+"','"+image+"','"+limits_ram+"',"+str(limits_cpu)+","+visible_to_user+");")
        conn.commit()
        conn.close()
        return "success"
    except Exception as e:
        print(e)
        return e
def cicd_insert_net_rules(name,netname,k8s_name):
    try:
        conn = pymysql.connect(host=serverIP,port=3306,user=user,passwd=password,database=databasename)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO net_rules(name,netname,k8s_name) VALUES ('"+name+"','"+netname+"','"+k8s_name+"');")
        conn.commit()
        conn.close()
        return "success"
    except Exception as e:
        print(e)
        return e
def cicd_insert_env_vars(name,k8s_name,env_var_name,env_var_value):
    try:
        conn = pymysql.connect(host=serverIP,port=3306,user=user,passwd=password,database=databasename)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO env_vars(name,k8s_name,env_var_name,env_var_value) VALUES ('"+name+"','"+k8s_name+"','"+env_var_name+"','"+env_var_value+"');")
        conn.commit()
        conn.close()
        return "success"
    except Exception as e:
        print(e)
        return e

def cicd_get_challenges_from_db():
    try:
        conn = pymysql.connect(host=serverIP,port=3306,user=user,passwd=password,database=databasename)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM challenges;")
        rows = cursor.fetchall()
        json="["
        for i in rows:
            json+='{"challengename":"'+i[0]+'"},'
        json=json[:len(json)-1]+"]"
        return json
    except Exception as e:
        print(e)
        return e
def cicd_get_challenge(name):
    try:
        conn = pymysql.connect(host=serverIP,port=3306,user=user,passwd=password,database=databasename)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM challenges WHERE name='"+name+"';")
        rows = cursor.fetchall()
        if(verbose):print(rows)
        conn.close()
        return rows[0]
    except Exception as e:
        print(e)
        return e
def cicd_get_pods(name):
    conn = pymysql.connect(host=serverIP,port=3306,user=user,passwd=password,database=databasename)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM pods WHERE name='"+str(name)+"';")
    rows = cursor.fetchall()
    try:
        return rows
    except Exception as e:
        print(e)
        return "null"
def cicd_get_env_vars(k8s_name):
    conn = pymysql.connect(host=serverIP,port=3306,user=user,passwd=password,database=databasename)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM env_vars WHERE k8s_name='"+str(k8s_name)+"';")
    rows = cursor.fetchall()
    env_vars=[]
    for i in rows:
        env_vars.append({"name":str(i[2]).upper(),"value":i[3]})
        print(i)
    try:
        return env_vars
    except Exception as e:
        print(e)
        return "null" 
def cicd_get_k8s_name_networks(k8s_name):
    conn = pymysql.connect(host=serverIP,port=3306,user=user,passwd=password,database=databasename)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM net_rules WHERE k8s_name='"+str(k8s_name)+"';")
    rows = cursor.fetchall()
    netnames=[]
    for i in rows:
        netnames.append(i[1])
    try:
        return netnames
    except Exception as e:
        print(e)
        return "null"    
def cicd_get_unique_networks(challengename):
    conn = pymysql.connect(host=serverIP,port=3306,user=user,passwd=password,database=databasename)
    cursor = conn.cursor()
    cursor.execute("SELECT netname FROM net_rules WHERE name = '"+challengename+"' ;")
    rows = cursor.fetchall()
    return list(set(rows)) #remove duplicates
def cicd_get_pods_in_network(challengename, netname):
    conn = pymysql.connect(host=serverIP,port=3306,user=user,passwd=password,database=databasename)
    cursor = conn.cursor()
    cursor.execute("SELECT k8s_name FROM net_rules WHERE netname = '"+netname+"' AND name = '"+challengename+"';")
    rows = cursor.fetchall()
    #print(rows)
    return rows
def cicd_get_challenge_from_k8s_name(k8s_name):
    conn = pymysql.connect(host=serverIP,port=3306,user=user,passwd=password,database=databasename)
    cursor = conn.cursor()
    cursor.execute('SELECT name FROM pods WHERE k8s_name="'+k8s_name+'";')
    rows = cursor.fetchall()
    return str(rows[0][0])
#def cicd_get_pods_namespace

#carried over functions for user creation and so on
def sanitizeInput(input):
    print("should sanitize something")
def delete_db():
    conn = pymysql.connect(host=serverIP,port=3306,user=user,passwd=password,database=databasename)
    cursor = conn.cursor()
    try:
        cursor.execute("DROP table teams")
        cursor.execute("DROP table vpn_map")
        cursor.execute("DROP table vpn_storage")    
    except:
        print("no db to be deleted")
    
def create_db():
    conn = pymysql.connect(host=serverIP,port=3306,user=user,passwd=password,database=databasename)
    cursor = conn.cursor()
    cursor.execute("CREATE table teams(name varchar(255), teamID INT NOT NULL AUTO_INCREMENT,PRIMARY KEY (teamID));")
    cursor.execute("CREATE table vpn_map(teamID int, port int);")
    cursor.execute("CREATE table vpn_storage(teamID int,username varchar(255),config varchar(8000));")

    cursor.execute("CREATE table challenges(name varchar(255),ctfd_desc varchar(1024),ctfd_score int,ctfd_type varchar(255));")
    cursor.execute("CREATE table pods(name varchar(255),k8s_name varchar(50),image varchar(1024),ram varchar(32),cpu int, visible_to_user bool);")
    cursor.execute("CREATE table net_rules(name varchar(255),netname varchar(255),k8s_name varchar(50));")
    cursor.execute("CREATE table env_vars(name varchar(255),k8s_name varchar(50),env_var_name varchar(1024),env_var_value varchar(1024));")
    

def insert_image_into_db(repo,name,tag,challengename):
    conn = pymysql.connect(host=serverIP,port=3306,user=user,passwd=password,database=databasename)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO image(repo,name,tag,challengename) VALUES ('"+repo+"','"+name+"','"+tag+"','"+challengename+"');")
    conn.commit()    
def get_image_from_db_json(challengename):
    conn = pymysql.connect(host=serverIP,port=3306,user=user,passwd=password,database=databasename)
    cursor = conn.cursor()
    cursor.execute('SELECT repo,name,tag,challengename FROM image WHERE challengename="'+challengename+'"')
    #conn.commit() 
    rows = cursor.fetchall()
    print(rows)
    json="["
    for i in rows:
        json+='{"repo":"'+i[0]+'","name":"'+i[1]+'","tag":"'+i[2]+'","challengename":"'+i[3]+'"},'
    json=json[:len(json)-1]+"]"
    return json
def get_image_from_db(challengename):
    conn = pymysql.connect(host=serverIP,port=3306,user=user,passwd=password,database=databasename)
    cursor = conn.cursor()
    cursor.execute('SELECT repo,name,tag,challengename FROM image WHERE challengename="'+challengename+'"')
    #conn.commit() 
    rows = cursor.fetchall()
    return rows    
def get_images_from_db():
    conn = pymysql.connect(host=serverIP,port=3306,user=user,passwd=password,database=databasename)
    cursor = conn.cursor()
    cursor.execute('SELECT challengename FROM image')
    #conn.commit() 
    rows = cursor.fetchall()
    print(rows)
    json="["
    for i in rows:
        json+='{"challengename":"'+i[0]+'"},'
    json=json[:len(json)-1]+"]"
    return json
    
def insert_team_into_db(teamname):
    if (verbose):print("connecting to db")
    conn = pymysql.connect(host=serverIP,port=3306,user=user,passwd=password,database=databasename)
    cursor = conn.cursor()
    if (verbose):print("inserting data in db")
    #implement sanitization here
    if get_team_id(teamname)!="null":
        return "team with that name alread exists in db"
    cursor.execute("INSERT INTO teams(name) VALUES ('"+teamname+"');")
    print("INSERT INTO teams(name) VALUES ('"+teamname+"');")
    conn.commit()
def insert_vpn_port_into_db(teamname,port):
    conn = pymysql.connect(host=serverIP,port=3306,user=user,passwd=password,database=databasename)
    cursor = conn.cursor()
    teamid=get_team_id(teamname)
    if get_port_team(port) == "null":
        if get_team_port(teamname) == "null":
            cursor.execute("INSERT INTO vpn_map(port,teamid) VALUES ("+str(port)+","+str(teamid)+")")
            conn.commit()
        else:
            return "team already has port allocated to it"
    else:
        return "port "+str(port)+" is already allocated" 
def insert_user_vpn_config(teamname, username, config):
    conn = pymysql.connect(host=serverIP,port=3306,user=user,passwd=password,database=databasename)
    cursor = conn.cursor()
    teamid=get_team_id(teamname)
    config=str(config).replace('\\n','\n')
    config=config[2:]
    config=config[:len(config)-2]
    config=config.replace("<key>","route-nopull\nroute "+k8s_ip_range+"\n\n<key>")#add IP route to the config
    config=config.replace("redirect-gateway def1","")   #remove the rule that replaces all routes with VPN
    config=config+"\ncomp-lzo yes\nallow-compression yes"
    cursor.execute("INSERT INTO vpn_storage(teamID,username,config) VALUES ("+str(teamid)+",'"+username+"','"+config+"')");
    conn.commit()

def get_team_id(teamname):
    conn = pymysql.connect(host=serverIP,port=3306,user=user,passwd=password,database=databasename)
    cursor = conn.cursor()
    #implement sanitization here
    cursor.execute("SELECT (teamID) FROM teams WHERE name='"+teamname+"'")
    rows = cursor.fetchall()
    print(rows)
    try:
        print(rows[0][0])
        return rows[0][0]
    except:
        return "null"    
def get_team_port(teamname):
    conn = pymysql.connect(host=serverIP,port=3306,user=user,passwd=password,database=databasename)
    cursor = conn.cursor()
    teamID = get_team_id(teamname)
    cursor.execute("SELECT (port) FROM vpn_map WHERE teamID='"+str(teamID)+"'")
    rows = cursor.fetchall()
    print(rows)
    try:
        print(rows[0][0])
        return rows[0][0]
    except:
        return "null"
def get_port_team(port):
    conn = pymysql.connect(host=serverIP,port=3306,user=user,passwd=password,database=databasename)
    cursor = conn.cursor()
    cursor.execute("SELECT (teamID) FROM vpn_map WHERE port="+str(port)+"")
    rows = cursor.fetchall()
    print(rows)
    try:
        print(rows[0][0])
        return rows[0][0]
    except:
        return "null"    
def get_user_vpn_config(teamname,username):
    teamID = get_team_id(teamname)
    conn = pymysql.connect(host=serverIP,port=3306,user=user,passwd=password,database=databasename)
    cursor = conn.cursor()
    cursor.execute("SELECT (config) FROM vpn_storage WHERE teamID="+str(teamID)+" and username='"+username+"'")
    rows = cursor.fetchall()
    print(rows)
    try:
        print(rows[0][0])
        return rows[0][0]
    except:
        return "null"  
def get_last_port():
    conn = pymysql.connect(host=serverIP,port=3306,user=user,passwd=password,database=databasename)
    cursor = conn.cursor()
    cursor.execute("SELECT (port) FROM vpn_map ORDER BY port DESC")
    rows = cursor.fetchall()
    print(rows)
    try:
        print(rows[0][0])
        return rows[0][0]
    except:
        return 30100
  
    
def printdb():
    conn = pymysql.connect(host=serverIP,port=3306,user=user,passwd=password,database=databasename)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM teams") 
    rows = cursor.fetchall()
    print(rows)
    cursor.execute("SELECT * FROM vpn_map") 
    rows = cursor.fetchall()
    print(rows)

    