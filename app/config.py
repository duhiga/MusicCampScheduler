import untangle
import os
from flask import render_template, jsonify
import datetime

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

#returns today plus or minus a delta number of days
def today(delta=None):
    if delta is not None:
        return datetime.datetime.combine(datetime.date.today(), datetime.time.min) + datetime.timedelta(days=delta)
    else:
        return datetime.datetime.combine(datetime.date.today(), datetime.time.min)

#returns now plus or minus a delta number of days
def now(delta=None):
    if delta is not None:
        return datetime.datetime.now() + datetime.timedelta(days=delta)
    else:
        return datetime.datetime.now()

#shows an error page
def errorpage(thisuser,message):
    return render_template('errorpage.html', \
            thisuser=thisuser, \
            campname=getconfig('Name'), 
            favicon=getconfig('Favicon_URL'), 
            supportemailaddress=getconfig('SupportEmailAddress'), \
            errormessage = message
            )