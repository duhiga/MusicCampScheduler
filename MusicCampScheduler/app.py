"""

This app runs the music camp scheduler site. The original target audience for this site is around 100 people for a camp around 1 week
long. The intended model for the music camp is that people are allocated into groups like orchestras, bands, quartets, etc
over several periods in a day. People can mark themselves as "absent" at least one day in advance and will not be allocated 
to groups in the session. Once running, the website must be maintained by an adminstrator, and conductors to confirm groups.

Before use, you need to open up config.xml and point it to a SQL database, and configure any other needed information.

"""

from flask import Flask, render_template, redirect, jsonify, make_response, json, request, url_for
from collections import namedtuple
import sys
import types
import time
import datetime
import re
import json
import untangle
import uuid
import sqlalchemy
from DBSetup import *
from sqlalchemy import *

# Make the WSGI interface available at the top level so wfastcgi can get it.
app = Flask(__name__)
config = untangle.parse('config.xml')
app.secret_key = config.root.CampDetails['SecretKey']
wsgi_app = app.wsgi_app
Session = sessionmaker(bind=engine)

#sets up debugging
debug = int(config.root.Application['Debug'])
def log1(string):
    if debug >= 1:
        print(string)
def log2(string):
    if debug >= 2:
        print(string)
print('Debug level set to %s' % debug)

log2('Python version: %s' % sys.version)

#Looks up the amount of times a user has participated in an "ismusical" group during the camp
def playcount(session,userid):
    playcount = session.query(groupassignment).join(group).join(user).outerjoin(period).\
        filter(user.userid == userid, group.ismusical == 1, period.endtime <= datetime.datetime.now()).count()
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

def getgroupname(g):
    instrumentlist = config.root.CampDetails['Instruments'].split(",")
    count = 0
    for i in instrumentlist:
        value = getattr(g, i)
        log2('Instrument %s is value %s' % (i, value))
        if value is not None:
            count = count + int(getattr(g, i))
    log2('Found %s instruments in group.' % value)
    if count == 1:
        name = 'Solo'
    elif count == 2:
        name = 'Duet'
    elif count == 3:
        name = 'Trio'
    elif count == 4:
        name = 'Quartet'
    elif count == 5:
        name = 'Quintet'
    elif count == 6:
        name = 'Sextet'
    elif count == 7:
        name = 'Septet'
    elif count == 8:
        name = 'Octet'
    else:
        name = 'Custom Group'
    return name

#the root page isn't meant to be navigable.  It shows the user an error and
#tells them how to get to their user dashboard.
@app.route('/')
def rootpage():
    return render_template('index.html')

#upon the URL request in the form domain/user/<userid> the user receives their dashboard.  This updates every day with the groups they 
#are playing in.
@app.route('/user/<userid>/')
def dashboard(userid,inputdate='n'):
    log1('dashboard fetch requested for user %s' % userid)
    log1('date modifier is currently set to %s' % inputdate)
    session = Session()
    #gets the data associated with this user
    thisuser = session.query(user).filter(user.userid == userid).first()
    if thisuser is None:
        return ('Did not find user in database. You have entered an incorrect URL address.')       
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

#When the user selects the "next day" and "previous day" links on their dashboard, it goes to this URL. this route redirects them back
#to the user dashboard with a date modifier.
@app.route('/user/<userid>/date/<date>/')
def dashboardDateModifier(userid,date):
    return dashboard(userid,date)

