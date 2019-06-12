__author__ = 'eliagenini'

import http.client
import json
import sys

try:
    import config as config
except ImportError:
    print('Can\'t find any config.py!')
    sys.exit(-1)

hostname = config.config["plex"].get("hostname") + ':' + config.config["plex"].get("port")
token = config.config["plex"].get("token")
tuner = config.config["plex"].get("tuner")

conn = http.client.HTTPSConnection(host=hostname)

payload = json.dumps({'X-Plex-Token': token})

conn.request(method="POST", url="/livetv/dvrs/" + tuner + "/reloadGuide", body=payload)

res = conn.getresponse()
data = res.read()

if res.status == 200:
    print(" Refreshing EPG")
else:
    print(" Error ")
