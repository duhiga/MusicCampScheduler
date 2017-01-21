from flask import Flask, render_template, request, redirect, jsonify, make_response, json, request, url_for, send_from_directory, flash
from collections import namedtuple
from werkzeug import secure_filename
import sys
import types
import time
import datetime
import re
import json
import untangle
import uuid
import sqlalchemy
import os
from datetime import date, timedelta
from DBSetup import *
from sqlalchemy import *
from sqlalchemy.orm import aliased
from config import *
from SMTPemail import *

# Make the WSGI interface available at the top level so wfastcgi can get it.
app = Flask(__name__)
#app.secret_key = 'MusicCampIsCool'
wsgi_app = app.wsgi_app
# These are the extension that we are accepting to be uploaded
app.config['ALLOWED_EXTENSIONS'] = set(['txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'xml', 'csv'])
app.secret_key = getconfig('SecretKey')
Session = sessionmaker(bind=engine)

# For a given file, return whether it's an allowed type or not
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1] in app.config['ALLOWED_EXTENSIONS']

#Looks up the amount of times a user has participated in an "ismusical" group during the camp
def playcount(session,userid):
    playcount = session.query(user.userid).join(groupassignment, user.userid == groupassignment.userid).join(group, groupassignment.groupid == group.groupid).outerjoin(period).filter(user.userid == userid, group.ismusical == 1, period.endtime <= datetime.datetime.now()).count()
    return playcount

#get the information needed to fill in the user's schedule table
def getschedule(session,thisuser,date):
    #find the start of the next day
    nextday = date + datetime.timedelta(days=1)

    schedule = []
    #for each period in the requested day
    for p in session.query(period).filter(period.starttime > date, period.endtime < nextday).order_by(period.starttime).all():
        #try to find a group assignment for the user
        g = session.query(group.groupname, period.starttime, period.endtime, location.locationname, group.groupid, group.ismusical, group.iseveryone, music.musicid, \
                            period.periodid, period.periodname, groupassignment.instrumentname, period.meal, group.groupdescription, music.composer, music.musicname, group.musicwritein).\
                            join(period).join(groupassignment).join(user).join(instrument).outerjoin(location).outerjoin(music).\
                            filter(user.userid == thisuser.userid, group.periodid == p.periodid, group.status == 'Confirmed').first()
        if g is not None:
            schedule.append(g)
        e = None
        #if we didn't find an assigned group...
        if g is None:
            #try to find an iseveryone group at the time of this period
            e = session.query(group.groupname, period.starttime, period.endtime, location.locationname, group.groupid, group.ismusical, \
                            group.iseveryone, period.periodid, period.periodname, period.meal, group.groupdescription).\
                            join(period).join(location).\
                            filter(group.iseveryone == 1, group.periodid == p.periodid).first()
        if e is not None:
            schedule.append(e)
        #if we didn't find an assigned group or an iseveryone group...
        if e is None and g is None:
            #just add the period detalis
            schedule.append(p)
    return schedule

def errorpage(thisuser,message):
    return render_template('errorpage.html', \
                                        thisuser=thisuser, \
                                        campname=getconfig('Name'), favicon=getconfig('Favicon_URL'), instrumentlist=getconfig('Instruments').split(","), supportemailaddress=getconfig('SupportEmailAddress'), \
                                        errormessage = message
                                        )

#from an input group, returns the highest and lowest instrument levels that should be assigned depending on its config
def getgrouplevel(session,inputgroup,min_or_max):
    if min_or_max == 'min':
        log('GETGROUPLEVEL: Finding group %s level' % min_or_max)
        #if the group is set to "auto", i.e. blank or 0, find the minimum level of all the players currently playing in the group
        if inputgroup.minimumlevel is None or inputgroup.minimumlevel == '' or inputgroup.minimumlevel == '0' or inputgroup.minimumlevel == 0:
            minimumgradeob = session.query(user.firstname, user.lastname, instrument.instrumentname, instrument.grade).join(groupassignment).join(group).\
                join(instrument, and_(groupassignment.instrumentname == instrument.instrumentname, user.userid == instrument.userid)).\
                filter(group.groupid == inputgroup.groupid).order_by(instrument.grade).first()
            #if we find at least one player in this group, set the minimumgrade to be this players level minus the autoassignlimitlow
            if minimumgradeob is not None:
                log('GETGROUPLEVEL: Found minimum grade in group %s to be %s %s playing %s with grade %s' % (inputgroup.groupid, minimumgradeob.firstname, minimumgradeob.lastname, minimumgradeob.instrumentname, minimumgradeob.grade))
                level = int(minimumgradeob.grade) - int(getconfig('AutoAssignLimitLow'))
                if level < 1:
                    level = 1
            #if we don't find a player in this group, set the minimum level to be 0 (not allowed to autofill)
            else: 
                level = 0
        #if this group's minimum level is explicitly set, use that setting
        else:
            level = inputgroup.minimumlevel
    if min_or_max == 'max':
        if inputgroup.maximumlevel is None or inputgroup.maximumlevel == '' or inputgroup.maximumlevel == '0' or inputgroup.maximumlevel == 0:
            minimumgradeob = session.query(user.firstname, user.lastname, instrument.instrumentname, instrument.grade).join(groupassignment).join(group).\
                join(instrument, and_(groupassignment.instrumentname == instrument.instrumentname, user.userid == instrument.userid)).\
                filter(group.groupid == inputgroup.groupid).order_by(instrument.grade).first()
            #if we find at least one player in this group, set the maximumgrade to be this players level plus the autoassignlimithigh
            if minimumgradeob is not None:
                log('GETGROUPLEVEL: Found minimum grade in group %s to be %s %s playing %s with grade %s' % (inputgroup.groupid, minimumgradeob.firstname, minimumgradeob.lastname, minimumgradeob.instrumentname, minimumgradeob.grade))
                level = int(minimumgradeob.grade) + int(getconfig('AutoAssignLimitHigh'))
                if level > int(getconfig('AutoAssignLimitHigh')):
                    level = getconfig('MaximumLevel')
            #if we don't find a player in this group, set the maximum level to 0 (not allowed to autofill)
            else:
                level = 0
        #if this group's maximum level is explicitly set, use that setting
        else:
            level = inputgroup.maximumlevel
    log('GETGROUPLEVEL: Found %s grade of group %s to be %s' % (min_or_max,inputgroup.groupid,level))
    return int(level)
    
#NOT USED gets a list of periods corresponding to the requested userid and date, formatting it in a nice way for the user home
"""def useridanddatetoperiods(session,userid,date):
    nextday = date + datetime.timedelta(days=1)"""

def getgroupname(session,thisgroup):

    log('GETGROUPNAME: Generating a name for requested group')
    instrumentlist = getconfig('Instruments').split(",")

    #if this group's instrumentation matches a grouptempplate, then give it the name of that template
    templatematch = session.query(grouptemplate).filter(*[getattr(grouptemplate,i) == getattr(thisgroup,i) for i in instrumentlist]).first()
    if templatematch is not None:
        log('GETGROUPNAME: Found that this group instrumentation matches the template %s' % templatematch.grouptemplatename)
        name = templatematch.grouptemplatename

    #if we don't get a match, then we find how many players there are in this group, and give it a more generic name
    else:
        count = 0
        for i in instrumentlist:
            value = getattr(thisgroup, i)
            log('GETGROUPNAME: Instrument %s is value %s' % (i, value))
            if value is not None:
                count = count + int(getattr(thisgroup, i))
        log('GETGROUPNAME: Found %s instruments in group.' % value)
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
        elif count == 9:
            name = 'Nonet'
        elif count == 10:
            name = 'Dectet'
        else:
            name = 'Custom Group'

    if thisgroup.musicid is not None:
        log('GETGROUPNAME: Found that this groups musicid is %s' % thisgroup.musicid)
        composer = session.query(music).filter(music.musicid == thisgroup.musicid).first().composer
        log('GETGROUPNAME: Found composer matching this music to be %s' % composer)
        name = composer + ' ' + name
        
    log('GETGROUPNAME: Full name of group returned is %s' % name)
    return name

#the root page isn't meant to be navigable.  It shows the user an error and
#tells them how to get to their user home.
@app.route('/')
def rootpage():
    return render_template('index.html')

#upon the URL request in the form domain/user/<logonid> the user receives their home. The home contains the groups they 
#are playing in. Optionally, this page presents their home in the future or the past, and gives them further options.
@app.route('/user/<logonid>/')
def home(logonid,inputdate='n'):

    session = Session()
    #gets the data associated with this user
    thisuser = session.query(user).filter(user.logonid == logonid).first()
    if thisuser is None:
        session.close()
        return ('Did not find user in database. You have entered an incorrect URL address.')

    try:
        log('home fetch requested for user %s %s' % (thisuser.firstname, thisuser.lastname))
        log('date modifier is currently set to %s' % inputdate)
        #get the current announcement
        currentannouncement = session.query(announcement).order_by(desc(announcement.creationtime)).first()
        if currentannouncement is not None:
            announcementcontent = currentannouncement.content.replace("\n","<br />")
        else:
            announcementcontent = ''
        #get impontant datetimes
        today = datetime.datetime.combine(datetime.date.today(), datetime.time.min) #get today's date
        log('Today is %s' % today.strftime('%Y-%m-%d %H:%M'))
        campstarttime = datetime.datetime.strptime(getconfig('StartTime'), '%Y-%m-%d %H:%M')
        campendtime = datetime.datetime.strptime(getconfig('EndTime'), '%Y-%m-%d %H:%M')
        #if the suer has submitted a date, convert it to a datetime and use it as the display date
        if inputdate != 'n': 
            displaydate = datetime.datetime.strptime(inputdate, '%Y-%m-%d')
        #if the user has not submitted a date and today is before the start of camp, use the first day of camp as the display date
        elif today < datetime.datetime.strptime(getconfig('StartTime'), '%Y-%m-%d %H:%M'): 
            displaydate = datetime.datetime.strptime(getconfig('StartTime').split()[0], '%Y-%m-%d')
        #if today is after the start of camp, use today as the display date
        else:
            displaydate = today
        
        previousday = displaydate + datetime.timedelta(days=-1)
        midday = displaydate + datetime.timedelta(hours=12)
        nextday = displaydate + datetime.timedelta(days=1)

        #get an array containing the dates that the camp is running
        dates = []
        for d in range((campendtime-campstarttime).days + 2):
            dates.append(campstarttime + timedelta(days=d))

        #get the user's schedule, an array of objects depending on the user's state during each period
        schedule = getschedule(session,thisuser,displaydate)

        unscheduled = False
        for p in schedule:
            if session.query(group).filter(group.periodid == p.periodid, group.status == "Confirmed", or_(group.ismusical == 1, group.iseveryone == 1)).first() is None:
                unscheduled = True
                break

        session.close()

        return render_template('home.html', \
                            thisuser=thisuser, \
                            date=displaydate,\
                            schedule=schedule, \
                            dates=dates, \
                            previousday=previousday, \
                            nextday=nextday, \
                            today=today, \
                            campname=getconfig('Name'), favicon=getconfig('Favicon_URL'), instrumentlist=getconfig('Instruments').split(","), supportemailaddress=getconfig('SupportEmailAddress'), \
                            currentannouncement=announcementcontent, \
                            now = datetime.datetime.now(), \
                            midday=midday, \
                            unscheduled=unscheduled, \
                            )

    except Exception as ex:
        log('Failed to execute %s for user %s %s with exception: %s.' % (request.method, thisuser.firstname, thisuser.lastname, ex))
        message = ('Failed to execute %s with exception: %s. Try refreshing the page and trying again or contact camp administration.' % (request.method, ex))
        session.rollback()
        session.close()
        if request.method == 'GET':
            return render_template('errorpage.html', \
                                        thisuser=thisuser, \
                                        campname=getconfig('Name'), favicon=getconfig('Favicon_URL'), instrumentlist=getconfig('Instruments').split(","), supportemailaddress=getconfig('SupportEmailAddress'), \
                                        errormessage = 'Failed to display page with exception: %s.' % ex
                                        )
        else:
            return jsonify(message = message, url = 'none')

#NOT CURRENTLY USED Currently broken. Doesn't like the fact that the getschedule function returns an array of inconsistant objects. Either make them consistant,
#or put logic into the 'for s in ...' part of the below function. Or maybe improve the query in the getschedule function.
"""@app.route('/user/<logonid>/requestschedule/', methods=["POST"])
def requestschedule(logonid):
    log('Schedule request for date %s' % request.json['date'])
    #convert the inputdate to a datetime object
    date = datetime.datetime.strptime(request.json['date'], '%Y-%m-%d')
    session = Session()
    #gets the data associated with this user
    thisuser = session.query(user).filter(user.logonid == logonid).first()
    if thisuser is None:
        session.close()
        return jsonify(message = 'Your user does not exist. Something went wrong.', url = 'none', status_code = 400)

    schedule_serialized = []
    for s in getschedule(session,thisuser,date):
        schedule_serialized.append({'groupname': s.groupname, 'starttime': s.starttime, 'endtime': s.endtime,\
            'locationname': s.locationname, 'groupid': s.groupid, 'ismusical': s.ismusical, 'iseveryone': s.iseveryone,\
            'preiodid': s.periodid, 'periodname': s.periodname, 'instrumentname': s.instrumentname})

    return jsonify(schedule_serialized)"""

#When the user selects the "next day" and "previous day" links on their home, it goes to this URL. this route redirects them back
#to the user home with a date modifier.
@app.route('/user/<logonid>/date/<date>/')
def homeDateModifier(logonid,date):
    return home(logonid,date)

#Makes a post query that marks a player adsent for a given period. This is triggered off the above (two) home functions.
@app.route("/user/<logonid>/period/<periodid>/absent/<command>/", methods=["POST"])
def mark_absent(logonid,periodid,command):
    session = Session()
    #gets the data associated with this user
    thisuser = session.query(user).filter(user.logonid == logonid).first()
    if thisuser is None:
        return ('Did not find user in database. You have entered an incorrect URL address.')

    currentassignment = session.query(group.groupname, groupassignment.groupassignmentid).\
                    join(groupassignment).join(user).join(period).\
                    filter(period.periodid == periodid, user.userid == thisuser.userid).first()
    log('User is currently assigned to ' + str(currentassignment))
    #case if the user is not assigned to anything, and attempted to mark themselves as absent
    if currentassignment == None and command == 'confirm':
        log('user is not assigned to anything and is requesting an absence')
        #get the groupid for the absent group associated with this period
        absentgroup = session.query(group.groupid).join(period).filter(group.groupname == 'absent', period.periodid == periodid).first()
        log('found absent group %s' % absentgroup)
        #assign this person to the absent group
        try:
            session.add(groupassignment(userid = thisuser.userid, groupid = absentgroup.groupid))
            session.commit()
            session.close()
            return 'Now user marked absent for period'
        except Exception as ex:
            log('failed to allocate user as absent for period %s with exception: %s' % (periodid,ex))
            session.rollback()
            session.close()
            return 'error'
    #case if the user is already marked absent and they tried to mark themselves as absent again
    if currentassignment != None:
        if currentassignment.groupname == 'absent' and command == 'confirm':
            session.close()
            log('User %s requested absent but is already marked absent' % thisuser.userid)
            return 'Already marked absent for period'
        #case if the user is already marked absent and their tried to cancel their absent request
        elif currentassignment.groupname == 'absent' and command == 'cancel':            
            try:
                session.delete(session.query(groupassignment).filter(groupassignment.groupassignmentid == currentassignment.groupassignmentid).first())
                session.commit()
                session.close()
                return 'Removed absent request for ' + periodid
            except Exception as ex:
                log('failed to remove absent request for period with exception: %s' % ex)
                session.rollback()
                session.close()
                return 'error'
    #catch-all case. You'd get here if the adminsitrator was changing the back-end while the user was on their home page
    else:
        session.close()
        return 'You are already assigned to a group for this period. You have NOT been marked absent. Talk to the adminsitrator to fix this.'

#The group page displays all the people in a given group, along with possible substitutes
@app.route('/user/<logonid>/group/<groupid>/')
def grouppage(logonid,groupid):
    session = Session()
    #gets the data associated with this user
    thisuser = session.query(user).filter(user.logonid == logonid).first()
    if thisuser is None:
        return ('Did not find user in database. You have entered an incorrect URL address.')
    try:
        thisgroup = session.query(group).filter(group.groupid == groupid).first()
        thislocation = session.query(location).join(group).filter(group.groupid == groupid).first()
        if thisgroup.musicid is not None:
            thismusic = session.query(music).filter(music.musicid == thisgroup.musicid).first()
        else:
            thismusic = None
        if thisgroup is None:
            return ('Did not find group in database. You have entered an incorrect URL address.')
        thisperiod = session.query(period).filter(period.periodid == thisgroup.periodid).first()

        #gets the list of players playing in the given group
        players = session.query(user.userid, user.firstname, user.lastname, groupassignment.instrumentname).join(groupassignment).join(group).\
                                filter(group.groupid == groupid).order_by(groupassignment.instrumentname).all()
        
        #find the substitutes for this group
        if thisgroup.status == 'Confirmed' and thisgroup.iseveryone != 1 and thisgroup.groupname != 'absent':
            minimumgrade = getgrouplevel(session,thisgroup,'min')
            maximumgrade = getgrouplevel(session,thisgroup,'max')
            #get the list of instruments played in this group and removes duplicates to be used as a subquery later
            instruments_in_group_query = session.query(groupassignment.instrumentname).join(group).filter(group.groupid == thisgroup.groupid).group_by(groupassignment.instrumentname)
            log('Found instruments in group to be %s' % instruments_in_group_query.all())
            #get the userids of everyone that's already playing in something this period
            everyone_playing_in_periodquery = session.query(user.userid).join(groupassignment).join(group).join(period).filter(period.periodid == thisgroup.periodid)
            #combine the last two queries with another query, finding everyone that both plays an instrument that's found in this
            #group AND isn't in the list of users that are already playing in this period.
            substitutes = session.query(instrument.instrumentname, user.userid, user.firstname, user.lastname).join(user).\
                filter(~user.userid.in_(everyone_playing_in_periodquery), user.isactive == 1, user.arrival <= thisperiod.starttime, user.departure >= thisperiod.endtime).\
                filter(instrument.instrumentname.in_(instruments_in_group_query), instrument.grade >= minimumgrade, instrument.grade <= maximumgrade, instrument.isactive == 1).\
                order_by(instrument.instrumentname)
        else:
            substitutes = None

        session.close()
        return render_template('grouppage.html', \
                            thisperiod=thisperiod, \
                            campname=getconfig('Name'), favicon=getconfig('Favicon_URL'), instrumentlist=getconfig('Instruments').split(","), supportemailaddress=getconfig('SupportEmailAddress'), \
                            thisgroup=thisgroup, \
                            players=players, \
                            substitutes=substitutes, \
                            thisuser=thisuser, \
                            thislocation=thislocation, \
                            thismusic=thismusic, \
                            )
    
    except Exception as ex:
        log('Failed to execute %s for user %s %s with exception: %s.' % (request.method, thisuser.firstname, thisuser.lastname, ex))
        message = ('Failed to execute %s with exception: %s. Try refreshing the page and trying again or contact camp administration.' % (request.method, ex))
        session.rollback()
        session.close()
        if request.method == 'GET':
            return render_template('errorpage.html', \
                                        thisuser=thisuser, \
                                        campname=getconfig('Name'), favicon=getconfig('Favicon_URL'), instrumentlist=getconfig('Instruments').split(","), supportemailaddress=getconfig('SupportEmailAddress'), \
                                        errormessage = 'Failed to display page with exception: %s.' % ex
                                        )
        else:
            return jsonify(message = message, url = 'none')

#Group editor page. Only accessable by admins. Navigate here from a group to edit group.
@app.route('/user/<logonid>/group/<groupid>/edit/', methods=['GET', 'POST', 'DELETE'])
def editgroup(logonid,groupid,periodid=None):

    session = Session()
    #gets the data associated with this user
    thisuser = session.query(user).filter(user.logonid == logonid).first()
    if thisuser is None:
        return ('Did not find user in database. You have entered an incorrect URL address.')

    try:
        if thisuser.isadmin != 1:
            session.close()
            return 'You do not have permission to do this.'
        if periodid == 'None':
            periodid = None
        if groupid == 'new' or groupid is None:
            groupid = None
            thisgroup = group(ismusical = 1, requesteduserid = thisuser.userid)
            requestor = thisuser
        else:
            thisgroup = session.query(group).filter(group.groupid == groupid).first()
            requestor = session.query(user).filter(user.userid == thisgroup.requesteduserid).first()
        if request.method == 'GET':

            tomorrow = datetime.datetime.combine(datetime.date.today(), datetime.time.min) + datetime.timedelta(days=1)

            #Current period tracks the period that the group is already set to (none, if it's a new group)
            currentperiod = session.query(period).filter(period.periodid == thisgroup.periodid).first()

            #print out the list of players and remove any that have already left camp
            thisgroupplayers = session.query(user.userid, user.firstname, user.lastname, groupassignment.instrumentname, user.departure).join(groupassignment).join(group).filter(group.groupid == thisgroup.groupid).order_by(groupassignment.instrumentname).all()
            if thisgroupplayers is not None:
                log('Players in this group:')
                for p in thisgroupplayers:
                    log('%s %s: %s' % (p.firstname, p.lastname, p.instrumentname))
                    if p.departure <= tomorrow:
                        a = session.query(groupassignment).filter(groupassignment.userid == p.userid, groupassignment.groupid == thisgroup.groupid).first()
                        log('Found user %s %s with departure before tomorrow, removing them from this group.' % (p.firstname, p.lastname))
                        session.delete(a)
                session.commit()

            #find all periods from now until the end of time to display to the user, then removes any periods that the people in this group cannot play in
            thisgroupplayers_query = session.query(user.userid).join(groupassignment).join(group).filter(group.groupid == thisgroup.groupid).order_by(groupassignment.instrumentname)
            periodlist = session.query(period).order_by(period.starttime).all()
            if thisgroupplayers_query.first() is not None:
                lastarrival = session.query(func.max(user.arrival).label("lastarrival")).filter(user.userid.in_(thisgroupplayers_query)).first().lastarrival
                firstdeparture = session.query(func.min(user.departure).label("firstdeparture")).filter(user.userid.in_(thisgroupplayers_query)).first().firstdeparture
            else:
                lastarrival = datetime.datetime.strptime(getconfig('StartTime'), '%Y-%m-%d %H:%M')
                firstdeparture = datetime.datetime.strptime(getconfig('EndTime'), '%Y-%m-%d %H:%M')
            log('Last Arrival time of players in this group: %s' % lastarrival)
            log('First Departure time of players in this group: %s' % firstdeparture)
            periods = []
            for p in periodlist:
                if thisgroupplayers_query.first() is None or ((currentperiod and p.periodid == currentperiod.periodid) \
                        or (len(session.query(user.userid).join(groupassignment).join(group).join(period).filter(group.periodid == p.periodid, or_(user.userid.in_(thisgroupplayers_query))).all()) == 0\
                        and p.starttime > lastarrival and p.starttime < firstdeparture)):
                    periods.append(p)

            #if there was no selected period by the user, select the first period
            if periodid is not None:
                selectedperiod = session.query(period).filter(period.periodid == periodid).first()
            elif currentperiod is None:
                log('This is a periodless group. Selecting a period for the group.')
                foundperiod = False
                for p in periods:
                    if p.starttime > tomorrow and session.query(period.periodid).join(group).filter(period.periodid == p.periodid, group.iseveryone == 1).first() is None:
                        selectedperiod = p
                        foundperiod = True
                        break
                if not foundperiod:
                    selectedperiod = None
            else:
                selectedperiod = currentperiod
            thislocation = session.query(location).join(group).filter(group.groupid == groupid).first()
            #gets the list of players playing in the given group
            thisgroupplayers = session.query(user.userid, user.firstname, user.lastname, groupassignment.instrumentname).join(groupassignment).join(group).\
                                    filter(group.groupid == thisgroup.groupid).order_by(groupassignment.instrumentname).all()
            thisgroupplayers_serialized = []
            for p in thisgroupplayers:
                    thisgroupplayers_serialized.append({'userid': p.userid, 'firstname': p.firstname, 'lastname': p.lastname,
                    'instrumentname': p.instrumentname})
            if selectedperiod is not None:
                #Finds all players who are already playing in this period (except in this specific group)
                playersPlayingInPeriod = session.query(user.userid).join(groupassignment).join(group).filter(group.groupid != thisgroup.groupid).filter(group.periodid == selectedperiod.periodid)
                #finds all players who are available to play in this group (they aren't already playing in other groups)
                playersdump = session.query(user.userid,user.firstname,user.lastname,instrument.instrumentname,instrument.grade,instrument.isprimary).\
                            join(instrument).filter(~user.userid.in_(playersPlayingInPeriod), user.isactive == 1, user.arrival <= selectedperiod.starttime, user.departure >= selectedperiod.endtime, instrument.isactive == 1).all()
            else:
                playersdump = session.query(user.userid,user.firstname,user.lastname,instrument.instrumentname,instrument.grade,instrument.isprimary).\
                            join(instrument).filter(user.isactive == 1, instrument.isactive == 1).all()
            playersdump_serialized = []
            for p in playersdump:
                playersdump_serialized.append({'userid': p.userid, 'firstname': p.firstname, 'lastname': p.lastname,
                    'instrumentname': p.instrumentname, 'grade': p.grade, 'isprimary': p.isprimary})

            #Get a list of the available music not being used in the period selected
            if selectedperiod is not None:
                musics_used_query = session.query(music.musicid).join(group).join(period).filter(period.periodid == selectedperiod.periodid, group.groupid != thisgroup.groupid)
                musics = session.query(music).filter(~music.musicid.in_(musics_used_query)).all()
            else:
                musics = session.query(music).all()
            musics_serialized = [i.serialize for i in musics]
            thismusic = session.query(music).filter(music.musicid == thisgroup.musicid).first()

            #get a list of the locations not being used in this period
            if selectedperiod is not None:
                locations_used_query = session.query(location.locationid).join(group).join(period).filter(period.periodid == selectedperiod.periodid, group.groupid != thisgroup.groupid, location.locationname != 'None')
                locations = session.query(location).filter(~location.locationid.in_(locations_used_query)).all()
            else:
                locations = session.query(location).all()
            log('This groups status is %s' % thisgroup.status)

            #find all group templates to show in a dropdown
            grouptemplates = session.query(grouptemplate).all()
            grouptemplates_serialized = [i.serialize for i in grouptemplates]

            groupmin = getgrouplevel(session,thisgroup,'min')
            groupmax = getgrouplevel(session,thisgroup,'max')

            template = render_template('editgroup.html', \
                                currentperiod=currentperiod, \
                                selectedperiod=selectedperiod, \
                                campname=getconfig('Name'), favicon=getconfig('Favicon_URL'), instrumentlist=getconfig('Instruments').split(","), supportemailaddress=getconfig('SupportEmailAddress'), \
                                thisgroup=thisgroup, \
                                thisgroupplayers=thisgroupplayers, \
                                thisuser=thisuser, \
                                periods=periods, \
                                thislocation=thislocation, \
                                locations=locations, \
                                playersdump=playersdump, \
                                playersdump_serialized=playersdump_serialized, \
                                thisgroupplayers_serialized=thisgroupplayers_serialized, \
                                maximumlevel=int(getconfig('MaximumLevel')), \
                                grouptemplates=grouptemplates, \
                                grouptemplates_serialized=grouptemplates_serialized, \
                                musics=musics, \
                                musics_serialized=musics_serialized, \
                                thismusic=thismusic, \
                                instrumentlist_string=getconfig('Instruments'), \
                                groupmin=groupmin, \
                                groupmax=groupmax, \
                                requestor=requestor, \
                                )
            session.close()
            return template

        if request.method == 'DELETE':
            if groupid is not None:
                thisgroupassignments = session.query(groupassignment).filter(groupassignment.groupid == thisgroup.groupid).all()
                for a in thisgroupassignments:
                    session.delete(a)
                session.commit()
                session.delete(thisgroup)
                session.commit()
            else:
                session.rollback()
            url = ('/user/' + str(thisuser.logonid) + '/')
            message = 'none'
            flash(u'Group Deleted','message')
            log('Sending user to URL: %s' % url)
            session.close()
            return jsonify(message = message, url = url)

        if request.method == 'POST':
            #format the packet received from the server as JSON
            content = request.json
            if content['groupname'] == '' or content['groupname'] == 'null' or content['groupname'] is None:
                session.rollback()
                session.close()
                return jsonify(message = 'You must give this group a name before saving or autofilling.', url = 'none')
            if content['periodid'] != '' and content['periodid'] != 'null' and content['periodid'] is not None:
                thisperiod = session.query(period).filter(period.periodid == content['periodid']).first()
            else:
                session.rollback()
                session.close()
                return jsonify(message = 'Could not find a period with the selected id. Refresh the page and try again.', url = 'none')
            thisgroupassignments = session.query(groupassignment).filter(groupassignment.groupid == thisgroup.groupid).all()
            for a in thisgroupassignments:
                session.delete(a)

            #add the content in the packet to this group's attributes
            for key,value in content.items():
                if (value is None or value == 'null' or value == '') and key != 'primary_only':
                    log('Setting %s to be NULL' % (key))
                    setattr(thisgroup,key,None)
                elif key != 'primary_only':
                    log('Setting %s to be %s' % (key, value))
                    setattr(thisgroup,key,value)
            if groupid == None:
                session.add(thisgroup)
                thisgroup.requesttime = datetime.datetime.now()
                session.commit()

            location_clash = session.query(location.locationname, group.groupid).join(group).join(period).filter(period.periodid == thisperiod.periodid, location.locationid == content['locationid'], group.groupid != thisgroup.groupid).first()
            if location_clash is not None:
                log('Group %s is already using this location %s' % (location_clash.groupid, location_clash.locationname))
                session.rollback()
                session.close()
                return jsonify(message = 'This location is already being used at this time. Select another.', url = 'none')

            if content['musicid'] != '' and content['musicid'] != 'null' and content['musicid'] is not None:
                music_clash = session.query(music.musicname, music.composer, group.groupid).join(group).join(period).filter(period.periodid == thisperiod.periodid, music.musicid == content['musicid'], group.groupid != thisgroup.groupid).first()
                if music_clash is not None:
                    log('Group %s is already using this music %s %s' % (music_clash.groupid, music_clash.composer, music_clash.musicname))
                    session.rollback()
                    session.close()
                    return jsonify(message = 'This music is already being used at this time. You cannot schedule in this period.', url = 'none')



            foundfilled = False
            for p in content['objects']:
                if p['userid'] != '' and p['userid'] is not None:
                    foundfilled = True
                    log('Attempting to find user %s' % p['userid'])
                    playeruser = session.query(user).filter(user.userid == p['userid']).first()
                    #if the player is already playing in something, we have a clash and we have to exit completely. This may happen if multiple people are creating groups at the same time.
                    currentassignment = session.query(groupassignment.instrumentname, group.groupname, group.groupid).join(group).filter(groupassignment.userid == p['userid']).filter(group.periodid == thisperiod.periodid).first()
                    if currentassignment is not None:
                        #if the player is already playing in something, we have a clash and we have to exit completely. This may happen if multiple people are creating groups at the same time.
                        if currentassignment.groupid != thisgroup.groupid:
                            url = 'none'
                            message = ('Found a clash for %s. They are already playing %s in %s. Refresh the page and try again.' % (playeruser.firstname, currentassignment.instrumentname, currentassignment.groupname))
                            log(message)
                            session.rollback()
                            session.close()
                            return jsonify(message = message, url = url)
                    #if we found a player and no clash, we can assign this player to the group
                    if playeruser is None:
                        url = ('/user/' + str(thisuser.logonid) + '/')
                        session.rollback()
                        session.close()
                        return jsonify(message = 'Could not find one of your selected players in the database. Please refresh the page and try again.', url = url)
                    else:
                        #if the player is inactive or not attending camp at this time, they should never have been shown to the admin and chosen - this could happen if they were set to inactive while the admin had the page open
                        if playeruser.isactive != 1 or playeruser.arrival > thisperiod.starttime or playeruser.departure < thisperiod.endtime:
                            url = 'none'
                            message = ('The user %s %s is set to inactive and they cannot be assigned. Refresh the page and try again with a different user.' % (playeruser.firstname, playeruser.lastname))
                            session.rollback()
                            session.close()
                            return jsonify(message = message, url = url)
                        else:
                            playergroupassignment = groupassignment(userid = playeruser.userid, groupid = thisgroup.groupid, instrumentname = p['instrumentname'])
                            session.add(playergroupassignment)
                            
            #get the minimum level of this group
            mingrade = getgrouplevel(session,thisgroup,'min')
            maxgrade = getgrouplevel(session,thisgroup,'max')
            if content['submittype'] == 'autofill' and (mingrade == 0 or maxgrade == 0) and foundfilled != True:
                session.rollback()
                session.close()
                return jsonify(message = 'You cannot autofill with all empty players and an auto minimum or maximum level. Set the level or pick at least one player.', url = 'none')
            if thisgroup.status == 'Confirmed' and (thisgroup.periodid == '' or thisgroup.groupname == '' or thisgroup.locationid == ''):
                session.rollback()
                session.close()
                return jsonify(message = 'Confirmed groups must have a name, assigned period, assigned location and no empty player slots.', url = 'none')

            #----AUTOFILL SECTION----
            if content['submittype'] == 'autofill':
                log('AUTOFILL: User selected to autofill the group')
                log('AUTOFILL: Primary_only switch set to %s' % content['primary_only'])
                if content['periodid'] == '' or content['periodid'] is None:
                    session.rollback()
                    session.close()
                    return jsonify(message = 'You must have a period selected before autofilling.', url = 'none')
                else:
                    for i in getconfig('Instruments').split(","):
                        numberinstrument = getattr(thisgroup,i)
                        if int(numberinstrument) > 0:
                            log('AUTOFILL: Group has configured %s total players for instrument %s' % (numberinstrument, i))
                            currentinstrumentplayers = session.query(user).join(groupassignment).filter(groupassignment.groupid == thisgroup.groupid, groupassignment.instrumentname == i).all()
                            requiredplayers = int(numberinstrument) - len(currentinstrumentplayers)
                            log('AUTOFILL: Found %s current players for instrument %s' % (len(currentinstrumentplayers), i))
                            log('AUTOFILL: We need to autofill %s extra players for instrument %s' % (requiredplayers, i))
                            if requiredplayers > 0:
                                #get the userids of everyone that's already playing in something this period
                                everyone_playing_in_period_query = session.query(
                                        user.userid.label('everyone_playing_in_period_query_userid')
                                    ).join(groupassignment
                                    ).join(group
                                    ).join(period
                                    ).filter(
                                        period.periodid == thisgroup.periodid
                                    )

                                #combine the last query with another query, finding everyone that both plays an instrument that's found in thisgroup AND isn't in the list of users that are already playing in this period.
                                #The admin controls if the query allows non-primary instruments by the content['primary_only']
                                possible_players_query = session.query(
                                        user.userid.label('possible_players_query_userid')
                                    ).outerjoin(instrument
                                    ).filter(
                                        ~user.userid.in_(everyone_playing_in_period_query), 
                                        user.isactive == 1, 
                                        user.arrival <= thisperiod.starttime, 
                                        user.departure >= thisperiod.endtime
                                    ).filter(
                                        instrument.grade >= mingrade, 
                                        instrument.grade <= maxgrade, 
                                        instrument.instrumentname == i, 
                                        instrument.isactive == 1, 
                                        instrument.isprimary >= int(content['primary_only'])
                                    )

                                log('AUTOFILL: Found %s possible players of a requested %s for instrument %s.' % (len(possible_players_query.all()), requiredplayers, i))
                                #if we found at least one possible player
                                if len(possible_players_query.all()) > 0:
                                    #get the players that have already played in groups at this camp, and inverse it to get the players with playcounts of zero. Limit the query to just the spots we have left. These will be the people at the top of the list.
                                    already_played_query = session.query(
                                            user.userid
                                        ).join(groupassignment
                                        ).join(group
                                        ).filter(
                                            group.ismusical == 1, 
                                            groupassignment.instrumentname != 'Conductor', 
                                            user.userid.in_(possible_players_query)
                                        )

                                    #make a query that totals the nmber of times each potential user has played at camp.
                                    playcounts_subquery = session.query(
                                            user.userid.label('playcounts_userid'),
                                            func.count(user.userid).label("playcount")
                                        ).group_by(
                                            user.userid
                                        ).outerjoin(groupassignment, groupassignment.userid == user.userid
                                        ).outerjoin(group, group.groupid == groupassignment.groupid
                                        ).filter(
                                            user.userid.in_(possible_players_query),
                                            groupassignment.instrumentname != 'Conductor', 
                                            group.ismusical == 1, 
                                            group.periodid != None,
                                            group.groupid != thisgroup.groupid
                                        ).subquery()

                                    #if this group has assignment music
                                    if thisgroup.musicid is not None:
                                        #get a count of the amount of times that each potential player has played in this group
                                        musiccounts_subquery = session.query(
                                                user.userid.label('musiccounts_userid'),
                                                func.count(user.userid).label("musiccount")
                                            ).group_by(
                                                user.userid
                                            ).outerjoin(groupassignment, groupassignment.userid == user.userid
                                            ).outerjoin(group, group.groupid == groupassignment.groupid
                                            ).filter(
                                                user.userid.in_(possible_players_query),
                                                groupassignment.instrumentname != 'Conductor', 
                                                group.ismusical == 1,           
                                                group.periodid != None,
                                                group.groupid != thisgroup.groupid,
                                                #grab all groups that share a musicid with this group
                                                group.musicid == thisgroup.musicid
                                            ).subquery()
                                    else:
                                        #make a query with all userids, and 0s in the next column so the subsequent queries work (because no users have a playcount for this music)
                                        musiccounts_subquery = session.query(
                                                user.userid.label('musiccounts_userid'),
                                                sqlalchemy.sql.expression.literal_column("0").label("musiccount")
                                            ).filter(
                                                user.userid.in_(possible_players_query),
                                            ).subquery()

                                    #THIS ISN'T WORKING - GROUPCOUNT ALWAYS COMES UP AS NONE...
                                    #make a query we can use to total up the number of times each user has played in a group like this

                                    groupcounts_subquery = session.query(
                                            user.userid.label('groupcounts_userid'),
                                            func.count(user.userid).label("groupcount")
                                        ).group_by(
                                            user.userid
                                        ).outerjoin(groupassignment, groupassignment.userid == user.userid
                                        ).outerjoin(group, group.groupid == groupassignment.groupid
                                        ).filter(
                                            user.userid.in_(possible_players_query),
                                            groupassignment.instrumentname != 'Conductor', 
                                            group.ismusical == 1,           
                                            group.periodid != None,
                                            group.groupid != thisgroup.groupid,
                                            #grab all groups that share a name with this group, or have the same instrumentation of this group
                                            or_(
                                                group.groupname == thisgroup.groupname,
                                                and_(*[getattr(thisgroup,inst) == getattr(group,inst) for inst in instrumentlist])
                                            )
                                        ).subquery()

                                    #Put it all together!
                                    final_list = session.query(
                                            user.userid,
                                            user.firstname,
                                            user.lastname,
                                            playcounts_subquery.c.playcount,
                                            musiccounts_subquery.c.musiccount,
                                            groupcounts_subquery.c.groupcount
                                        ).outerjoin(playcounts_subquery, playcounts_subquery.c.playcounts_userid == user.userid
                                        ).outerjoin(musiccounts_subquery, musiccounts_subquery.c.musiccounts_userid == user.userid
                                        ).outerjoin(groupcounts_subquery, groupcounts_subquery.c.groupcounts_userid == user.userid
                                        ).filter(
                                            user.userid.in_(possible_players_query)
                                        ).order_by(
                                            #order by the number of times that the players have played this specific piece of music
                                            musiccounts_subquery.c.musiccount.nullsfirst(), 
                                            #then order by the number of times that the players have played in a group similar to this in name or instrumentation
                                            groupcounts_subquery.c.groupcount.nullsfirst(), 
                                            #then order by their total playcounts
                                            playcounts_subquery.c.playcount.nullsfirst()
                                        ).limit(requiredplayers
                                        ).all()
                                    log('AUTOFILL: Players in final list with playcounts:')
                                    #add groupassignments for the final player list
                                    for pl in final_list:
                                        log('AUTOFILL: Selected %s %s to play %s with totals - musiccount:%s groupcount:%s playcount:%s ' % (pl.firstname, pl.lastname, i, pl.musiccount, pl.groupcount, pl.playcount))
                                        playergroupassignment = groupassignment(userid = pl.userid, groupid = thisgroup.groupid, instrumentname = i)
                                        session.add(playergroupassignment)

            #Check for empty instrument slots if group is set to confirmed - if there are empties we have to switch it back to queued
            if thisgroup.status == 'Confirmed':
                for i in getconfig('Instruments').split(","):
                    log('This group has a required %s number of %s and an assigned %s.' % (i, getattr(thisgroup,i), session.query(user).join(groupassignment).filter(groupassignment.groupid == thisgroup.groupid, groupassignment.instrumentname == i).count()))
                    if int(session.query(user).join(groupassignment).filter(groupassignment.groupid == thisgroup.groupid, groupassignment.instrumentname == i).count()) != int(getattr(thisgroup,i)):
                        thisgroup.status = 'Queued'
                        try:
                            session.merge(thisgroup)
                            session.commit()
                        except Exception as ex:
                            log('failed to commit changes to database after a groupedit on group %s with error: %s' % (thisgroup.groupid,ex))
                        flash(u'Changes Partially Saved','message')
                        return jsonify(message = 'Your group is not confirmed because there are empty instrument slots. Your other changes have been saved.', url = '/user/' + str(thisuser.logonid) + '/group/' + str(thisgroup.groupid) + '/edit/')
            try:
                session.merge(thisgroup)
                session.commit()
            except Exception as ex:
                log('failed to commit changes to database after a groupedit on group %s with error: %s' % (thisgroup.groupid,ex))
            if content['submittype'] == 'autofill':
                url = '/user/' + str(thisuser.logonid) + '/group/' + str(thisgroup.groupid) + '/edit/'
                message = 'none'
                flash(u'Autofill Completed','message')
            elif content['submittype'] == 'save':
                if groupid == None:
                    url = '/user/' + str(thisuser.logonid) + '/group/' + str(thisgroup.groupid) + '/edit/'
                else:
                    url = 'none'
                message = 'none'
            else:
                url = '/user/' + str(thisuser.logonid) + '/group/' + str(thisgroup.groupid) + '/'
                message = 'none'
                if thisgroup.status == 'Confirmed':
                    flash(u'Group Confirmed and Scheduled','message')
                else:
                    flash(u'Changes Saved','success')
            session.close()
            return jsonify(message = message, url = url)
    
    except Exception as ex:
        log('Failed to execute %s for user %s %s with exception: %s.' % (request.method, thisuser.firstname, thisuser.lastname, ex))
        message = ('Failed to execute %s with exception: %s. Try refreshing the page and trying again or contact camp administration.' % (request.method, ex))
        session.rollback()
        session.close()
        if request.method == 'GET':
            return errorpage(thisuser,'Failed to display page with exception: %s.' % ex)
        else:
            return jsonify(message = message, url = 'none')
        
@app.route('/user/<logonid>/group/<groupid>/period/<periodid>/edit/', methods=['GET', 'POST', 'DELETE'])
def editgroupperiod(logonid,groupid,periodid):
    return editgroup(logonid,groupid,periodid)

@app.route('/user/<logonid>/grouphistory/')
def grouphistory(logonid):

    session = Session()
    #gets the data associated with this user
    thisuser = session.query(user).filter(user.logonid == logonid).first()
    if thisuser is None:
        return ('Did not find user in database. You have entered an incorrect URL address.')
    try:
        now = datetime.datetime.now() #get the time now
        groups = session.query(group.groupname, group.groupid, period.periodid, period.starttime, period.endtime, groupassignment.instrumentname, group.status, location.locationname).\
                    join(groupassignment).outerjoin(period).outerjoin(location).filter(groupassignment.userid == thisuser.userid, group.groupname != 'absent').order_by(period.starttime).all()
        log(groups)
        count = playcount(session, thisuser.userid)

        thisuserprimary = session.query(instrument.instrumentname).filter(instrument.userid == thisuser.userid, instrument.isprimary == 1).first().instrumentname
        total = 0
        number = 0
        for p in session.query(instrument.userid).filter(instrument.isactive == 1, instrument.isprimary == 1, instrument.instrumentname == thisuserprimary).group_by(instrument.userid).all():
            total = total + playcount(session, p.userid)
            number = number + 1
        average = "%.2f" % (float(total) / float(number))
        log('Found total number of %s players to be %s and plays by all of them totalling %s giving an average of %s' % (thisuserprimary, number, total, average))


        session.close()
        return render_template('grouphistory.html', \
                                thisuser=thisuser, \
                                groups = groups, \
                                campname=getconfig('Name'), favicon=getconfig('Favicon_URL'), instrumentlist=getconfig('Instruments').split(","), supportemailaddress=getconfig('SupportEmailAddress'), \
                                now=now, \
                                playcount=count, \
                                average=average, \
                                thisuserprimary=thisuserprimary, \
                                )
    except Exception as ex:
        log('Failed to execute %s for user %s %s with exception: %s.' % (request.method, thisuser.firstname, thisuser.lastname, ex))
        message = ('Failed to execute %s with exception: %s. Try refreshing the page and trying again or contact camp administration.' % (request.method, ex))
        session.rollback()
        session.close()
        if request.method == 'GET':
            return errorpage(thisuser,'Failed to display page with exception: %s.' % ex)
        else:
            return jsonify(message = message, url = 'none')

@app.route('/user/<logonid>/musiclibrary/')
def musiclibrary(logonid):

    session = Session()
    #gets the data associated with this user
    thisuser = session.query(user).filter(user.logonid == logonid).first()
    if thisuser is None:
        return ('Did not find user in database. You have entered an incorrect URL address.')
    try:
        musics = session.query(music).all()
        grouptemplates = session.query(grouptemplate).filter(grouptemplate.size == 'S').all()
        session.close()
        return render_template('musiclibrary.html', \
                                thisuser=thisuser, \
                                musics=musics, \
                                grouptemplates=grouptemplates, \
                                campname=getconfig('Name'), favicon=getconfig('Favicon_URL'), instrumentlist=getconfig('Instruments').split(","), supportemailaddress=getconfig('SupportEmailAddress'), \
                                )
    except Exception as ex:
        log('Failed to execute %s for user %s %s with exception: %s.' % (request.method, thisuser.firstname, thisuser.lastname, ex))
        message = ('Failed to execute %s with exception: %s. Try refreshing the page and trying again or contact camp administration.' % (request.method, ex))
        session.rollback()
        session.close()
        if request.method == 'GET':
            return errorpage(thisuser,'Failed to display page with exception: %s.' % ex)
        else:
            return jsonify(message = message, url = 'none')

@app.route('/user/<logonid>/musiclibrary/details/<musicid>/')
def musicdetails(logonid,musicid):

    session = Session()
    #gets the data associated with this user
    thisuser = session.query(user).filter(user.logonid == logonid).first()
    if thisuser is None:
        return ('Did not find user in database. You have entered an incorrect URL address.')
    try:
        thismusic = session.query(music).filter(music.musicid == musicid).first()
        if thismusic is None:
            session.close()
            return errorpage(thisuser,'The music you selected does not exist in the database.')
        thisuserinstruments = session.query(instrument).filter(instrument.userid == thisuser.userid, instrument.isactive == 1).all()
        canplay = False
        for i in thisuserinstruments:
            for j in getconfig('Instruments').split(","):
                if i.instrumentname == j and getattr(thismusic,j) > 0:
                    canplay = True
                    break
            if canplay == True:
                break
        grouptemplates = session.query(grouptemplate).filter(grouptemplate.size == 'S').all()
        playcount = session.query(group).filter(group.musicid == thismusic.musicid).count()
        session.close()
        return render_template('musicdetails.html', \
                                thisuser=thisuser, \
                                thismusic=thismusic, \
                                grouptemplates=grouptemplates, \
                                canplay=canplay, \
                                campname=getconfig('Name'), favicon=getconfig('Favicon_URL'), instrumentlist=getconfig('Instruments').split(","), supportemailaddress=getconfig('SupportEmailAddress'), \
                                playcount=playcount, \
                                )
    except Exception as ex:
        log('Failed to execute %s for user %s %s with exception: %s.' % (request.method, thisuser.firstname, thisuser.lastname, ex))
        message = ('Failed to execute %s with exception: %s. Try refreshing the page and trying again or contact camp administration.' % (request.method, ex))
        session.rollback()
        session.close()
        if request.method == 'GET':
            return errorpage(thisuser,'Failed to display page with exception: %s.' % ex)
        else:
            return jsonify(message = message, url = 'none')

@app.route('/user/<logonid>/musiclibrary/new/', methods=['GET', 'POST'])
def newmusic(logonid):

    session = Session()
    #gets the data associated with this user
    thisuser = session.query(user).filter(user.logonid == logonid).first()
    if thisuser is None:
        return ('Did not find user in database. You have entered an incorrect URL address.')
    try:
        if request.method == 'GET':
            grouptemplates = session.query(grouptemplate).all()
            grouptemplates_serialized = [i.serialize for i in grouptemplates]
            return render_template('newmusic.html', \
                                    thisuser=thisuser, \
                                    grouptemplates=grouptemplates, \
                                    grouptemplates_serialized=grouptemplates_serialized, \
                                    instrumentlist_string=getconfig('Instruments'), \
                                    campname=getconfig('Name'), favicon=getconfig('Favicon_URL'), instrumentlist=getconfig('Instruments').split(","), supportemailaddress=getconfig('SupportEmailAddress'), \
                                    )

        if request.method == 'POST':
            #format the packet received from the server as JSON
            content = request.json
            found_non_zero = False
            for i in getconfig('Instruments').split(","):
                if content[i] != 0 and content[i] != '' and content[i] != '0' and content[i] is not None:
                    found_non_zero = True
            if not found_non_zero:
                session.rollback()
                session.close()
                return jsonify(message = 'You cannot submit music without instrumentation.', url = 'none')
            thismusic = music()
            log('New Music: Submitted by user %s %s' % (thisuser.firstname, thisuser.lastname))
            for key,value in content.items():
                if (value is None or value == 'null' or value == '') and key == 'composer':
                    session.rollback()
                    session.close()
                    return jsonify(message = 'You must enter a composer', url = 'none')
                if (value is None or value == 'null' or value == '') and key == 'name':
                    session.rollback()
                    session.close()
                    return jsonify(message = 'You must enter a name', url = 'none')
                log('New Music: setting %s to be %s' % (key,value))
                setattr(thismusic,key,value)

            #try to find a grouptemplate that matches this instrumentation
            matchingtemplate = session.query(grouptemplate).filter(*[getattr(thismusic,i) == getattr(grouptemplate,i) for i in instrumentlist]).first()
            if matchingtemplate is not None:
                log('New Music: Found a template matching this music: %s' % matchingtemplate.grouptemplatename)
                thismusic.grouptemplateid = matchingtemplate.grouptemplateid
            
            session.add(thismusic)
            session.commit()
            log('New Music: Successfully created')
            url = ('/user/' + str(thisuser.logonid) + '/musiclibrary/')
            session.close()
            flash(u'New Music Accepted', 'success')
            return jsonify(message = 'none', url = url)

    except Exception as ex:
        log('Failed to execute %s for user %s %s with exception: %s.' % (request.method, thisuser.firstname, thisuser.lastname, ex))
        message = ('Failed to execute %s with exception: %s. Try refreshing the page and trying again or contact camp administration.' % (request.method, ex))
        session.rollback()
        session.close()
        if request.method == 'GET':
            return errorpage(thisuser,'Failed to display page with exception: %s.' % ex)
        else:
            return jsonify(message = message, url = 'none')

#Handles the group request page. If a user visits the page, it gives them a form to create a new group request. Pressing submit 
#sends a post containing configuration data. Their group request is queued until an adminsitrator approves it and assigns it to 
#a period.
@app.route('/user/<logonid>/grouprequest/', methods=['GET', 'POST'])
def grouprequest(logonid,periodid=None,musicid=None):
    
    session = Session()
    #gets the data associated with this user
    thisuser = session.query(user).filter(user.logonid == logonid).first()
    if thisuser is None:
        return ('Did not find user in database. You have entered an incorrect URL address.')
    try:
        log('GROUPREQUEST: Group request page requested by user %s %s using method %s' % (thisuser.firstname, thisuser.lastname, request.method))

        today = datetime.datetime.combine(datetime.date.today(), datetime.time.min) #get today's date
        intwodays = today + datetime.timedelta(days=2)
        now = datetime.datetime.now() #get the time now
        #if this camper is inactive, has not arrived at camp yet, or is departing before the end of tomorrow
        if (thisuser.isactive != 1) and periodid is None:
            session.close()
            return errorpage(thisuser,'Your account is currently set to inactive. Inactive users cannot request groups. Is this is a mistake, navigate to your settings and set yourself to active.')
        if (thisuser.departure < intwodays) and periodid is None:
            session.close()
            return errorpage(thisuser,"You are set to depart camp in less than one days' time, so you cannot request a group. If this is incorrect, you can change your departure time in your settings.")
        #find the instruments this user plays
        thisuserinstruments = session.query(instrument).filter(instrument.userid == thisuser.userid, instrument.isactive == 1).all()
        thisuserinstruments_serialized = [i.serialize for i in thisuserinstruments]

        #check if this user is really a conductor and actually requested a conductorpage for a specific period
        if thisuser.isconductor == 1 and periodid is not None:
            conductorpage = True
            thisperiod = session.query(period).filter(period.periodid == periodid).first()
            if thisperiod is None:
                return ('Did not find period in database. Something has gone wrong.')
        elif thisuserinstruments is None:
            session.close()
            return errorpage(thisuser,'Failed to display page with exception: %s.' % ex)
        else:
            conductorpage = False
            thisperiod = None

        #if this user isn't a conductor and/or they didn't request the conductor page and they've already surpassed their group-per-day limit, deny them.
        if conductorpage == False:
            if thisuser.grouprequestcount == 0 or thisuser.grouprequestcount == None or thisuser.grouprequestcount == '':
                thisuser.grouprequestcount = 0
                alreadyrequestedratio = 0
            log('GROUPREQUEST: User has requested %s groups' % thisuser.grouprequestcount)
            log('GROUPREQUEST: Maximum allowance is %s plus an extra %s per day' % (getconfig('BonusGroupRequests'), getconfig('DailyGroupRequestLimit')))
            log('GROUPREQUEST: User arrived at camp at %s.' % thisuser.arrival)
            log('GROUPREQUEST: User is allowed total %s requests.' % (((now - thisuser.arrival).days + 2) * float(getconfig('DailyGroupRequestLimit')) + float(getconfig('BonusGroupRequests'))))
            if thisuser.grouprequestcount >= (((now - thisuser.arrival).days + 2) * float(getconfig('DailyGroupRequestLimit')) + float(getconfig('BonusGroupRequests'))):
                log('GROUPREQUEST: This user is denied access to request another group.')
                session.close()
                return errorpage(thisuser,"You have requested %s groups throughout the camp, and you're allowed %s per day (as well as %s welcome bonus requests!). You've reached your limit for today. Come back tomorrow!" % \
                    (thisuser.grouprequestcount, getconfig('DailyGroupRequestLimit'), getconfig('BonusGroupRequests')))
        
        #The below runs when a user visits the grouprequest page
        if request.method == 'GET':
        
            #if this is the conductorpage, the user will need a list of the locations that are not being used in the period selected
            if conductorpage == True:
                locations_used_query = session.query(location.locationid).join(group).join(period).filter(period.periodid == periodid)
                locations = session.query(location).filter(~location.locationid.in_(locations_used_query)).all()
                musics_used_query = session.query(music.musicid).join(group).join(period).filter(period.periodid == periodid)
                musics = session.query(music).filter(~music.musicid.in_(musics_used_query)).all()
            else: 
                locations = None
                musics = session.query(music).filter(or_(*[(getattr(music,getattr(i,'instrumentname')) > 0) for i in session.query(instrument.instrumentname).filter(instrument.userid == thisuser.userid, instrument.isactive == 1)])).all()
        
            musics_serialized = [i.serialize for i in musics]
            #checks if the requested music exists and sets it up for the page
            if musicid is not None:
                requestedmusic = session.query(music).filter(music.musicid == musicid).first()
                if requestedmusic is None:
                    return errorpage(thisuser,"You have requested music that could not be found in the database. Talk to the administrator." % (thisuser.grouprequestcount, getconfig('DailyGroupRequestLimit'), (now - datetime.datetime.strptime(getconfig('StartTime'), '%Y-%m-%d %H:%M')).days))
            else:
                requestedmusic = None

            if conductorpage == True:
                #Finds all players who aren't already playing in this period
                playersPlayingInPeriod = session.query(user.userid).join(groupassignment).join(group).filter(group.periodid == periodid)
                playersdump = session.query(user.userid,user.firstname,user.lastname,instrument.instrumentname,instrument.grade,instrument.isprimary).\
                    join(instrument).filter(~user.userid.in_(playersPlayingInPeriod), user.isactive == 1, user.arrival <= thisperiod.starttime, user.departure >= thisperiod.endtime).all()
            else:
                #find all the instruments that everyone plays and serialize them to prepare to inject into the javascript
                playersdump = session.query(user.userid,user.firstname,user.lastname,instrument.instrumentname,instrument.grade,instrument.isprimary).\
                    join(instrument).filter(user.userid != thisuser.userid, user.isactive == 1, instrument.isactive == 1).all()
            playersdump_serialized = []
            for p in playersdump:
                playersdump_serialized.append({'userid': p.userid, 'firstname': p.firstname, 'lastname': p.lastname,
                                                'instrumentname': p.instrumentname, 'grade': p.grade, 'isprimary': p.isprimary})

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
            session.close()
            return render_template('grouprequest.html', \
                                thisuser=thisuser, \
                                thisuserinstruments=thisuserinstruments, \
                                thisuserinstruments_serialized=thisuserinstruments_serialized, \
                                playerlimit = int(getconfig('GroupRequestPlayerLimit')), \
                                grouptemplates = grouptemplates, \
                                grouptemplates_serialized=grouptemplates_serialized, \
                                campname=getconfig('Name'), favicon=getconfig('Favicon_URL'), instrumentlist=getconfig('Instruments').split(","), supportemailaddress=getconfig('SupportEmailAddress'), \
                                instrumentlist_string=getconfig('Instruments'), \
                                playersdump_serialized=playersdump_serialized, \
                                conductorpage=conductorpage, \
                                thisperiod=thisperiod, \
                                locations=locations, \
                                musics=musics, \
                                musics_serialized=musics_serialized, \
                                requestedmusic=requestedmusic, \
                                )

        #The below runs when a user presses "Submit" on the grouprequest page. It creates a group object with the configuraiton selected by 
        #the user, and creates groupassignments for all players they selected (and the user themselves)
        if request.method == 'POST':
            instrumentlist = getconfig('Instruments').split(",")
            #format the packet received from the server as JSON
            content = request.json
            session = Session()
            log('GROUPREQUEST: Grouprequest received. Whole content of JSON returned is: %s' % content)
            #if we received too many players, send the user an error
            if (content['musicid'] == '' or content['musicid'] is None or content['musicid'] == 'null') and (len(content['objects']) > int(getconfig('GroupRequestPlayerLimit'))) and conductorpage == False:
                session.rollback()
                session.close()
                return jsonify(message = 'You have entered too many players. You may only submit grouprequests of players %s or less.' % getconfig('GroupRequestPlayerLimit'), url = 'none')
            if len(content['objects']) == 0:
                session.rollback()
                session.close()
                return jsonify(message = 'You must have at least one player in the group', url = 'none')
            #establish the 'grouprequest' group object. This will be built up from the JSON packet, and then added to the database
            #a minimumlevel and maximumlevel of 0 indicates that they will be automatically be picked on group confirmation
            grouprequest = group(ismusical = 1, requesteduserid = thisuser.userid, requesttime = datetime.datetime.now(), minimumlevel = 0, maximumlevel = 0)
            if content['musicid'] is not None and content['musicid'] != '':
                grouprequest.musicid = content['musicid']
            else:
                grouprequest.musicwritein = content['musicwritein']
            #if the conductorpage is false, we need to set the status to queued
            if conductorpage == False:
                grouprequest.status = "Queued"
            #if the conductorpage is true, we expect to also receive a locationid from the JSON packet, so we add it to the grouprequest, we also confirm the request
            if conductorpage == True:
                if content['locationid'] == '':
                    session.rollback()
                    session.close()
                    return jsonify(message = 'You must select a location for this group', url = 'none')
                grouprequest.locationid = content['locationid']
                grouprequest.status = "Queued"

            #for each instrument
            for i in instrumentlist:
                #set a default value of 0
                setattr(grouprequest,i,0)
                #iterate over the objects in the request corresponding with that instrument, and increment the counter for each
                for p in content['objects']:
                    if p['instrumentname'] == i:

                        #if it has a corresponding user, check that that user exists
                        if p['userid'] != 'null' and p['userid'] != '':
                            #try to find a user that matches this id
                            puser = session.query(user).filter(user.userid == p['userid']).first()
                            #if we don't find one, this grouprequset is a failiure
                            if puser is None:
                                log('Input error. user %s does not exist in the database.' % p['userid'])
                                session.rollback()
                                session.close()
                                return jsonify(message = 'Input error. One of the sent users does not exist in the database.', url = 'none')
                            #if we find an inactive user, it's also a failure
                            elif puser.isactive != 1:
                                log('User %s %s is inactive. Cannot accept this group request.' % (puser.firstname, puser.lastname))
                                session.rollback()
                                session.close()
                                return jsonify(message = 'A selected user is inactive. Cannot accept this group request.', url = 'none')

                        #increment the instrument counter
                        setattr(grouprequest,i,getattr(grouprequest,i) + 1)
                log('Instrument %s is value %s' % (i, getattr(grouprequest,i)))
                    
            #run the getgroupname function, which logically names the group
            grouprequest.groupname = getgroupname(session,grouprequest)

            #if we are on the conductorpage, assign it to the period the user submitted
            if conductorpage == True:
                grouprequest.periodid = thisperiod.periodid     
        
            #--------MATCHMAKING SECTION-----------
            #try to find an existing group request with the same music and instrumentation configuration as the request
            musicstatus = None
            if (content['musicid'] != '' and content['musicid'] != 'null' and content['musicid'] != None):
                log('MATCHMAKING: Found that user has requested the music to be %s' % content['musicid'])
                matchinggroups = session.query(group).filter(or_(group.musicid == content['musicid'], group.musicwritein == content['musicwritein']), group.iseveryone == None, group.ismusical == 1, group.periodid == None, *[getattr(grouprequest,i) == getattr(group,i) for i in instrumentlist]).order_by(group.requesttime).all()
                musicstatus = 'musicid'
                musicvalue = content['musicid']
            elif (content['musicwritein'] != '' and content['musicwritein'] != 'null' and content['musicwritein'] != None):
                log('MATCHMAKING: Found that user has written in %s for their music' % content['musicwritein'])
                matchinggroups = session.query(group).filter(group.musicwritein == content['musicwritein'], group.iseveryone == None, group.ismusical == 1, group.periodid == None, *[getattr(grouprequest,i) == getattr(group,i) for i in instrumentlist]).order_by(group.requesttime).all()
                musicstatus = 'musicwritein'
                musicvalue = content['musicwritein']
            else:
                log('MATCHMAKING: User did not specify any music in their request')
                matchinggroups = session.query(group).filter(group.iseveryone == None, group.ismusical == 1, group.periodid == None, *[getattr(grouprequest,i) == getattr(group,i) for i in instrumentlist]).order_by(group.requesttime).all()
            Match = False
            #if we found at least one matching group
            if matchinggroups is not None:
                #check each group that matched the instrumentation for player slots
                for m in matchinggroups:
                
                    log("MATCHMAKING: Instrumentation and music match found, requested by %s at time %s" % (m.requesteduserid, m.requesttime))
                    #check if this group is a suitable level
                    groupmin = getgrouplevel(session,m,'min')
                    groupmax = getgrouplevel(session,m,'max')
                    #for each specific player in the request, check if there's a free spot in the matching group
                    #for each player in the group request
                    clash = False
                    for p in content['objects']:
                        #if it's a named player, not a blank drop-down
                        if p['userid'] != 'null' and p['userid'] != '':
                            #find a list of players that are already assigned to this group, and play the instrument requested by the grouprequest
                            instrumentclash = session.query(groupassignment).filter(groupassignment.instrumentname == p['instrumentname'],\
                                groupassignment.groupid == m.groupid).all()
                            #if the list of players already matches the group instrumentation for this instrument, this match fails and break out
                            if instrumentclash is not None and instrumentclash != []:
                                if len(instrumentclash) >= getattr(m, p['instrumentname']):
                                    log('MATCHMAKING: Found group not suitable, does not have an open slot for this player.')
                                    clash = True
                                    break
                            #find out if this group's level is unsuitable for this player on this instrument and make a clash if they are
                            playerinstrument = session.query(instrument).filter(instrument.userid == p['userid'], instrument.instrumentname == p['instrumentname']).first()
                            if groupmin < playerinstrument.grade < groupmax:
                                log('MATCHMAKING: Found group not suitable, the current players are of unsuitable level. Current min: %s, Current max: %s, this players level: %s.' % (groupmin,groupmax,playerinstrument.grade))
                                clash = True
                                break
                            #find out if this player is already playing in the found group and make a clash if they are
                            playerclash = session.query(groupassignment).filter(groupassignment.userid == p['userid'], groupassignment.groupid == m.groupid).all()
                            if playerclash is not None and playerclash != []:
                                log('MATCHMAKING: Found group not suitable, already has this player playing in it. Found the following group assignment: %s' % playerclash)
                                clash = True
                                break
                    #if we didn't have a clash while iterating over this group, we have a match! set the grouprequest group to be the old group and break out
                    if clash == False:
                        log('MATCHMAKING: Match found. Adding the players in this request to the already formed group.')
                        grouprequest = m
                        #if the original group doesn't have music already assigned, we can assign it music from the user request
                        if musicstatus is not None:
                            setattr(grouprequest,musicstatus,musicvalue)
                            if musicstatus == 'musicid':
                                musicrequest = session.query(music).filter(music.musicid == content['musicid']).first()
                                grouprequest.addtolog('Setting group music to %s: %s (Requested by %s %s)' % (musicrequest.composer,musicrequest.musicname, thisuser.firstname, thisuser.lastname))
                            elif musicstatus == 'musicwritein':
                                grouprequest.addtolog('Setting group music to be custom value "%s" (Requested by %s %s)' % (content['musicwritein'], thisuser.firstname, thisuser.lastname))
                        session.merge(grouprequest)
                        Match = True
                        break
            #if we didn't get a match, we need to create the grouprequest, we won't be using an old one
            if Match == False:
                log('MATCHMAKING: No group already exists with the correct instrumentation slots. Creating a new group.')
                #add the grouprequest to the database
                session.add(grouprequest)
                grouprequest.addtolog('Group initially created (Requested by %s %s)' % (thisuser.firstname,thisuser.lastname))
            #If we have got to here, the user successfully created their group (or was matchmade). We need to increment their total.
            if not conductorpage:
                thisuser.grouprequestcount = thisuser.grouprequestcount + 1
                log('%s %s has now made %s group requests' % (thisuser.firstname, thisuser.lastname, thisuser.grouprequestcount))
            #for each player object in the players array in the JSON packet
            for p in content['objects']:
                #if we are on the conductorpage, you cannot submit blank players. Give the user an error and take them back to their home.
                if (p['userid'] == 'null' or p['userid'] == '') and conductorpage == True:
                    url = ('/user/' + str(thisuser.logonid) + '/')
                    session.rollback()
                    session.close()
                    return jsonify(message = 'You cannot have any empty player boxes in the group, because this is the conductor version of the group request page.', url = 'none')
                #if the playerid is not null, we create a groupassignment for them and bind it to this group
                if p['userid'] != 'null' and p['userid'] != '':
                    playeruser = session.query(user).filter(user.userid == p['userid']).first()
                    if playeruser is not None:
                        playergroupassignment = groupassignment(userid = playeruser.userid, groupid = grouprequest.groupid, instrumentname = p['instrumentname'])
                        session.add(playergroupassignment)
                        grouprequest.addtolog('Adding player %s %s to group with instrument %s (Requested by %s %s)' % (playeruser.firstname,playeruser.lastname,p['instrumentname'],thisuser.firstname,thisuser.lastname))
                    else:
                        url = ('/user/' + str(thisuser.logonid) + '/')
                        session.rollback()
                        session.close()
                        return jsonify(message = 'Could not find one of your selected players in the database. Please refresh the page and try again.', url = url)
                #if none of the above are satisfied - that's ok. you're allowed to submit null playernames in the user request page, these will be 
                #allocated by the admin when the group is confirmed.
        
            #create the group and the groupassinments configured above in the database
            session.merge(thisuser)
            session.commit()
            #send the URL for the group that was just created to the user, and send them to that page
            url = ('/user/' + str(thisuser.logonid) + '/group/' + str(grouprequest.groupid) + '/')
            log('Sending user to URL: %s' % url)
            session.close()
            flash(u'Request Successful', 'success')
            return jsonify(message = 'none', url = url)

    except Exception as ex:
        log('Failed to execute %s for user %s %s with exception: %s.' % (request.method, thisuser.firstname, thisuser.lastname, ex))
        message = ('Failed to execute %s with exception: %s. Try refreshing the page and trying again or contact camp administration.' % (request.method, ex))
        session.rollback()
        session.close()
        if request.method == 'GET':
            return errorpage(thisuser,'Failed to display page with exception: %s.' % ex)
        else:
            return jsonify(message = message, url = 'none')
        

@app.route('/user/<logonid>/grouprequest/conductor/<periodid>/', methods=['GET', 'POST'])
def conductorgrouprequest(logonid,periodid):
    
    session = Session()
    #gets the data associated with this user
    thisuser = session.query(user).filter(user.logonid == logonid).first()
    if thisuser is None:
        return ('Did not find user in database. You have entered an incorrect URL address.')
    if thisuser.isconductor != 1:
        return ('You are not a conductor and cannot visit this page.')
    session.close()
    return grouprequest(logonid,periodid,None)

@app.route('/user/<logonid>/grouprequest/music/<musicid>/', methods=['GET', 'POST'])
def musicgrouprequest(logonid,musicid):
    return grouprequest(logonid,None,musicid)

#This page is used by an "announcer" to edit the announcement that users see when they open their homes
@app.route('/user/<logonid>/announcement/', methods=['GET', 'POST'])
def announcementpage(logonid):
    
    session = Session()
    #gets the data associated with this user
    thisuser = session.query(user).filter(user.logonid == logonid).first()
    if thisuser is None:
        return ('Did not find user in database. You have entered an incorrect URL address.')
    try:
        if thisuser.isannouncer != 1:
            session.close()
            return 'You do not have permission to view this page'
        else:
        
            #if this is a user requesting the page
            if request.method == 'GET':
                #get the current announcement
                currentannouncement = session.query(announcement).order_by(desc(announcement.creationtime)).first()
                session.close()            
                return render_template('announcement.html', \
                                        currentannouncement=currentannouncement, \
                                        thisuser=thisuser, \
                                        campname=getconfig('Name'), favicon=getconfig('Favicon_URL'), instrumentlist=getconfig('Instruments').split(","), supportemailaddress=getconfig('SupportEmailAddress'), \
                                        )
 
            #if this is a user that just pressed submit
            if request.method == 'POST':
                #create a new announcement object with the submitted content, and send it
                newannouncement = announcement(content = request.json['content'], creationtime = datetime.datetime.now())
                session.add(newannouncement)
                session.commit()
                url = ('/user/' + str(thisuser.logonid) + '/')
                session.close()
                #send the user back to their home
                flash(u'Changes Saved', 'success')
                return jsonify(message = 'none', url = url)

    except Exception as ex:
        log('Failed to execute %s for user %s %s with exception: %s.' % (request.method, thisuser.firstname, thisuser.lastname, ex))
        message = ('Failed to execute %s with exception: %s. Try refreshing the page and trying again or contact camp administration.' % (request.method, ex))
        session.rollback()
        session.close()
        if request.method == 'GET':
            return errorpage(thisuser,'Failed to display page with exception: %s.' % ex)
        else:
            return jsonify(message = message, url = 'none')

#This page shows the queued groups, it is only accessible by the admin
@app.route('/user/<logonid>/groupqueue/', methods=['GET', 'POST'])
def groupqueue(logonid):
    session = Session()
    #gets the data associated with this user
    thisuser = session.query(user).filter(user.logonid == logonid).first()
    if thisuser is None:
        return ('Did not find user in database. You have entered an incorrect URL address.')
    try:
        if thisuser.isadmin != 1:
            session.close()
            return 'You do not have permission to view this page'
        else:
            if request.method == 'GET':
                queuedgroups = session.query(group.groupid, group.requesttime, group.status, group.groupname, period.periodname, period.starttime, period.endtime, user.firstname, user.lastname).\
                    outerjoin(period).outerjoin(user).filter(group.status == "Queued", user.isactive == 1).order_by(group.requesttime).all()
                log("Found %s queued groups to show the user" % len(queuedgroups))
                session.close()
                return render_template('groupqueue.html', \
                                        queuedgroups=queuedgroups, \
                                        thisuser=thisuser, \
                                        campname=getconfig('Name'), favicon=getconfig('Favicon_URL'), instrumentlist=getconfig('Instruments').split(","), supportemailaddress=getconfig('SupportEmailAddress'), \
                                        )
            if request.method == 'POST':
                thisgroup = session.query(group).filter(group.groupid == request.json['groupid']).first()
                if thisgroup is None:
                    session.rollback()
                    session.close()
                    return jsonify(message = 'Could not find this group in the database. Refresh your page and try again.', success = 'false')
                else:
                    thisgroup.periodid = None
                    thisgroup.locationid = None
                    session.merge(thisgroup)
                    session.commit()
                    session.close()
                    return jsonify(message = 'none', success = 'true')

    except Exception as ex:
        log('Failed to execute %s for user %s %s with exception: %s.' % (request.method, thisuser.firstname, thisuser.lastname, ex))
        message = ('Failed to execute %s with exception: %s. Try refreshing the page and trying again or contact camp administration.' % (request.method, ex))
        session.rollback()
        session.close()
        if request.method == 'GET':
            return errorpage(thisuser,'Failed to display page with exception: %s.' % ex)
        else:
            return jsonify(message = message, url = 'none')

#This page is for creating a public event. It comes up as an option for adminsitrators on their homes
@app.route('/user/<logonid>/publicevent/<periodid>/', methods=['GET', 'POST'])
def publiceventpage(logonid,periodid):

    session = Session()
    #gets the data associated with this user
    thisuser = session.query(user).filter(user.logonid == logonid).first()
    if thisuser is None:
        return ('Did not find user in database. You have entered an incorrect URL address.')
    try:
        if thisuser.isadmin != 1:
            session.close()
            return errorpage(thisuser,'You do not have permission to view this page')
        else:
        
            #if the user requested the public event page
            if request.method == 'GET':
                #get the locations that aren't being used yet for this period
                locations_used_query = session.query(location.locationid).join(group).join(period).filter(period.periodid == periodid)
                locations = session.query(location).filter(~location.locationid.in_(locations_used_query)).all()
                #get the period details to display to the user on the page
                thisperiod = session.query(period).filter(period.periodid == periodid).first()
                session.close()            
                return render_template('publicevent.html', \
                                        locations=locations, \
                                        thisuser=thisuser, \
                                        thisperiod=thisperiod, \
                                        campname=getconfig('Name'), favicon=getconfig('Favicon_URL'), instrumentlist=getconfig('Instruments').split(","), supportemailaddress=getconfig('SupportEmailAddress'), \
                                        )
        
            #if the user pressed "submit" on the public event page
            if request.method == 'POST':
                if request.json['locationid'] == '' or request.json['groupname'] == '':
                    session.rollback()
                    url = ('none')
                    session.close()
                    return jsonify(message = 'Submission failed. You must submit both an event name and location.', url = url)
                event = group(periodid = periodid, iseveryone = 1, groupname =  request.json['groupname'], requesteduserid = thisuser.userid,\
                    ismusical = 0, locationid = request.json['locationid'], status = "Confirmed", requesttime = datetime.datetime.now())
                if request.json['groupdescription'] and request.json['groupdescription'] != '':
                    event.groupdescription = request.json['groupdescription']
                session.add(event)
                session.commit()
                url = ('/user/' + str(thisuser.logonid) + '/group/' + str(event.groupid) + '/')
                session.close()
                flash(u'Event Created', 'success')
                return jsonify(message = 'none', url = url)

    except Exception as ex:
        log('Failed to execute %s for user %s %s with exception: %s.' % (request.method, thisuser.firstname, thisuser.lastname, ex))
        message = ('Failed to execute %s with exception: %s. Try refreshing the page and trying again or contact camp administration.' % (request.method, ex))
        session.rollback()
        session.close()
        if request.method == 'GET':
            return errorpage(thisuser,'Failed to display page with exception: %s.' % ex)
        else:
            return jsonify(message = message, url = 'none')

#this page is the full report for any given period
@app.route('/user/<logonid>/period/<periodid>/')
def periodpage(logonid,periodid):
    session = Session()
    #gets the data associated with this user
    thisuser = session.query(user).filter(user.logonid == logonid).first()
    if thisuser is None:
        return ('Did not find user in database. You have entered an incorrect URL address.')
    try:
        thisperiod = session.query(period).filter(period.periodid == periodid).first()
        #find any public events on during this period
        publicevents = session.query(
                group.groupname,
                group.groupid,
                location.locationname,
                group.groupdescription
            ).join(location
            ).filter(
                group.iseveryone == 1, 
                group.periodid == periodid
            ).all()
        #start with the players that are playing in groups in the period
        players = session.query(
                user.userid, 
                user.firstname, 
                user.lastname, 
                period.starttime, 
                period.endtime, 
                group.groupname,
                groupassignment.instrumentname, 
                location.locationname, 
                groupassignment.groupid
            ).join(groupassignment
            ).join(group
            ).join(period
            ).outerjoin(location
            ).filter(
                user.arrival <= thisperiod.starttime, 
                user.departure >= thisperiod.endtime, 
                group.periodid == thisperiod.periodid, 
                group.status == 'Confirmed', 
                group.groupname != 'absent'
            ).order_by(
                group.groupid,
                groupassignment.instrumentname
            ).all()
        #grab just the userids of those players to be used in the next query
        players_in_groups_query = session.query(user.userid).\
            join(groupassignment).join(group).join(period).\
            filter(user.isactive == 1, user.arrival <= thisperiod.starttime, user.departure >= thisperiod.endtime, group.periodid == thisperiod.periodid, group.status == 'Confirmed')
        #find all other players to be displayed to the user
        unallocatedplayers = session.query(user.userid, user.firstname, user.lastname, instrument.instrumentname).join(instrument).filter(~user.userid.in_(players_in_groups_query), user.isactive == 1, user.arrival <= thisperiod.starttime, user.departure >= thisperiod.endtime, instrument.isprimary == 1).all()
        unallocatedplayers_query = session.query(user.userid).join(instrument).filter(~user.userid.in_(players_in_groups_query), user.isactive == 1, user.arrival <= thisperiod.starttime, user.departure >= thisperiod.endtime, instrument.isprimary == 1)
        nonplayers = session.query(user.userid, user.firstname, user.lastname, sqlalchemy.sql.expression.literal_column("'Non Player'").label("instrumentname")).filter(~user.userid.in_(players_in_groups_query), ~user.userid.in_(unallocatedplayers_query), user.isactive == 1, user.arrival <= thisperiod.starttime, user.departure >= thisperiod.endtime).all()
        thisperiod = session.query(period).filter(period.periodid == periodid).first()
        session.close()
        return render_template('periodpage.html', \
                                players=players, \
                                unallocatedplayers=unallocatedplayers, \
                                publicevents=publicevents, \
                                nonplayers=nonplayers, \
                                campname=getconfig('Name'), favicon=getconfig('Favicon_URL'), instrumentlist=(getconfig('Instruments') + ',Non Player').split(","), supportemailaddress=getconfig('SupportEmailAddress'), \
                                thisuser=thisuser, \
                                thisperiod=thisperiod, \
                                )
    except Exception as ex:
        log('Failed to execute %s for user %s %s with exception: %s.' % (request.method, thisuser.firstname, thisuser.lastname, ex))
        message = ('Failed to execute %s with exception: %s. Try refreshing the page and trying again or contact camp administration.' % (request.method, ex))
        session.rollback()
        session.close()
        if request.method == 'GET':
            return errorpage(thisuser,'Failed to display page with exception: %s.' % ex)
        else:
            return jsonify(message = message, url = 'none')

#handles the admin page
@app.route('/user/<logonid>/useradmin/')
def useradmin(logonid):

    session = Session()
    #gets the data associated with this user
    thisuser = session.query(user).filter(user.logonid == logonid).first()
    if thisuser is None:
        return ('Did not find user in database. You have entered an incorrect URL address.')
    try:
        #check if this user is a conductor, if they are not, deny them.
        if thisuser.isadmin != 1 and thisuser.logonid != getconfig('AdminUUID'):
            return ('You are not allowed to view this page.')
        else:
            #get the list of people that play instruments
            players_query = session.query(instrument.userid).filter(instrument.isactive == 1)
            #get the players that have not played yet in this camp, add a 0 playcount to them and append them to the list
            already_played_query = session.query(
                                user.userid
                            ).join(groupassignment
                            ).join(group
                            ).filter(
                                group.ismusical == 1, 
                                group.status == 'Confirmed', 
                                user.userid.in_(players_query)
                            )
            users = session.query(
                                user.userid, 
                                user.logonid, 
                                user.isactive, 
                                user.firstname, 
                                user.lastname, 
                                user.isadmin, 
                                user.isconductor, 
                                user.isannouncer, 
                                user.grouprequestcount,
                                instrument.instrumentname,
                                sqlalchemy.sql.expression.literal_column("0").label("playcount")
                            ).outerjoin(instrument
                            ).filter(
                                ~user.userid.in_(already_played_query),
                                user.userid.in_(players_query),
                                instrument.isprimary == 1
                            ).all()
            #append the players that have already played.
            for p in (session.query(
                                user.userid, 
                                user.logonid, 
                                user.isactive, 
                                user.firstname, 
                                user.lastname, 
                                user.isadmin, 
                                user.isconductor, 
                                user.isannouncer, 
                                user.grouprequestcount,
                                func.count(groupassignment.userid).label("playcount")
                            ).group_by(user.userid
                            ).outerjoin(groupassignment, user.userid == groupassignment.userid
                            ).outerjoin(group
                            ).filter(
                                group.ismusical == 1, 
                                group.status == 'Confirmed', 
                                user.userid.in_(players_query),
                            ).order_by(func.count(groupassignment.userid)
                            ).all()):
                users.append(p)
            #get the inverse of that - the non-players and add it to the list
            for p in (session.query(user.userid, user.logonid, user.firstname, user.lastname, user.isadmin, user.isconductor, user.isannouncer, sqlalchemy.sql.expression.literal_column("'Non Player'").label("playcount")).filter(~user.userid.in_(players_query)).all()):
                users.append(p)
            return render_template('useradmin.html', \
                                thisuser=thisuser, \
                                users=users, \
                                campname=getconfig('Name'), favicon=getconfig('Favicon_URL'), instrumentlist=getconfig('Instruments').split(","), supportemailaddress=getconfig('SupportEmailAddress'), \
                                )
    except Exception as ex:
        log('Failed to execute %s for user %s %s with exception: %s.' % (request.method, thisuser.firstname, thisuser.lastname, ex))
        message = ('Failed to execute %s with exception: %s. Try refreshing the page and trying again or contact camp administration.' % (request.method, ex))
        session.rollback()
        session.close()
        if request.method == 'GET':
            return errorpage(thisuser,'Failed to display page with exception: %s.' % ex)
        else:
            return jsonify(message = message, url = 'none')

#handles the useredit page
@app.route('/user/<logonid>/edituser/<targetuserid>/', methods=['GET', 'POST'])
def edituser(logonid, targetuserid):
    session = Session()
    #gets the data associated with this user
    thisuser = session.query(user).filter(user.logonid == logonid).first()
    if thisuser is None:
        return ('Did not find user in database. You have entered an incorrect URL address.')
    try:
        if thisuser.isadmin != 1 and targetuserid is None:
            session.close()
            return errorpage(thisuser,'You do not have permission to view this page.')
        if targetuserid is not None:
            if targetuserid == 'self':
                targetuser = session.query(user).filter(user.userid == thisuser.userid).first()
            else:
                targetuser = session.query(user).filter(user.userid == targetuserid).first()
            if targetuser is None:
                    session.close()
                    return errorpage(thisuser,'Could not find requested user in database.')
            elif thisuser.isadmin != 1 and (thisuser.userid != targetuser.userid):
                session.close()
                return errorpage(thisuser,'You do not have permission to view this page.')
        else:
            targetuser = user()
        targetuserinstruments = session.query(instrument).filter(instrument.userid == targetuser.userid).all()
        periods = session.query(period).order_by(period.starttime).all()
        #if this is a user requesting the page
        if request.method == 'GET':
            session.close()
            return render_template('edituser.html', \
                                    thisuser=thisuser, \
                                    targetuser=targetuser, \
                                    targetuserinstruments=targetuserinstruments, \
                                    campname=getconfig('Name'), favicon=getconfig('Favicon_URL'), instrumentlist=getconfig('Instruments').split(","), supportemailaddress=getconfig('SupportEmailAddress'), \
                                    periods=periods, \
                                    maximumlevel=int(getconfig('MaximumLevel')), \
                                    )
        
        #if this is a user that just pressed submit
        if request.method == 'POST':
            #format the packet received from the server as JSON
            content = request.json

            if thisuser.isadmin == 1:
                #is this user doesn't have an ID yet, they are new and we must set them up
                if targetuser.userid is None:
                    #assign them a userid from a randomly generated uuid
                    targetuser.userid = str(uuid.uuid4())
                    targetuser.logonid = str(uuid.uuid4())
                    session.add(targetuser)

                elif content['submittype'] == 'reset':
                    targetuser.logonid = str(uuid.uuid4())
                    session.merge(targetuser)
                    session.commit()
                    session.close()
                    return jsonify(message = 'User logon reset.', url = 'none', success='true')

                if content['firstname'] == '' or content['firstname'] == 'null' or content['firstname'] == 'None' or \
                            content['lastname'] == '' or content['lastname'] == 'null' or content['lastname'] == 'None':
                    session.rollback()
                    session.close()
                    return jsonify(message = 'You cannot save a user without a firstname and lastname.', url = 'none')

            if content['arrival'] >= content['departure']:
                        session.rollback()
                        session.close()
                        return jsonify(message = 'Your departure time must be after your arrival time.', url = 'none')
            
            #add the content in the packet to this group's attributes
            for key,value in content.items():
                if (thisuser.isadmin != 1 and thisuser.isadmin != '1') and key != 'arrival' and key != 'departure' and key != 'isactive' and key != 'submittype' and key != 'objects':
                    session.rollback()
                    session.close()
                    return jsonify(message = 'Users are not allowed to edit this attribute. The page should not have given you this option.', url = 'none')
                elif not isinstance(value, list) and value is not None and value != 'null' and value != '' and value != 'None' and value != 'HIDDEN':
                    log('Setting %s to be %s' % (key, value))
                    setattr(targetuser,key,value)
            session.merge(targetuser)
            session.commit()
            newinstrument = False
            #for each instrument object in the receiving packet
            for i in content['objects']:
                if i['instrumentid'] == 'new' and thisuser.isadmin == 1:
                    thisinstrument = instrument(userid = targetuser.userid)
                    session.add(thisinstrument)
                    log('Added new instrument for user %s' % targetuser.firstname)
                    newinstrument = True
                elif i['instrumentid'] != 'new':
                    thisinstrument = session.query(instrument).filter(instrument.instrumentid == i['instrumentid']).first()
                    if thisinstrument is None:
                        session.rollback()
                        session.close()
                        return jsonify(message = 'Instrument listing not found, could not modify the listing.', url = 'none')
                    if thisuser.isadmin != 1 and thisinstrument.userid != thisuser.userid:
                        session.rollback()
                        session.close()
                        return jsonify(message = 'You cannot change an instrument listing for another user.', url = 'none')
                else:
                    session.rollback()
                    session.close()
                    return jsonify(message = 'You have submitted illegal parameters for your instrument. No changes have been made to your instrument listings.', url = 'none')
                for key,value in i.items():
                    if key != 'instrumentid':
                        if thisuser.isadmin != 1 and key != 'isactive' and key != 'isprimary':
                            session.rollback()
                            session.close()
                            return jsonify(message = 'You have submitted illegal parameters for your instrument. No changes have been made to your instrument listings.', url = 'none')
                        elif value != 'None':
                            setattr(thisinstrument,key,value)
                session.merge(thisinstrument)
            session.commit()

            if content['submittype'] == 'submit':
                url = '/user/' + str(thisuser.logonid) + '/'
                message = 'none'
                flash(u'Changes Saved', 'success')
            elif content['submittype'] == 'save':
                if targetuserid is None:
                    url = ('/user/' + str(thisuser.logonid) + '/edituser/' + str(targetuser.userid) + '/')
                    message = 'none'
                    flash(u'New User Successfully Created', 'success')
                else:
                    if newinstrument == True:
                        url = 'refresh'
                        flash(u'New Instrument Successfully Added', 'success')
                    else:
                        url = 'none'
                    message = 'none'
            else:
                url = 'none'
                message = 'Incomplete request. Request failed.'
            session.close()
            #send the user back to their home
            return jsonify(message = message, url = url)
    except Exception as ex:
        log('Failed to execute %s for user %s %s with exception: %s.' % (request.method, thisuser.firstname, thisuser.lastname, ex))
        message = ('Failed to execute %s with exception: %s. Try refreshing the page and trying again or contact camp administration.' % (request.method, ex))
        session.rollback()
        session.close()
        if request.method == 'GET':
            return errorpage(thisuser,'Failed to display page with exception: %s.' % ex)
        else:
            return jsonify(message = message, url = 'none')

@app.route('/user/<logonid>/newuser/', methods=['GET', 'POST'])
def newuser(logonid):
    return edituser(logonid,None)

@app.route('/user/<logonid>/settings/', methods=['GET', 'POST'])
def settings(logonid):
    return edituser(logonid,'self')

#sends bulk emails to an array of users sent with the request
@app.route('/user/<logonid>/email/', methods=['POST'])
def send_home_link_email(logonid):

    session = Session()
    #gets the data associated with this user
    thisuser = session.query(user).filter(user.logonid == logonid).first()
    if thisuser is None:
        return ('Did not find user in database. You have entered an incorrect URL address.')

    try:
        if thisuser.isadmin != 1:
            session.close()
            return errorpage(thisuser,'You do not have permission to view this page')
        content = request.json
        log('Content received: %s' % content)
        errors = ''
        success = 'true'
        for u in content['objects']:
            targetuser = session.query(user).filter(user.userid == u['userid']).first()
            if targetuser is None:
                errors = errors + ('Could not find user with id %s in database\n' % u['userid'])
            elif targetuser.email is None or targetuser.email == '':
                errors = errors + ('Could not find email for user %s %s\n' % (targetuser.firstname, targetuser.lastname))
            else:
                subject = ('Your link to the %s Scheduler' % getconfig('Name'))
                body = """Hi %s, welcome to %s!\n
%s\n
Your homepage, containing your daily schedule, is here:\n
%s/user/%s/ \n
WARNING: DO NOT GIVE THIS LINK, OR ANY LINK ON THIS WEBSITE TO ANYONE ELSE. It is yours, and yours alone and contains your connection credentials.\n
A small rundown of how to use the web app:\n
-Visit this page each day to see your schedule. Click or tap each item to see times, locations, and the instrument you're playing. Don't forget to refresh the page each day, your phone may not refresh the page if you minimise it and come back to it later.
-If you're going to be absent for a session or meal, plesae notify us at least one day before by navigating to a future date with the "Next" button, selecting your desired period, then selecting "Mark Me as Absent".
-You can request groups in a few ways. The best way is to visit the music library by clicking the book icon in your top bar, select music you'd like to play, and click the request button there. When you're on the group requset page, fill in your desired information, and press submit. Leaving blanks for other player names is fine and encouraged, you'll be matched up with other players at the end of the day.\n
If you have any questions, please reply to this email or contact us on %s.\n
Thanks!\n
%s %s
%s""" % (targetuser.firstname, \
                getconfig('Name'), \
                getconfig('EmailIntroSentence'), \
                getconfig('Website_URL'), \
                targetuser.logonid, \
                getconfig('SupportEmailAddress'), \
                thisuser.firstname, \
                thisuser.lastname, \
                getconfig('Name')\
                )
                message = send_email(targetuser.email, subject, body)
                if message == 'Failed to Send Email':
                    errors = errors + ('Failed to send email to %s %s\n' % (targetuser.firstname, targetuser.lastname))
        session.close()
        if errors != '':
            message = 'Completed with errors:\n' + errors
            success = 'false'
        return jsonify(message = message, url = 'none', success = success)

    except Exception as ex:
        log('Failed to execute %s for user %s %s with exception: %s.' % (request.method, thisuser.firstname, thisuser.lastname, ex))
        message = ('Failed to execute %s with exception: %s. Try refreshing the page and trying again or contact camp administration.' % (request.method, ex))
        session.rollback()
        session.close()
        if request.method == 'GET':
            return errorpage(thisuser,'Failed to display page with exception: %s.' % ex)
        else:
            return jsonify(message = message, url = 'none')

#Handles the conductor instrumentation page.
@app.route('/user/<logonid>/instrumentation/<periodid>/', methods=['GET', 'POST'])
def instrumentation(logonid,periodid):

    session = Session()
    #gets the data associated with this user
    thisuser = session.query(user).filter(user.logonid == logonid).first()
    if thisuser is None:
        return ('Did not find user in database. You have entered an incorrect URL address.')
    try:
        #check if this user is a conductor, if they are not, deny them.
        if thisuser.isconductor != 1:
            return ('You are not allowed to view this page.')
        else:
            #gets the data associated with this period
            thisperiod = session.query(period).filter(period.periodid == periodid).first()
            if thisperiod is None:
                return ('Could not find the period requested.')

            #The below runs when a user visits the instrumentation page
            if request.method == 'GET':

                #Get a list of the locations that are not being used in the period selected
                locations_used_query = session.query(location.locationid).join(group).join(period).filter(period.periodid == periodid)
                locations = session.query(location).filter(~location.locationid.in_(locations_used_query)).all()
                #Get a list of the available music not being used in the period selected
                musics_used_query = session.query(music.musicid).join(group).join(period).filter(period.periodid == periodid)
                musics = session.query(music).filter(~music.musicid.in_(musics_used_query)).all()
                musics_serialized = [i.serialize for i in musics]
                #get a list of conductors to fill the dropdown on the page
                everyone_playing_in_periodquery = session.query(user.userid).join(groupassignment).join(group).join(period).filter(period.periodid == thisperiod.periodid)
                conductors = session.query(user).join(instrument, user.userid == instrument.userid).filter(instrument.instrumentname == 'Conductor', instrument.isactive == 1).filter(~user.userid.in_(everyone_playing_in_periodquery)).all()
                #get the list of instruments from the config file
                instrumentlist = getconfig('Instruments').split(",")
                #find all large group templates and serialize them to prepare to inject into the javascript
                grouptemplates = session.query(grouptemplate).filter(grouptemplate.size == 'L').all()
                grouptemplates_serialized = [i.serialize for i in grouptemplates]
                session.close()
                return render_template('instrumentation.html', \
                                    thisuser=thisuser, \
                                    grouptemplates = grouptemplates, \
                                    conductors=conductors, \
                                    grouptemplates_serialized=grouptemplates_serialized, \
                                    campname=getconfig('Name'), favicon=getconfig('Favicon_URL'), instrumentlist=getconfig('Instruments').split(","), supportemailaddress=getconfig('SupportEmailAddress'), \
                                    thisperiod=thisperiod, \
                                    locations=locations, \
                                    maximumlevel=int(getconfig('MaximumLevel')), \
                                    musics=musics, \
                                    musics_serialized=musics_serialized, \
                                    instrumentlist_string=getconfig('Instruments'), \
                                    )

            #The below runs when a user presses "Submit" on the instrumentation page. It creates a group object with the configuraiton selected by 
            #the user, and creates groupassignments if needed
            if request.method == 'POST':
                #format the packet received from the server as JSON
                content = request.json
                session = Session()
                log('Grouprequest received. Whole content of JSON returned is: %s' % content)
                #establish the 'grouprequest' group object. This will be built up from the JSON packet, and then added to the database
                grouprequest = group(ismusical = 1, requesteduserid = thisuser.userid, periodid = thisperiod.periodid, status = "Queued", requesttime = datetime.datetime.now())
                #check if a group already exists for this period with the same name
                namecheck = session.query(group).filter(group.groupname == content['groupname'], group.periodid == thisperiod.periodid).first()
                if namecheck is not None:
                    url = 'none'
                    log('Instrumentation creation failed, duplicate name for this period')
                    session.close()
                    session.rollback()
                    return jsonify(message = 'Could not create instrumentation, there is already a group named %s in this period.' % namecheck.groupname, url = url)
                #for each player object in the players array in the JSON packet
                for key, value in content.items():
                    if (key == 'groupname' or key == 'maximumlevel' or key == 'mininumlevel') and value == '':
                        url = 'none'
                        log('Instrumentation creation failed, misconfiguration')
                        session.close()
                        session.rollback()
                        return jsonify(message = 'Could not create instrumentation, you must enter a groupname, music, maximumlevel and mininumlevel', url = url)
                    if value != '' and value is not None and value != 'null' and value != 'None':
                        setattr(grouprequest, key, value)
                    else:
                        setattr(grouprequest, key, None)
                #create the group and the groupassinments configured above in the database
                session.add(grouprequest)
                #if the user plays the "conductor" instrument (i.e. they are actually a conductor) assign them to this group
                if content['conductoruserid'] is not None and content['conductoruserid'] != 'null' and content['conductoruserid'] != '':
                    userconductor = session.query(user).join(instrument, user.userid == instrument.userid).filter(user.userid == content['conductoruserid'], instrument.instrumentname == "Conductor", instrument.isactive == 1, user.isactive == 1, user.arrival <= thisperiod.starttime, user.departure >= thisperiod.endtime).first()
                    if userconductor is not None:
                        userplayinginperiod = session.query(user.userid).join(groupassignment).join(group).join(period).filter(period.periodid == thisperiod.periodid, user.userid == content['conductoruserid']).first()
                        if userplayinginperiod is None:
                            conductorassignment = groupassignment(userid = content['conductoruserid'], groupid = grouprequest.groupid, instrumentname = 'Conductor')
                            session.add(conductorassignment)
                        else:
                            url = 'none'
                            log('Instrumentation creation failed, conductor is already assigned to a group')
                            session.close()
                            session.rollback()
                            return jsonify(message = 'Could not create instrumentation, %s is already assigned to a group during this period.' % userconductor.firstname, url = url)
                    else:
                        url = 'none'
                        log('Instrumentation creation failed, conductor user is not set up properly')
                        session.close()
                        session.rollback()
                        return jsonify(message = 'The user requested as the conductor is not set up to be a conductor in the database.', url = url)
                session.commit()
                #send the URL for the group that was just created to the user, and send them to that page
                url = ('/user/' + str(thisuser.logonid) + '/group/' + str(grouprequest.groupid) + '/')
                log('Sending user to URL: %s' % url)
                session.close()
                flash(u'Instrumentation Accepted', 'success')
                return jsonify(message = 'none', url = url)

    except Exception as ex:
        log('Failed to execute %s for user %s %s with exception: %s.' % (request.method, thisuser.firstname, thisuser.lastname, ex))
        message = ('Failed to execute %s with exception: %s. Try refreshing the page and trying again or contact camp administration.' % (request.method, ex))
        session.rollback()
        session.close()
        if request.method == 'GET':
            return errorpage(thisuser,'Failed to display page with exception: %s.' % ex)
        else:
            return jsonify(message = message, url = 'none')

#Application setup page. This needs to be run at the start, just after the app has been deployed. The user uploads config files and user lists to populate the database.
@app.route('/user/<logonid>/setup/', methods=["GET", "POST"])
def setup(logonid):

    session = Session()
    #gets the data associated with this user
    thisuser = session.query(user).filter(user.logonid == logonid).first()
    if thisuser is None:
        session.close()
        return ('Did not find user in database. You have entered an incorrect URL address.')
    try:
        #check if this user is an admin or the Administrator superuser, if they are not, deny them.
        if thisuser.isadmin != 1 and thisuser.logonid != getconfig('AdminUUID'):
            return errorpage(thisuser,'You are not allowed to view this page.')
        else:
            if request.method == 'GET':
                session.close()
                return render_template('setup.html', \
                                                thisuser=thisuser, \
                                                campname=getconfig('Name'), favicon=getconfig('Favicon_URL'), instrumentlist=getconfig('Instruments').split(","), supportemailaddress=getconfig('SupportEmailAddress'), \
                                                )
            if request.method == 'POST':
                session.close()
                # Get the name of the uploaded file
                file = request.files['file']
                if file and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    if filename == 'config.xml':
                        message = dbbuild(file.read())
                    if filename == 'campers.csv':
                         message = importusers(file)
                    if filename == 'musiclibrary.csv':
                         message = importmusic(file)
                    if message == 'Success':
                        flash(message,'success')
                    else:
                        flash(message,'error')
                    return message
    
    except Exception as ex:
        log('Failed to execute %s for user %s %s with exception: %s.' % (request.method, thisuser.firstname, thisuser.lastname, ex))
        message = ('Failed to execute %s with exception: %s. Try refreshing the page and trying again or contact camp administration.' % (request.method, ex))
        session.rollback()
        session.close()
        if request.method == 'GET':
            return errorpage(thisuser,'Failed to display page with exception: %s.' % ex)
        else:
            return jsonify(message = message, url = 'none')

#This page is viewable by the admin only, it lets them edit different objects in the database - grouptemplates, locations, periods, etc.
@app.route('/user/<logonid>/objecteditor/<input>/', methods=["GET","POST","DELETE"])
def objecteditor(logonid, input, objectid=None):

    session = Session()
    #gets the data associated with this user
    thisuser = session.query(user).filter(user.logonid == logonid).first()
    if thisuser is None:
        session.close()
        return ('Did not find user in database. You have entered an incorrect URL address.')

    try:
        if thisuser.isadmin != 1:
            session.close()
            return render_template('errorpage.html', \
                                    thisuser=thisuser, \
                                    campname=getconfig('Name'), favicon=getconfig('Favicon_URL'), instrumentlist=getconfig('Instruments').split(","), supportemailaddress=getconfig('SupportEmailAddress'), \
                                    errormessage = 'You do not have permission to view this page.'
                                    )

        log('User requested objects with type %s' % input)
        if input == 'grouptemplate':
            table = 'grouptemplate'
            type = 'Group Template'
            objects_query = session.query(grouptemplate)
        elif input == 'location':
            table = 'location'
            type = 'Location'
            objects_query = session.query(location)
        elif input == 'period':
            table = 'period'
            type = 'Period'
            objects_query = session.query(period)
        elif input == 'music':
            table = 'music'
            type = 'Music'
            objects_query = session.query(music)
        elif input == 'group':
            table = 'group'
            type = 'Group'
            objects_query = session.query(group)
        else:
            session.close()
            return render_template('errorpage.html', \
                                thisuser=thisuser, \
                                campname=getconfig('Name'), favicon=getconfig('Favicon_URL'), instrumentlist=getconfig('Instruments').split(","), supportemailaddress=getconfig('SupportEmailAddress'), \
                                errormessage = 'Invalid input.'
                                )
        if request.method == 'GET':
                object_dict = dict((col, getattr(objects_query.first(), col)) for col in objects_query.first().__table__.columns.keys())
                objects = objects_query.all()
                session.close()
                return render_template('objecteditor.html', \
                                    thisuser=thisuser, \
                                    object_dict=object_dict, \
                                    objects=objects, \
                                    type=type, \
                                    table=table, \
                                    objectid=objectid, \
                                    campname=getconfig('Name'), favicon=getconfig('Favicon_URL'), instrumentlist=getconfig('Instruments').split(","), supportemailaddress=getconfig('SupportEmailAddress'), \
                                    )

        if request.method == 'POST':
            try:
                #format the packet received from the server as JSON
                content = request.json
                log('Received packet for modifying %ss with content: %s' % (type, content))
                for o in content['objects']:
                    if o[table + 'id'] != '' and o[table + 'id'] is not None:
                        if o[table + 'id'] == 'new':
                            log('Found a new object to create')
                            if table == 'grouptemplate':
                                object = grouptemplate()
                            elif table == 'location':
                                object = location()
                            elif table == 'period':
                                object = period()
                            elif table == 'music':
                                object = music()
                            elif table == 'group':
                                object = group()
                            session.add(object)
                        else:
                            log('Trying to find a %s object with id %s' % (table, o[table + 'id']))
                            object = objects_query.filter(getattr(globals()[table],(table + 'id')) == o[table + 'id']).first()
                            if object is None:
                                session.rollback()
                                session.close()
                                return jsonify(message = 'Could not find one of your requested objects. This is a malformed request packet.', url = 'none')
                        for key, value in o.items():
                            if key != table + 'id':
                                log('Changing object %s key %s to %s' % (table, key, value))
                                setattr(object,key,value)
                        session.merge(object)
                        url = '/user/' + thisuser.logonid + '/objecteditor/' + table + '/'
                        session.commit()
                        session.close()
                        return jsonify(message = 'none', url = url)
            except Exception as ex:
                session.rollback()
                session.close()
                return jsonify(message = 'Failed to post update with exception: %s' % ex, url = url)

        if request.method == 'DELETE':
            try:
                session.delete(objects_query.filter(getattr(globals()[table],(table + 'id')) == request.json).first())
                url = '/user/' + thisuser.logonid + '/objecteditor/' + table + '/'
                session.commit()
                session.close()
                return jsonify(message = 'none', url = url)
            except Exception as ex:
                session.rollback()
                session.close()
                return jsonify(message = 'Failed to delete object with exception %s' % ex, url = 'none')

    except Exception as ex:
        log('Failed to execute %s for user %s %s with exception: %s.' % (request.method, thisuser.firstname, thisuser.lastname, ex))
        message = ('Failed to execute %s with exception: %s. Try refreshing the page and trying again or contact camp administration.' % (request.method, ex))
        session.rollback()
        session.close()
        if request.method == 'GET':
            return errorpage(thisuser,'Failed to display page with exception: %s.' % ex)
        else:
            return jsonify(message = message, url = 'none')

@app.route('/js/<path:path>')
def send_js(path):
    return send_from_directory('js', path)

@app.route('/css/<path:path>')
def send_css(path):
    return send_from_directory('css', path)

@app.route('/img/<path:path>')
def send_png(path):
    return send_from_directory('img', path)