#Makes a post query that marks a player adsent for a given period. This is triggered off the above (two) dashboard functions.
@app.route("/user/<userid>/period/<periodid>/absent/<command>/", methods=["POST"])
def mark_absent(userid,periodid,command):
    session = Session()
    #gets the data associated with this user
    thisuser = session.query(user).filter(user.userid == userid).first()
    if thisuser is None:
        return ('Did not find user in database. You have entered an incorrect URL address.')
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
            return 'Now user marked absent for period'
        except Exception as ex:
            log1('failed to allocate user as absent for period %s with exception: %s' % (periodid,ex))
            session.rollback()
            session.close()
            return 'error'
    #case if the user is already marked absent and they tried to mark themselves as absent again
    if currentassignment != None:
        if currentassignment.groupname == 'absent' and command == 'confirm':
            session.close()
            return 'Already marked absent for period'
        #case if the user is already marked absent and their tried to cancel their absent request
        elif currentassignment.groupname == 'absent' and command == 'cancel':            
            try:
                session.delete(session.query(groupassignment).filter(groupassignment.groupassignmentid == currentassignment.groupassignmentid).first())
                session.commit()
                session.close()
                return 'Removed absent request for ' + periodid
            except Exception as ex:
                log1('failed to remove absent request for period with exception: %s' % ex)
                session.rollback()
                session.close()
                return 'error'
    #catch-all case. You'd get here if the adminsitrator was changing the back-end while the user was on their dashboard page
    else:
        session.close()
        return 'You are already assigned to a group for this period. You have NOT been marked absent. Talk to the adminsitrator to fix this.'

#this route is linked to from the user's dashboard.  When they click on a group name, they are taken to a page showing all the people
#in that group, along with possible substitutes
@app.route('/user/<userid>/group/<groupid>/')
def groupdetails(userid,groupid):
    log1('Group page requested by %s for groupID %s' % (userid,groupid))
    session = Session()
    #gets the data associated with this user
    thisuser = session.query(user).filter(user.userid == userid).first()
    if thisuser is None:
        return ('Did not find user in database. You have entered an incorrect URL address.')
    thisgroup = session.query(group.groupid, group.groupname, group.periodid, group.music, location.locationname).outerjoin(location).filter(group.groupid == groupid).first()
    if thisgroup is None:
        return ('Did not find group in database. You have entered an incorrect URL address.')
    thisperiod = session.query(period).filter(period.periodid == thisgroup.periodid).first()
        
    #gets the list of players playing in the given group
    players = session.query(user.firstname, user.lastname, groupassignment.instrument).join(groupassignment).join(group).\
                            filter(group.groupid == groupid).order_by(groupassignment.instrument).all()
    """
    #VERY unfinished. Need data to test this to continue.
    everyoneplayingquery = session.query(user.userid).join(groupassignment).join(group).join(period).filter(period.periodid == thisperiod.periodid)
    everyoneNOTplayingquery = session.query(user.userid).filter(~user.in_(everyoneplayingquery))
    """
        
    session.close()
    return render_template('group.html', \
                        period=thisperiod, \
                        campname=config.root.CampDetails['Name'], \
                        group=thisgroup, \
                        players=players, \
                        #substitutes=substitutes, \
                        user=thisuser \
                        )

