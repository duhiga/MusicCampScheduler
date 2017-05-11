import untangle
import os
from flask import render_template, jsonify

def getconfig(attribute):
    try:
        #if we are deployed in production, use the environment variable
        attr = os.environ[attribute]
    except:
        #if not, use the config file in the local store
        config = untangle.parse('config.xml')
        attr = config.root.CampDetails[attribute]
    return attr

#sets up debugging
def log(string):
    if int(getconfig('Debug')) == 1:
        print(string)

#shows an error page
def errorpage(thisuser,message):
    return render_template('errorpage.html', \
                                        thisuser=thisuser, \
                                        campname=getconfig('Name'), favicon=getconfig('Favicon_URL'), instrumentlist=getconfig('Instruments').split(","), supportemailaddress=getconfig('SupportEmailAddress'), \
                                        errormessage = message
                                        )