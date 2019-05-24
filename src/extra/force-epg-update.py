__author__ = 'eliagenini'

import urllib.request as urllib
import sys

try:
    import config as config
except ImportError:
    print('Can\'t find any config.py!')
    sys.exit(-1)


hostname = config.config["plex"].get("hostname") + ':' + config.config["plex"].get("port")
token = config.config["plex"].get("token")
tuner = config.config["plex"].get("tuner")

URL = hostname + "/livetv/dvrs/" + tuner + "/reloadGuide"

request = urllib.Request(URL, data={'X-Plex-Token': token})
response = urllib.urlopen(request)

if response.status_code == 200:
    print(" Refreshing EPG")
else:
    print(" Error Returned : " + str(response.status_code))