import untangle
import os

def getconfig(attribute):
    try:
        #if we are deployed in production, use the environment variable
        attr = os.environ[attribute]
    except:
        #if not, use the config file in the local store
        config = untangle.parse('config.xml')
        attr = config.root.CampDetails[attribute]

    return attr