#UNFINISHED - need to test the "UNTESTED" query, and handle the post properly (currently the post doesn't support conductors at all)
#Handlnes the group request page. If a user visits the page, it gives them a form to create a new group request. Pressing submit sends a post
#containing configuration data. Their group request is queued until an adminsitrator approves it and assigns it to a period.
@app.route('/user/<userid>/grouprequest/', methods=['GET', 'POST'])
def grouprequestpage(userid,periodid=None):
    session = Session()
    #gets the data associated with this user
    thisuser = session.query(user).filter(user.userid == userid).first()
    if thisuser is None:
        return ('Did not find user in database. You have entered an incorrect URL address.')
    #check if this user is really a conductor and actually requested a conductorpage for a specific period
    if thisuser.isconductor == 1 and periodid is not None:
        conductorpage = True
        thisperiod = session.query(period).filter(period.periodid == periodid).first()
        if thisperiod is None:
            return ('Did not find period in database. Something has gone wrong.')
    else:
        conductorpage = False
        thisperiod = None
    today = datetime.datetime.combine(datetime.date.today(), datetime.time.min) #get today's date
    now = datetime.datetime.now() #get the time now
    #if this user isn't a conductor and/or they didn't request the conductor page and they've already requested groups today, deny them.
    if conductorpage == False:
        alreadyrequestedcount = session.query(group).filter(group.requesteduserid == thisuser.userid, group.requesttime >= today).count()
        log2('User has requested %s sessions today, and the limit is %s' % (alreadyrequestedcount, config.root.CampDetails['DailyGroupRequestLimit']))
        if int(alreadyrequestedcount) >= int(config.root.CampDetails['DailyGroupRequestLimit']):
            session.close()
            return ('You have already requested the maximum number of groups you can request in a single day. Please come back tomorrow!')
        
    #The below runs when a user visits the grouprequest page    
    if request.method == 'GET':
        
        if conductorpage == True:
            #UNTESTED - Finds all players who aren't already playing in this period
            playersPlayingInPeriod = session.query(user.userid).join(groupassignment).join(group).filter(group.periodid == periodid)
            playersdump = session.query(user.userid,user.firstname,user.lastname,instrument.instrumentname,instrument.grade,instrument.isprimary).\
                join(instrument).filter(~user.userid.in_(playersPlayingInPeriod)).all()
        else:
            #find all the instruments that everyone plays and serialize them to prepare to inject into the javascript
            playersdump = session.query(user.userid,user.firstname,user.lastname,instrument.instrumentname,instrument.grade,instrument.isprimary).\
                join(instrument).filter(user.userid != thisuser.userid).all()
        playersdump_serialized = []
        for p in playersdump:
            playersdump_serialized.append({'userid': p.userid, 'firstname': p.firstname, 'lastname': p.lastname,
                                            'instrumentname': p.instrumentname, 'grade': p.grade, 'isprimary': p.isprimary})
        log2('Players dump is: %s' % playersdump)
        #find the instruments this user plays
        thisuserinstruments = session.query(instrument).filter(instrument.userid == userid).all()
        thisuserinstruments_serialized = [i.serialize for i in thisuserinstruments]
        log2(thisuserinstruments_serialized)

        #if this is the conductorpage, the user will need a list of the locations at camp
        if conductorpage == True:
            locations = session.query(location).all()
        else: 
            locations = None

        #get the list of instruments from the config file
        instrumentlist = config.root.CampDetails['Instruments'].split(",")
        levels = config.root.CampDetails['Levels'].split(",")
        #find all group templates and serialize them to prepare to inject into the javascript
        allgrouptemplates = session.query(grouptemplate).filter(grouptemplate.size == 'S').all()
        
        #if we are not on the conductorpage, filter the group templates so the user only sees templates that are covered by their instruments
        if conductorpage == False:
            grouptemplates = []
            for t in allgrouptemplates:
                        found = False
                        for i in thisuserinstruments:
                            if getattr(t, i.instrumentname) > 0 and found == False:
                                grouptemplates.append(t)
                                found = True
        #if we are on the conductorpage, show the user all the grouptemplates
        else:
            grouptemplates = allgrouptemplates        

        #serialize the grouptemplates so the JS can read them properly
        grouptemplates_serialized = [i.serialize for i in grouptemplates]
        log2(grouptemplates_serialized)
        session.close()
        return render_template('grouprequest.html', \
                            user=thisuser, \
                            thisuserinstruments=thisuserinstruments, \
                            thisuserinstruments_serialized=thisuserinstruments_serialized, \
                            playerlimit = config.root.CampDetails['SmallGroupPlayerLimit'], \
                            grouptemplates = grouptemplates, \
                            grouptemplates_serialized=grouptemplates_serialized, \
                            campname=config.root.CampDetails['Name'], \
                            instrumentlist=instrumentlist, \
                            levels=levels, \
                            playersdump_serialized=playersdump_serialized, \
                            conductorpage=conductorpage, \
                            thisperiod=thisperiod, \
                            locations=locations, \
                            )
    
    #The below runs when a user presses "Submit" on the grouprequest page. It creates a group object with the configuraiton selected by 
    #the user, and creates groupassignments for all players they selected (and the user themselves)
    if request.method == 'POST':
        #format the packet received from the server as JSON
        content = request.json
        session = Session()
        log2('Grouprequest received. Whole content of JSON returned is: %s' % content)
        #establish the 'grouprequest' group object. This will be built up from the JSON packet, and then added to the database
        grouprequest = group(music = content['music'], ismusical = 1, requesteduserid = userid)
        #if the conductorpage is false, we need to add a requesttime to properly order the requests later
        if conductorpage == False:
            grouprequest.requesttime = now
        #if the conductorpage is true, we expect to also receive a locationid from the JSON packet, so we add it to the grouprequest
        if conductorpage == True:
            grouprequest.locationid = content['locationid']
        #for each player object in the players array in the JSON packet
        for p in content['players']:
            log2('Performing action for instrument %s' % p['instrumentname'])
            #increment the instrument counter in the grouprequest object corresponding with this instrument name
            currentinstrumentcount = getattr(grouprequest, p['instrumentname'])
            if currentinstrumentcount is None:
                setattr(grouprequest, p['instrumentname'], 1)
            else:
                setattr(grouprequest, p['instrumentname'], (currentinstrumentcount + 1))
        #run the getgroupname function, which logically names the group
        grouprequest.groupname = getgroupname(grouprequest)
        #if we are on the conductorpage, instantly confirm this group (assign it to the period the user submitted)
        if conductorpage == True:
            grouprequest.periodid = thisperiod.periodid     
        #add the grouprequest to the database
        session.add(grouprequest)
        #for each player object in the players array in the JSON packet
        for p in content['players']:
            log2('Performing action for player with id %s' % p['playerid'])
            #if we are on the conductorpage, you cannot submit blank players. Give the user an error and take them back to their dashboard.
            if p['playerid'] == 'null' and conductorpage == True:
                url = ('/user/' + str(thisuser.userid) + '/')
                session.close()
                return jsonify(message = 'Something went wrong. You are not allowed to have null players in a conductor group request.', url = url)
            #if the playerid is not null, we create a groupassignment for them and bind it to this group
            if p['playerid'] != 'null':
                playeruser = session.query(user).filter(user.userid == p['playerid']).first()
                if playeruser is not None:
                    playergroupassignment = groupassignment(userid = playeruser.userid, groupid = grouprequest.groupid, instrument = p['instrumentname'])
                    session.add(playergroupassignment)
                else:
                    url = ('/user/' + str(thisuser.userid) + '/')
                    session.close()
                    return jsonify(message = 'Could not find one of your selected players in the database. Please refresh the page and try again.', url = url)
            #if none of the above are satisfied - that's ok. you're allowed to submit null playernames in the user request page, these will be 
            #allocated by the admin when the group is confirmed.
        
        #create the group and the groupassinments configured above in the database
        session.commit()
        #send the URL for the group that was just created to the user, and send them to that page
        url = ('/user/' + str(thisuser.userid) + '/group/' + str(grouprequest.groupid) + '/')
        log2('Sending user to URL: %s' % url)
        session.close()
        if conductorpage == True:
            return jsonify(message = 'Your group has been created and confirmed', url = url)
        else:
            return jsonify(message = 'Your group request has been successfully created. When everyone in your group is avaliable, it will be scheduled to run.', url = url)

