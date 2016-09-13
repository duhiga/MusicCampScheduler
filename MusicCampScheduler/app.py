"""

This app runs the music camp scheduler site the target audience for this site is around 100 people for a camp around 1 week
long. The intended model for the music camp is that people are allocated into groups like orchestras, bands, quartets, etc
over several periods in a day. People can mark themselves as "absent" at least one day in advance and will not be allocated 
to groups in the session. Once running, the website must be maintained by an adminstrator, and conductors to confirm groups.

Before use, you need to open up config.xml and point it to a SQL database, and configure any other needed information. Debug
levels are 0=none, 1=debug, 2=verbose.

"""


from flask import Flask, render_template, redirect, jsonify, make_response, json
import scss
import sys
import types
import time
import datetime
import re
import json
import untangle
import uuid
import sqlalchemy
#import DBSetup
from DBSetup import *
from SQL import *
from json import JSONEncoder, JSONDecoder
from sqlalchemy import *

# Make the WSGI interface available at the top level so wfastcgi can get it.
app = Flask(__name__)
config = untangle.parse('config.xml')
app.secret_key = config.root.CampDetails['SecretKey']
wsgi_app = app.wsgi_app
Session = sessionmaker(bind=engine)

#sets up debugging
debug = config.root.Application['Debug']
def log1(string):
    if debug >= 1:
        print(string)
def log2(string):
    if debug >= 2:
        print(string)
print('Debug level set to %s' % debug)

log2('Python version: %s' % sys.version)

#checks a user entry for bad characters.  Users are only allowed to submit inputs in their URLs with letters and numbers and dashes.
def check(string):
    log1('checking input %s' % string)
    if re.match("^[a-zA-Z0-9-]*$",string):
        log1('%s passes the check' % string)
        tf = True
    else:
        log1('%s fails the check' % string)
        tf = False
    return tf

from sqlalchemy.ext.declarative import DeclarativeMeta
class AlchemyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj.__class__, DeclarativeMeta):
            # an SQLAlchemy class
            fields = {}
            for field in [x for x in dir(obj) if not x.startswith('_') and x != 'metadata']:
                data = obj.__getattribute__(field)
                try:
                    json.dumps(data) # this will fail on non-encodable values, like other classes
                    fields[field] = data
                except TypeError:
                    fields[field] = None
            # a json-encodable dict
            return fields

        return json.JSONEncoder.default(self, obj)


#Looks up the amount of times a user has participated in an "ismusical" group during the camp
def playcount(session,userid):
    playcount = session.query(groupassignment).join(group).join(user).filter(user.userid == userid, group.ismusical == 1).count()
    return playcount

#gets a list of periods corresponding to the requested userid and date
def useridanddatetoperiods(session,userid,date):
    nextday = date + datetime.timedelta(days=1)
    #---------------   
    #the below two queries and 1 loop could be optimized with a single query, but I don't know exactly how to do embedded queries in sqlalchemy  
    #get this user's assigned periods today
    periods = []
    for p in session.query(period).filter(period.starttime > date, period.endtime < nextday).all():
        g = session.query(group.groupname, period.starttime, period.endtime, location.locationname, group.groupid, group.ismusical, \
                            group.iseveryone, period.periodid, period.periodname, groupassignment.instrument).\
                            join(period).join(groupassignment).join(user).outerjoin(instrument).outerjoin(location).filter(user.userid == userid,group.periodid == p.periodid).first()
        if g == None:
            periods.append(p)
        if g != None:
            periods.append(g)

    return periods

#looks up the whole list of players in a given periodID
def periodidtoplayerlist(session, periodid):
    playerlist = session.query(user.firstname, user.lastname, period.starttime, period.endtime, user.userid, groupassignment.instrument, group.groupname, location.locationname).\
                              outerjoin(groupassignment).outerjoin(group).outerjoin(period).outerjoin(location).\
                              filter(periodid == periodid).order_by(group.groupname,groupassignment.instrument)    
    log2(str(playerlist))
    return playerlist

#the root page isn't meant to be navigable.  It shows the user an error and
#tells them how to get to their user dashboard.
@app.route('/')
def rootpage():

    return render_template('index.html')

