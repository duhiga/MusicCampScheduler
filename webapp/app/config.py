import untangle
import os
import sys

def getconfig(attribute):
    try:
        #if we are deployed in production, use the environment variable
        attr = os.environ[attribute]
    except:
        #if not, use the config file in the local store
        config = untangle.parse("config/config.xml")
        attr = config.root.CampDetails[attribute]
    return attr

#sets up logging
def log(string):
    print(string)
    #sys.stdout.write(string + '\n')

def debuglog(string):
    if int(getconfig('Debug')) == 1:
        print(string)