@app.route('/user/<userid>/grouprequest/conductor/<periodid>/', methods=['GET', 'POST'])
def conductorgrouprequestpage(userid,periodid):
    session = Session()
    #gets the data associated with this user
    thisuser = session.query(user).filter(user.userid == userid).first()
    if thisuser is None:
        return ('Did not find user in database. You have entered an incorrect URL address.')
    if thisuser.isconductor != 1:
        return ('You are not a conductor and cannot visit this page.')
    return grouprequestpage(userid,periodid)

#This page is currently a placehoder for the large group instrumentation page, where conductors can choose instrumentation for their groups.
@app.route('/user/<userid>/largegroupinstrumentation/')
def largegroupinstrumentation(userid,periodid):
    session = Session()
    #gets the data associated with this user
    thisuser = session.query(user).filter(user.userid == userid).first()
    session.close()
    return 'nothing'

#This page is currently a placehoder for the announcement editor page. An "announcer" user can edit it and everyone else will see the
#announcement on their dashboards.
@app.route('/user/<userid>/announcement/')
def announcementpage(userid):
    session = Session()
    #gets the data associated with this user
    thisuser = session.query(user).filter(user.userid == userid).first()
    session.close()
    return 'nothing'

#this page is the full report for any given period
@app.route('/user/<userid>/period/<periodid>/')
def periodpage(userid,periodid):
    session = Session()
    #gets the data associated with this user
    thisuser = session.query(user).filter(user.userid == userid).first()
    if thisuser is None:
        return ('Did not find user in database. You have entered an incorrect URL address.')
    players = periodidtoplayerlist(session, periodid)
    thisperiod = session.query(period).filter(period.periodid == periodid).first()
    session.close()
    return render_template('period.html', \
                            players=players, \
                            campname=config.root.CampDetails['Name'], \
                            user=thisuser, \
                            period=thisperiod \
                            )