#upon the URL request in the form domain/user/<userid> the user receives their dashboard.  This updates every day with the groups they 
#are playing in.
@app.route('/user/<userid>/')
def dashboard(userid,inputdate='n'):
    if check(userid) and check(inputdate):
        log1('dashboard fetch requested for user %s' % userid)
        log1('date modifier is currently set to %s' % inputdate)
        session = Session()
        #gets the data associated with this user
        thisuser = session.query(user).filter(user.userid == userid).first()
        if thisuser is None:
            return ('Did not find user %s in database. You have entered an incorrect URL address.' % userid)       
        #find the number of times a user has played in groups in the past
        count = playcount(session, userid)
        #get impontant datetimes
        today = datetime.datetime.combine(datetime.date.today(), datetime.time.min) #get today's date
        #if the suer has submitted a date, convert it to a datetime and use it as the display date
        if inputdate != 'n': 
            displaydate = datetime.datetime.strptime(inputdate, '%Y-%m-%d')
        #if the user has not submitted a date and today is before the start of camp, use the first day of camp as the display date
        elif today < datetime.datetime.strptime(config.root.CampDetails['StartTime'], '%Y-%m-%d %H:%M'): 
            displaydate = datetime.datetime.strptime(config.root.CampDetails['StartTime'].split()[0], '%Y-%m-%d')
            log2(displaydate)
        #if today is after the start of camp, use today as the display date
        else:
            displaydate = today
        
        previousday = displaydate + datetime.timedelta(days=-1)
        nextday = displaydate + datetime.timedelta(days=1)
        periods = useridanddatetoperiods(session,userid,displaydate)
        session.close()
        return render_template('dashboard.html', \
                            user=thisuser, \
                            count=count, \
                            date=displaydate,\
                            periods=periods, \
                            previousday=datetime.datetime.strftime(previousday, '%Y-%m-%d'), \
                            nextday=datetime.datetime.strftime(nextday, '%Y-%m-%d'), \
                            today=today, \
                            weekday=datetime.datetime.strftime(displaydate, '%A'), \
                            campname=config.root.CampDetails['Name'], \
                            supportemailaddress=config.root.CampDetails['SupportEmailAddress'], \
                            )
        
    else:
        return 'You have submitted illegal characters in your URL. Any inputs must only contain letters, numbers and dashes.'

@app.route('/user/<userid>/date/<date>/')
def dashboardDateModifier(userid,date):
    return dashboard(userid,date)

#Makes a post query that marks a player adsent for a given period. This is triggered off the above (two) dashboard functions.
@app.route("/user/<userid>/period/<periodid>/absent/<command>/", methods=["POST"])
def mark_absent(userid,periodid,command):
    if check(userid) and check(periodid) and check(command):
        session = Session()
        #gets the data associated with this user
        thisuser = session.query(user).filter(user.userid == userid).first()
        if thisuser is None:
            return ('Did not find user %s in database. You have entered an incorrect URL address.' % userid)
        currentassignment = session.query(group.groupname, groupassignment.groupassignmentid).\
                        join(groupassignment).join(user).join(period).\
                        filter(period.periodid == periodid, user.userid == userid).first()
        log2('User is currently assigned to ' + str(currentassignment))
        #case if the user is not assigned to anything, and attempted to mark themselves as absent
        if currentassignment == None and command == 'confirm':
            log2('user is not assigned to anything and is requesting an absence')
            #get the groupid for the absent group associated with this period
            absentgroup = session.query(group.groupid).join(period).filter(group.groupname == 'absent', period.periodid == periodid).first()
            log2('found absent group %s' % absentgroup)
            #assign this person to the absent group
            try:
                session.add(groupassignment(userid = userid, groupid = absentgroup.groupid))
                session.commit()
                session.close()
                return 'Now user marked absent for periodid ' + periodid
            except Exception as ex:
                log1('failed to allocate user as absent for period %s with exception: %s' % (periodid,ex))
                session.rollback()
                session.close()
                return 'error'
        #case if the user is already marked absent and they tried to mark themselves as absent again
        if currentassignment != None:
            if currentassignment.groupname == 'absent' and command == 'confirm':
                session.close()
                return 'Already marked absent for period with id ' + periodid
            #case if the user is already marked absent and their tried to cancel their absent request
            elif currentassignment.groupname == 'absent' and command == 'cancel':            
                try:
                    session.delete(session.query(groupassignment).filter(groupassignment.groupassignmentid == currentassignment.groupassignmentid).first())
                    session.commit()
                    session.close()
                    return 'Removed absent request for ' + periodid
                except Exception as ex:
                    log1('failed to remove absent request for period %s with exception: %s' % (periodid,ex))
                    session.rollback()
                    session.close()
                    return 'error'
        #catch-all case. You'd get here if the adminsitrator was changing the back-end while the user was on their dashboard page
        else:
            session.close()
            return 'You are already assigned to a group for this period. You have NOT been marked absent. Talk to the adminsitrator to fix this.'
    else:
        return 'You have submitted illegal characters in your URL. Any inputs must only contain letters, numbers and dashes.'