#ADMIN PAGES ARE BELOW















#Shows the godpage to the user. Godpage contains all user names and links to all their dashboards. Right now uses a shared password,
#but would be better if tied to a user's admin account. However, there's no easy way to currently see what the userid of the admin is
#after it's been created. Hmm... a conundrum.
@app.route('/godpage/<password>/')
def godpage(password):
    if password != config.root.CampDetails['SecretKey']:
        return 'Wrong password'
    else:
        session = Session()
        users = session.query(user).all()
        session.close()
        return render_template('godpage.html', \
                                #user=thisuser, \
                                users=users, \
                                campname=config.root.CampDetails['Name'], \
                                )

#the below creates a new user. The idea for this is that you could concatenate a string up in Excel with your user's details and click 
#on all the links to create them.
@app.route('/new/user/<firstname>/<lastname>/<age>/<arrival>/<departure>/<isannouncer>/<isconductor>/<isadmin>/')
def new_user(firstname,lastname,age,arrival,departure,isannouncer,isconductor,isadmin):
    session = Session()
    arrival = datetime.datetime.strptime(arrival, '%Y-%m-%d %H:%M')
    departure = datetime.datetime.strptime(departure, '%Y-%m-%d %H:%M')
    log2('user is staying at camp starting %s and ending %s' % (arrival,departure))
    userid = str(uuid.uuid4())
    newuser = user(userid=userid, firstname=firstname, lastname=lastname, age=age, arrival=arrival, departure=departure, isannouncer=isannouncer, isconductor=isconductor, isadmin=isadmin)
    session.add(newuser)
    absentgroups = session.query(group.groupid).join(period).filter(or_(period.starttime < arrival, period.starttime > departure)).all()
    for g in absentgroups:
        log2('assigning user to absent group with id %s' % g.groupid)
        ga = groupassignment(userid = userid, groupid = g.groupid, instrument = 'absent')
        session.add(ga)
    session.commit()
    session.close()
    return ('user created with id %s' % userid)

#the below creates a new user-instrument relationship.
@app.route('/new/instrument/<userid>/<instrumentname>/<grade>/<isprimary>/')
def new_instrument(userid,instrumentname,grade,isprimary):
    session = Session()
    thisuser = session.query(user).filter(user.userid == userid).first()    
    checkduplicate = session.query(instrument).filter(instrument.userid == thisuser.userid, instrument.instrumentname == instrumentname).first()
    checkprimary = session.query(instrument).filter(instrument.userid == thisuser.userid, instrument.isprimary == 1).first()
    if thisuser is None:
        session.close()
        return ('Did not find user in database. You have entered an incorrect URL address.')
    elif checkduplicate is not None:
        session.close()
        return ('This user is already associated with this instrument.')
    elif 1 > int(grade) > 5:
        log2('User submitted grade of %s' % grade)
        session.close()
        return ('incorrect grade. Grade should be between 1 and 5.')
    elif not (int(isprimary) == 0 or int(isprimary) == 1):
        log2('User submitted isprimary of %s' % isprimary)
        session.close()
        return ('incorrect isprimary value. isprimary should be a 0 or a 1.')
    elif int(isprimary) == 1 and checkprimary is not None:
        session.close()
        return ('This user already has a primary instrument. Cannot create another primary instrument record.')
    else:
        thisinstrument = instrument(userid = thisuser.userid, instrumentname = instrumentname, grade = grade, isprimary = isprimary)
        session.add(thisinstrument)
        session.commit()
        return ('intsrument link created for user with id %s' % thisuser.userid)
        session.close()
    return ('something went wrong. you should never get this message. Inside new_instrument method with no caught errors.')

if __name__ == '__main__':
    app.run(debug=True, \
            #host='0.0.0.0'\
            )