#this route is linked to from the user's dashboard.  When they click on a group name, they are taken to a page showing all the people
#in that group, along with possible substitutes
@app.route('/user/<userid>/group/<groupid>/')
def groupdetails(userid,groupid):
    if check(userid) and check(groupid):
        log1('Group page requested by %s for groupID %s' % (userid,groupid))
        session = Session()
        #gets the data associated with this user
        thisuser = session.query(user).filter(user.userid == userid).first()
        if thisuser is None:
            return ('Did not find user %s in database. You have entered an incorrect URL address.' % userid)
        thisgroup = session.query(group, location.locationname).filter(group.groupid == groupid).join(location).first()
        thisperiod = session.query(period).filter(period.periodid == group.periodid).first()
        
        #gets the list of players playing in the given group
        players = session.query(user.firstname, user.lastname, groupassignment.instrument).join(groupassignment).join(group).\
                                filter(group.groupid == groupid).order_by(groupassignment.instrument).all()
        """
        #VERY unfinished. Need data to test this to continue.
        everyoneplayingquery = session.query(user.userid).join(groupassignment).join(group).join(period).filter(period.periodid == thisperiod.periodid)
        everyoneNOTplayingquery = session.query(user.userid).filter(~user.in_(everyoneplayingquery))

        #the below is probably junk
        substitutes = session.query(user.firstname, user.lastname, instrument.instrumentname).\
                                join(instrument).outerjoin(groupassignment).outerjoin(group).outerjoin(period).\
                                filter(period.periodid == thisperiod.periodid)
        """
        
        """
        data = sql(SELECT u.userid,u.firstname,u.lastname,ga.instrument,null,null,null FROM groupassignments ga INNER JOIN (
                                SELECT si.userid,si.instrument FROM instruments si WHERE NOT EXISTS (
                                    SELECT nu.userid FROM users nu
                                    INNER JOIN groupassignments nga ON nga.userid = nu.userid
                                    INNER JOIN groups ng ON nga.groupid = ng.groupid
                                    WHERE nu.userid = si.userid AND ng.periodid =  + g.periodid + )) n
                            ON ga.instrument = n.instrument
                            INNER JOIN users u ON n.userid = u.userid
                            WHERE ga.groupid =  + g.groupid)
        """
        
        session.close()
        return render_template('group.html', \
                            period=thisperiod, \
                            group=thisgroup, \
                            location=location, \
                            players=players, \
                            #substitutes=substitutes, \
                            user=thisuser \
                            )
    else:
        return 'You have submitted illegal characters in your URL. Any inputs must only contain letters, numbers and dashes.'

#UNFINISHED - still need to work on the form submission, and the group template autofill. Also greying out of buttons when it hits the limits
@app.route('/user/<userid>/grouprequest/')
def grouprequestpage(userid):
    if check(userid):
        session = Session()
        #gets the data associated with this user
        thisuser = session.query(user).filter(user.userid == userid).first()
        if thisuser is None:
            return ('Did not find user %s in database. You have entered an incorrect URL address.' % userid)
        thisuserinstruments = session.query(instrument.instrumentname).join(user).filter(user.userid == userid).all()
        grouptemplates = session.query(grouptemplate).all()
        grouptemplates = json.dumps(grouptemplates, cls=AlchemyEncoder)
        log2(grouptemplates)
        instruments = []
        instrumentlist = config.root.CampDetails['Instruments'].split(",")
        playersdump = session.query(user.userid,user.firstname,user.lastname,instrument.instrumentname,instrument.grade,instrument.isprimary).join(instrument).all()
        
        log2('Players dump is: %s' % playersdump)
        session.close()
        return render_template('grouprequest.html', \
                            thisuser=thisuser, \
                            thisuserinstruments=thisuserinstruments, \
                            playerlimit = config.root.CampDetails['SmallGroupPlayerLimit'], \
                            grouptemplates=grouptemplates, \
                            instrumentlist=instrumentlist, \
                            playersdump=playersdump, \
                            )
    else:
        return 'You have submitted illegal characters in your URL. Any inputs must only contain letters, numbers and dashes.'
    
#this page is the full report for any given period
@app.route('/user/<userid>/period/<periodid>/')
def periodpage(userid,periodid):
    if check(userid) and check(periodid):
        session = Session()
        #gets the data associated with this user
        thisuser = session.query(user).filter(user.userid == userid).first()
        if thisuser is None:
            return ('Did not find user %s in database. You have entered an incorrect URL address.' % userid)
        players = periodidtoplayerlist(session, periodid)        
        thisperiod = session.query(period).filter(period.periodid == periodid).first()
        session.close()
        return render_template('period.html', \
                            players=players, \
                            user=thisuser, \
                            period=thisperiod \
                            )
    else:
        return 'You have submitted illegal characters in your URL. Any inputs must only contain letters, numbers and dashes.'

@app.route('/new/user/<firstname>/<lastname>/<age>/<email>/<isannouncer>/<isconductor>/<isadmin>/')
def new_user(firstname,lastname,age,isannouncer,isconductor,isadmin):
    newuser = user(firstname=firstname, lastname=lastname, age=age, isannouncer=isannouncer, isconductor=isconductor, isadmin=isadmin)
    session = Session()
    session.add(newuser)
    session.commit()
    session.close()
    return 'user created'    

if __name__ == '__main__':
    app.run(debug=True, \
            host='0.0.0.0')