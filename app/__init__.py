from flask import Flask, render_template, request, redirect, jsonify, make_response, json, request, url_for, send_from_directory
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
from config import *
from SMTPemail import *

# Make the WSGI interface available at the top level so wfastcgi can get it.
app = Flask(__name__)
#app.secret_key = 'MusicCampIsCool'
wsgi_app = app.wsgi_app
# These are the extension that we are accepting to be uploaded
app.config['ALLOWED_EXTENSIONS'] = set(['txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'xml', 'csv'])

Session = sessionmaker(bind=engine)

#sets up debugging
def log(string):
    if int(getconfig('Debug')) == 1:
        print(string)

# For a given file, return whether it's an allowed type or not
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1] in app.config['ALLOWED_EXTENSIONS']

#Looks up the amount of times a user has participated in an "ismusical" group during the camp
def playcount(session,userid):
    playcount = session.query(groupassignment.userid).join(group).join(user).outerjoin(period).\
        filter(user.userid == userid, group.ismusical == 1, period.endtime <= datetime.datetime.now()).count()
    return playcount

#get the information needed to fill in the user's schedule table
def getschedule(session,thisuser,date):
    #find the start of the next day
    nextday = date + datetime.timedelta(days=1)

    schedule = []
    #for each period in the requested day
    for p in session.query(period).filter(period.starttime > date, period.endtime < nextday).all():
        #try to find a group assignment for the user
        g = session.query(group.groupname, period.starttime, period.endtime, location.locationname, group.groupid, group.ismusical, \
                            group.iseveryone, period.periodid, period.periodname, groupassignment.instrumentname).\
                            join(period).join(groupassignment).join(user).join(instrument).outerjoin(location).\
                            filter(user.userid == thisuser.userid, group.periodid == p.periodid, group.status == 'Confirmed').first()
        if g is not None:
            schedule.append(g)
        e = None
        #if we didn't find an assigned group...
        if g is None:
            #try to find an iseveryone group at the time of this period
            e = session.query(group.groupname, period.starttime, period.endtime, location.locationname, group.groupid, group.ismusical, \
                            group.iseveryone, period.periodid, period.periodname).\
                            join(period).join(location).\
                            filter(group.iseveryone == 1, group.periodid == p.periodid).first()
        if e is not None:
            schedule.append(e)
        #if we didn't find an assigned group or an iseveryone group...
        if e is None and g is None:
            #just add the period detalis
            schedule.append(p)
    return schedule

#from an input group, returns the highest and lowest instrument levels that should be assigned depending on its config
def getgrouplevel(session,inputgroup,min_or_max):
    if min_or_max == 'min':
        log('Finding group %s level' % min_or_max)
        #if the group is set to "auto", i.e. blank or 0, find the minimum level of all the players currently playing in the group
        if inputgroup.minimumlevel is None or inputgroup.minimumlevel == '' or inputgroup.minimumlevel == '0' or inputgroup.minimumlevel == 0:
            minimumgradeob = session.query(user.firstname, user.lastname, instrument.instrumentname, instrument.grade).join(groupassignment).join(group).\
                join(instrument, and_(groupassignment.instrumentname == instrument.instrumentname, user.userid == instrument.userid)).\
                filter(group.groupid == inputgroup.groupid).order_by(instrument.grade).first()
            #if we find at least one player in this group, set the minimumgrade to be this players level minus the autoassignlimitlow
            if minimumgradeob is not None:
                log('Found minimum grade in group %s to be %s %s playing %s with grade %s' % (inputgroup.groupid, minimumgradeob.firstname, minimumgradeob.lastname, minimumgradeob.instrumentname, minimumgradeob.grade))
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
                log('Found minimum grade in group %s to be %s %s playing %s with grade %s' % (inputgroup.groupid, minimumgradeob.firstname, minimumgradeob.lastname, minimumgradeob.instrumentname, minimumgradeob.grade))
                level = int(minimumgradeob.grade) + int(getconfig('AutoAssignLimitHigh'))
                if level > int(getconfig('AutoAssignLimitHigh')):
                    level = getconfig('MaximumLevel')
            #if we don't find a player in this group, set the maximum level to 0 (not allowed to autofill)
            else:
                level = 0
        #if this group's maximum level is explicitly set, use that setting
        else:
            level = inputgroup.maximumlevel
    log('Found %s grade of group %s to be %s' % (min_or_max,inputgroup.groupid,level))
    return int(level)
    
#gets a list of periods corresponding to the requested userid and date, formatting it in a nice way for the user home
def useridanddatetoperiods(session,userid,date):
    nextday = date + datetime.timedelta(days=1)
    
def getgroupname(g):
    instrumentlist = getconfig('Instruments').split(",")
    count = 0
    for i in instrumentlist:
        value = getattr(g, i)
        log('Instrument %s is value %s' % (i, value))
        if value is not None:
            count = count + int(getattr(g, i))
    log('Found %s instruments in group.' % value)
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
#tells them how to get to their user home.
@app.route('/')
def rootpage():
    return render_template('index.html')

#upon the URL request in the form domain/user/<userid> the user receives their home. The home contains the groups they 
#are playing in. Optionally, this page presents their home in the future or the past, and gives them further options.
@app.route('/user/<userid>/')
def home(userid,inputdate='n'):

    session = Session()
    #gets the data associated with this user
    thisuser = session.query(user).filter(user.userid == userid).first()
    if thisuser is None:
        session.close()
        return ('Did not find user in database. You have entered an incorrect URL address.')

    try:
        log('home fetch requested for user %s' % userid)
        log('date modifier is currently set to %s' % inputdate)
        #get the current announcement
        currentannouncement = session.query(announcement).order_by(desc(announcement.creationtime)).first()
        if currentannouncement is not None:
            announcementcontent = currentannouncement.content.replace("\n","<br />")
        else:
            announcementcontent = ''
        #get impontant datetimes
        today = datetime.datetime.combine(datetime.date.today(), datetime.time.min) #get today's date
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
        nextday = displaydate + datetime.timedelta(days=1)

        #get an array containing the dates that the camp is running
        dates = []
        for d in range((campendtime-campstarttime).days + 2):
            dates.append(campstarttime + timedelta(days=d))

        #get the user's schedule, an array of objects depending on the user's state during each period
        schedule = getschedule(session,thisuser,displaydate)

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
                            )

    except Exception as ex:
        log('Failed to display page to user %s %s with exception: %s.' % (thisuser.firstname, thisuser.lastname, ex))
        session.rollback()
        session.close()
        return render_template('errorpage.html', \
                            thisuser=thisuser, \
                            campname=getconfig('Name'), favicon=getconfig('Favicon_URL'), instrumentlist=getconfig('Instruments').split(","), supportemailaddress=getconfig('SupportEmailAddress'), \
                            errormessage = 'Failed to display page with exception: %s.' % ex
                            )

#Currently broken. Doesn't like the fact that the getschedule function returns an array of inconsistant objects. Either make them consistant,
#or put logic into the 'for s in ...' part of the below function. Or maybe improve the query in the getschedule function.
@app.route('/user/<userid>/requestschedule/', methods=["POST"])
def requestschedule(userid):
    log('Schedule request for date %s' % request.json['date'])
    #convert the inputdate to a datetime object
    date = datetime.datetime.strptime(request.json['date'], '%Y-%m-%d')
    session = Session()
    #gets the data associated with this user
    thisuser = session.query(user).filter(user.userid == userid).first()
    if thisuser is None:
        session.close()
        return jsonify(message = 'Your user does not exist. Something went wrong.', url = 'none', status_code = 400)

    schedule_serialized = []
    for s in getschedule(session,thisuser,date):
        schedule_serialized.append({'groupname': s.groupname, 'starttime': s.starttime, 'endtime': s.endtime,\
            'locationname': s.locationname, 'groupid': s.groupid, 'ismusical': s.ismusical, 'iseveryone': s.iseveryone,\
            'preiodid': s.periodid, 'periodname': s.periodname, 'instrumentname': s.instrumentname})

    return jsonify(schedule_serialized)

#When the user selects the "next day" and "previous day" links on their home, it goes to this URL. this route redirects them back
#to the user home with a date modifier.
@app.route('/user/<userid>/date/<date>/')
def homeDateModifier(userid,date):
    return home(userid,date)

#Makes a post query that marks a player adsent for a given period. This is triggered off the above (two) home functions.
@app.route("/user/<userid>/period/<periodid>/absent/<command>/", methods=["POST"])
def mark_absent(userid,periodid,command):
    session = Session()
    #gets the data associated with this user
    thisuser = session.query(user).filter(user.userid == userid).first()
    if thisuser is None:
        return ('Did not find user in database. You have entered an incorrect URL address.')

    try:

        currentassignment = session.query(group.groupname, groupassignment.groupassignmentid).\
                        join(groupassignment).join(user).join(period).\
                        filter(period.periodid == periodid, user.userid == userid).first()
        log('User is currently assigned to ' + str(currentassignment))
        #case if the user is not assigned to anything, and attempted to mark themselves as absent
        if currentassignment == None and command == 'confirm':
            log('user is not assigned to anything and is requesting an absence')
            #get the groupid for the absent group associated with this period
            absentgroup = session.query(group.groupid).join(period).filter(group.groupname == 'absent', period.periodid == periodid).first()
            log('found absent group %s' % absentgroup)
            #assign this person to the absent group
            try:
                session.add(groupassignment(userid = userid, groupid = absentgroup.groupid))
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

    except Exception as ex:
        log('Failed to display page to user %s %s with exception: %s.' % (thisuser.firstname, thisuser.lastname, ex))
        session.rollback()
        session.close()
        return render_template('errorpage.html', \
                            thisuser=thisuser, \
                            campname=getconfig('Name'), favicon=getconfig('Favicon_URL'), instrumentlist=getconfig('Instruments').split(","), supportemailaddress=getconfig('SupportEmailAddress'), \
                            errormessage = 'Failed to display page with exception: %s.' % ex
                            )

#The group page displays all the people in a given group, along with possible substitutes
@app.route('/user/<userid>/group/<groupid>/')
def grouppage(userid,groupid):
    session = Session()
    #gets the data associated with this user
    thisuser = session.query(user).filter(user.userid == userid).first()
    if thisuser is None:
        return ('Did not find user in database. You have entered an incorrect URL address.')

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
    
    """except Exception as ex:
        log('Failed to display page to user %s %s with exception: %s.' % (thisuser.firstname, thisuser.lastname, ex))
        session.rollback()
        session.close()
        return render_template('errorpage.html', \
                            thisuser=thisuser, \
                            campname=getconfig('Name'), favicon=getconfig('Favicon_URL'), instrumentlist=getconfig('Instruments').split(","), supportemailaddress=getconfig('SupportEmailAddress'), \
                            errormessage = 'Failed to display page with exception: %s.' % ex
                            )"""

#Group editor page. Only accessable by admins. Navigate here from a group to edit group.
@app.route('/user/<userid>/group/<groupid>/edit/', methods=['GET', 'POST', 'DELETE'])
def editgroup(userid,groupid,periodid=None):

    session = Session()
    #gets the data associated with this user
    thisuser = session.query(user).filter(user.userid == userid).first()
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
            thisgroup = group(ismusical = 1)
        else:
            thisgroup = session.query(group).filter(group.groupid == groupid).first()
        if request.method == 'GET':
            #Current period tracks the period that the group is already set to (none, if it's a new group)
            currentperiod = session.query(period).filter(period.periodid == thisgroup.periodid).first()
            if periodid is not None:
                selectedperiod = session.query(period).filter(period.periodid == periodid).first()
            else:
                selectedperiod = currentperiod
            thislocation = session.query(location).join(group).filter(group.groupid == groupid).first()
            #gets the list of players playing in the given group
            thisgroupplayers = session.query(user.userid, user.firstname, user.lastname, groupassignment.instrumentname).join(groupassignment).join(group).\
                                    filter(group.groupid == groupid).order_by(groupassignment.instrumentname).all()
            thisgroupplayers_serialized = []
            for p in thisgroupplayers:
                 thisgroupplayers_serialized.append({'userid': p.userid, 'firstname': p.firstname, 'lastname': p.lastname,
                    'instrumentname': p.instrumentname})
            #handler in case user selected the blank period
            if selectedperiod is None:
                selectedperiodid = None
            else:
                selectedperiodid = selectedperiod.periodid
            #Finds all players who are already playing in this period (except in this specific group)
            playersPlayingInPeriod = session.query(user.userid).join(groupassignment).join(group).filter(group.groupid != thisgroup.groupid).filter(group.periodid == selectedperiodid)
            #finds all players who are available to play in this group (they aren't already playing in other groups)
            playersdump = session.query(user.userid,user.firstname,user.lastname,instrument.instrumentname,instrument.grade,instrument.isprimary).\
                        join(instrument).filter(~user.userid.in_(playersPlayingInPeriod), user.isactive == 1, user.arrival <= selectedperiod.starttime, user.departure >= selectedperiod.endtime, instrument.isactive == 1).all()
            playersdump_serialized = []
            for p in playersdump:
                playersdump_serialized.append({'userid': p.userid, 'firstname': p.firstname, 'lastname': p.lastname,
                    'instrumentname': p.instrumentname, 'grade': p.grade, 'isprimary': p.isprimary})

            #find all periods from now until the end of time to display to the user
            periods = session.query(period).order_by(period.starttime).filter(period.starttime > datetime.datetime.now()).all()
            locations_used_query = session.query(location.locationid).join(group).join(period).filter(period.periodid == periodid)
            locations = session.query(location).filter(~location.locationid.in_(locations_used_query)).all()
            log('This groups status is %s' % thisgroup.status)

            #find all group templates to show in a dropdown
            grouptemplates = session.query(grouptemplate).all()
            grouptemplates_serialized = [i.serialize for i in grouptemplates]

            session.close()
            return render_template('editgroup.html', \
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
                                )

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
            url = ('/user/' + str(thisuser.userid) + '/')
            message = 'none'
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
            thisperiod = session.query(period).filter(period.periodid == content['periodid']).first()
            if thisperiod is None:
                session.rollback()
                session.close()
                return jsonify(message = 'Could not find a period with the selected id. Refresh the page and try again.', url = 'none')
            thisgroupassignments = session.query(groupassignment).filter(groupassignment.groupid == thisgroup.groupid).all()
            for a in thisgroupassignments:
                session.delete(a)
            #add the content in the packet to this group's attributes
            for key,value in content.iteritems():
                if value is not None or value != 'null' or value != '' or key != 'primary_only':
                    log('Setting %s to be %s' % (key, value))
                    setattr(thisgroup,key,value)
            thisgroup.requesteduserid = thisuser.userid
            if groupid == None:
                session.add(thisgroup)
                thisgroup.requesttime = datetime.datetime.now()
                session.commit()
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
                            session.rollback()
                            session.close()
                            log('Found a clash for %s. They are already playing %s in %s. Refresh the page and try again.' % (playeruser.firstname, currentassignment.instrumentname, currentassignment.groupname))
                            return jsonify(message = ('Found a clash for %s. They are alrdeay playing %s in %s. Refresh the page and try again.' % (playeruser.firstname, currentassignment.instrumentname, currentassignment.groupname)), url = url)
                    #if we found a player and no clash, we can assign this player to the group
                    if playeruser is None:
                        url = ('/user/' + str(thisuser.userid) + '/')
                        session.rollback()
                        session.close()
                        return jsonify(message = 'Could not find one of your selected players in the database. Please refresh the page and try again.', url = url)
                    else:
                        #if the player is inactive or not attending camp at this time, they should never have been shown to the admin and chosen - this could happen if they were set to inactive while the admin had the page open
                        if playeruser.isactive != 1 or playeruser.arrival > thisperiod.starttime or playeruser.departure < thisperiod.endtime:
                            url = 'none'
                            session.rollback()
                            session.close()
                            log('The user %s %s is set to inactive and they cannot be assigned. Refresh the page and try again with a different user.' % (playeruser.firstname, playeruser.lastname))
                            return jsonify(message = ('The user %s %s is set to inactive and they cannot be assigned. Refresh the page and try again with a different user.' % (playeruser.firstname, playeruser.lastname)), url = url)
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
                log('User selected to autofill the group')
                log('Primary_only switch set to %s' % content['primary_only'])
                if content['periodid'] == '' or content['periodid'] is None:
                    session.rollback()
                    session.close()
                    return jsonify(message = 'You must have a period selected before autofilling.', url = 'none')
                else:
                    for i in getconfig('Instruments').split(","):
                        numberinstrument = getattr(thisgroup,i)
                        if int(getattr(thisgroup,i)) > 0:
                            log('Group has configured %s total players for instrument %s' % (numberinstrument, i))
                            currentinstrumentplayers = session.query(user).join(groupassignment).filter(groupassignment.groupid == thisgroup.groupid, groupassignment.instrumentname == i).all()
                            requiredplayers = int(numberinstrument) - len(currentinstrumentplayers)
                            log('Found %s current players for instrument %s' % (len(currentinstrumentplayers), i))
                            log('We need to autofill %s extra players for instrument %s' % (requiredplayers, i))
                            if requiredplayers > 0:
                                #get the userids of everyone that's already playing in something this period
                                everyone_playing_in_period_query = session.query(user.userid).join(groupassignment).join(group).join(period).filter(period.periodid == thisgroup.periodid)
                                #combine the last query with another query, finding everyone that both plays an instrument that's found in this
                                #group AND isn't in the list of users that are already playing in this period.
                                possible_players_query = session.query(user.userid).outerjoin(instrument).filter(~user.userid.in_(everyone_playing_in_period_query), user.isactive == 1, user.arrival <= thisperiod.starttime, user.departure >= thisperiod.endtime).\
                                    filter(instrument.grade >= mingrade, instrument.grade <= maxgrade, instrument.instrumentname == i, instrument.isactive == 1)
                                log('Found %s possible players of a requested %s for instrument %s.' % (len(possible_players_query.all()), requiredplayers, i))
                                #if we found at least one possible player
                                if len(possible_players_query.all()) > 0:
                                    #get the players that have already played in groups at this camp, and inverse it to get the players with playcounts of zero. Limit the query to just the spots we have left.
                                    already_played_query = session.query(user.userid).join(groupassignment).join(group).filter(group.ismusical == 1).\
                                        filter(groupassignment.userid.in_(possible_players_query))
                                    final_list = session.query(user.userid,sqlalchemy.sql.expression.literal_column("0").label("playcount")).filter(user.userid.in_(possible_players_query)).\
                                                    filter(~user.userid.in_(already_played_query)).limit(requiredplayers).all()
                                    #append the players that have already played, ordered by the number of times they've played. Keep the query limited to just the number we need. The admin controls if the query allows non-primary instruments by the content['primary_only']
                                    if len(final_list) < requiredplayers:
                                        for p in (session.query(user.userid, func.count(groupassignment.userid).label("playcount")).group_by(user.userid).outerjoin(groupassignment).outerjoin(group).outerjoin(instrument, groupassignment.userid == instrument.userid).\
                                                filter(group.ismusical == 1, instrument.isprimary >= content['primary_only']).filter(groupassignment.userid.in_(possible_players_query)).order_by(func.count(groupassignment.userid)).limit(requiredplayers - len(final_list)).all()):
                                            final_list.append(p)
                                    log('Players in final list with playcounts:')
                                    #add groupassignments for the final player list
                                    for pl in final_list:
                                        log('Selected %s with playcount %s to play %s' % (pl.userid, pl.playcount, i))
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
                        return jsonify(message = 'Your group is not confirmed because there are empty instrument slots. Your other changes have been saved.', url = '/user/' + str(thisuser.userid) + '/group/' + str(thisgroup.groupid) + '/edit/')
            try:
                session.merge(thisgroup)
                session.commit()
            except Exception as ex:
                log('failed to commit changes to database after a groupedit on group %s with error: %s' % (thisgroup.groupid,ex))
            if content['submittype'] == 'autofill':
                url = '/user/' + str(thisuser.userid) + '/group/' + str(thisgroup.groupid) + '/edit/'
                message = 'none'
            elif content['submittype'] == 'save':
                if groupid == None:
                    url = '/user/' + str(thisuser.userid) + '/group/' + str(thisgroup.groupid) + '/edit/'
                else:
                    url = 'none'
                message = 'none'
            else:
                url = '/user/' + str(thisuser.userid) + '/group/' + str(thisgroup.groupid) + '/'
                message = 'none'
            session.close()
            return jsonify(message = message, url = url)
    
    except Exception as ex:
        log('Failed to display page to user %s %s with exception: %s.' % (thisuser.firstname, thisuser.lastname, ex))
        session.rollback()
        session.close()
        return render_template('errorpage.html', \
                            thisuser=thisuser, \
                            campname=getconfig('Name'), favicon=getconfig('Favicon_URL'), instrumentlist=getconfig('Instruments').split(","), supportemailaddress=getconfig('SupportEmailAddress'), \
                            errormessage = 'Failed to display page with exception: %s.' % ex
                            )
        
@app.route('/user/<userid>/group/<groupid>/period/<periodid>/edit/', methods=['GET', 'POST', 'DELETE'])
def editgroupperiod(userid,groupid,periodid):
    return editgroup(userid,groupid,periodid)

@app.route('/user/<userid>/grouphistory/')
def grouphistory(userid):

    session = Session()
    #gets the data associated with this user
    thisuser = session.query(user).filter(user.userid == userid).first()
    if thisuser is None:
        return ('Did not find user in database. You have entered an incorrect URL address.')
    try:
        now = datetime.datetime.now() #get the time now
        groups = session.query(group.groupname, group.groupid, period.periodid, period.starttime, period.endtime, groupassignment.instrumentname, group.status, location.locationname).\
                    join(groupassignment).outerjoin(period).outerjoin(location).filter(groupassignment.userid == thisuser.userid, group.groupname != 'absent').order_by(period.starttime).all()
        log(groups)
        count = playcount(session, thisuser.userid)
        session.close()
        return render_template('grouphistory.html', \
                                thisuser=thisuser, \
                                groups = groups, \
                                campname=getconfig('Name'), favicon=getconfig('Favicon_URL'), instrumentlist=getconfig('Instruments').split(","), supportemailaddress=getconfig('SupportEmailAddress'), \
                                now=now, \
                                playcount=count, \
                                )
    except Exception as ex:
        log('Failed to display page to user %s %s with exception: %s.' % (thisuser.firstname, thisuser.lastname, ex))
        session.rollback()
        session.close()
        return render_template('errorpage.html', \
                            thisuser=thisuser, \
                            campname=getconfig('Name'), favicon=getconfig('Favicon_URL'), instrumentlist=getconfig('Instruments').split(","), supportemailaddress=getconfig('SupportEmailAddress'), \
                            errormessage = 'Failed to display page with exception: %s.' % ex
                            )

@app.route('/user/<userid>/musiclibrary/')
def musiclibrary(userid):

    session = Session()
    #gets the data associated with this user
    thisuser = session.query(user).filter(user.userid == userid).first()
    if thisuser is None:
        return ('Did not find user in database. You have entered an incorrect URL address.')
    
    musics = session.query(music).all()
    grouptemplates = session.query(grouptemplate).filter(grouptemplate.size == 'S').all()
    session.close()
    return render_template('musiclibrary.html', \
                            thisuser=thisuser, \
                            musics=musics, \
                            grouptemplates=grouptemplates, \
                            campname=getconfig('Name'), favicon=getconfig('Favicon_URL'), instrumentlist=getconfig('Instruments').split(","), supportemailaddress=getconfig('SupportEmailAddress'), \
                            )
    """except Exception as ex:
        log('Failed to display page to user %s %s with exception: %s.' % (thisuser.firstname, thisuser.lastname, ex))
        session.rollback()
        session.close()
        return render_template('errorpage.html', \
                            thisuser=thisuser, \
                            campname=getconfig('Name'), favicon=getconfig('Favicon_URL'), instrumentlist=getconfig('Instruments').split(","), supportemailaddress=getconfig('SupportEmailAddress'), \
                            errormessage = 'Failed to display page with exception: %s.' % ex
                            )"""

#Handles the group request page. If a user visits the page, it gives them a form to create a new group request. Pressing submit 
#sends a post containing configuration data. Their group request is queued until an adminsitrator approves it and assigns it to 
#a period.
@app.route('/user/<userid>/grouprequest/', methods=['GET', 'POST'])
def grouprequest(userid,periodid=None,musicid=None):
    
    session = Session()
    #gets the data associated with this user
    thisuser = session.query(user).filter(user.userid == userid).first()
    if thisuser is None:
        return ('Did not find user in database. You have entered an incorrect URL address.')

    today = datetime.datetime.combine(datetime.date.today(), datetime.time.min) #get today's date
    intwodays = today + datetime.timedelta(days=2)
    now = datetime.datetime.now() #get the time now
    #if this camper is inactive, has not arrived at camp yet, or is departing before the end of tomorrow
    if (thisuser.isactive != 1 or thisuser.arrival > now or thisuser.departure < intwodays) and periodid is None:
        session.close()
        return render_template('errorpage.html', \
                            thisuser=thisuser, \
                            campname=getconfig('Name'), favicon=getconfig('Favicon_URL'), instrumentlist=getconfig('Instruments').split(","), supportemailaddress=getconfig('SupportEmailAddress'), \
                            errormessage = 'Your user is currently set to inactive or are not attending camp at this time. Inactive users cannot request groups. Navigate to your settings and change them, or revisit this page at another time.'
                            )

    #find the instruments this user plays
    thisuserinstruments = session.query(instrument).filter(instrument.userid == userid, instrument.isactive == 1).all()
    thisuserinstruments_serialized = [i.serialize for i in thisuserinstruments]

    #check if this user is really a conductor and actually requested a conductorpage for a specific period
    if thisuser.isconductor == 1 and periodid is not None:
        conductorpage = True
        thisperiod = session.query(period).filter(period.periodid == periodid).first()
        if thisperiod is None:
            return ('Did not find period in database. Something has gone wrong.')
    elif thisuserinstruments is None:
        session.close()
        return render_template('errorpage.html', \
                            thisuser=thisuser, \
                            campname=getconfig('Name'), favicon=getconfig('Favicon_URL'), instrumentlist=getconfig('Instruments').split(","), supportemailaddress=getconfig('SupportEmailAddress'), \
                            errormessage = 'You do not play any instruments. You cannot make a group request.'
                            )
    else:
        conductorpage = False
        thisperiod = None

    #if this user isn't a conductor and/or they didn't request the conductor page and they've already surpassed their group-per-day limit, deny them.
    if conductorpage == False:
        if thisuser.grouprequestcount == 0 or thisuser.grouprequestcount == None or thisuser.grouprequestcount == '':
            thisuser.grouprequestcount = 0
            alreadyrequestedratio = 0
        log('User has requested %s groups since the start of camp. Maximum allowance is %s per day, and there have been %s days of camp so far.' \
            % (thisuser.grouprequestcount, getconfig('DailyGroupRequestLimit'), \
            (now - datetime.datetime.strptime(getconfig('StartTime'), '%Y-%m-%d %H:%M')).days))
        if thisuser.grouprequestcount >= (now - datetime.datetime.strptime(getconfig('StartTime'), '%Y-%m-%d %H:%M')).days * int(getconfig('DailyGroupRequestLimit')):
            log('This user is denied access to request another group.')
            session.close()
            return render_template('errorpage.html', \
                                thisuser=thisuser, \
                                campname=getconfig('Name'), favicon=getconfig('Favicon_URL'), instrumentlist=getconfig('Instruments').split(","), supportemailaddress=getconfig('SupportEmailAddress'), \
                                errormessage = ("You have requested %s groups throughout the camp, and you're allowed %s per day. Unfortunately, the camp has been running %s days and you've reached the limit. Please come back tomorrow!" % (thisuser.grouprequestcount, getconfig('DailyGroupRequestLimit'), (now - datetime.datetime.strptime(getconfig('StartTime'), '%Y-%m-%d %H:%M')).days))
                                )
        
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
                return render_template('errorpage.html', \
                                thisuser=thisuser, \
                                campname=getconfig('Name'), favicon=getconfig('Favicon_URL'), instrumentlist=getconfig('Instruments').split(","), supportemailaddress=getconfig('SupportEmailAddress'), \
                                errormessage = ("You have requested music that could not be found in the database. Talk to the administrator." % (thisuser.grouprequestcount, getconfig('DailyGroupRequestLimit'), (now - datetime.datetime.strptime(getconfig('StartTime'), '%Y-%m-%d %H:%M')).days))
                                )
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
        #format the packet received from the server as JSON
        content = request.json
        session = Session()
        log('Grouprequest received. Whole content of JSON returned is: %s' % content)
        #if we received too many players, send the user an error
        if len(content['objects']) > int(getconfig('GroupRequestPlayerLimit')) and conductorpage == False:
            session.rollback()
            session.close()
            return jsonify(message = 'You have entered too many players. You may only submit grouprequests of players %s or less.' % getconfig('GroupRequestPlayerLimit'), url = 'none')
        if len(content['objects']) == 0:
            session.rollback()
            session.close()
            return jsonify(message = 'You must have at least one player in the group', url = 'none')
        #establish the 'grouprequest' group object. This will be built up from the JSON packet, and then added to the database
        #a minimumlevel and maximumlevel of 0 indicates that they will be automatically be picked on group confirmation
        grouprequest = group(ismusical = 1, requesteduserid = userid, requesttime = datetime.datetime.now(), minimumlevel = 0, maximumlevel = 0)
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
            grouprequest.status = "Confirmed"
        #for each player object in the players array in the JSON packet
        for p in content['objects']:
            #if it's not a blank dropdown
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
            log('Incrementing group counter for instrument %s' % p['instrumentname'])
            #increment the instrument counter in the grouprequest object corresponding with this instrument name
            currentinstrumentcount = getattr(grouprequest, p['instrumentname'])
            if currentinstrumentcount is None:
                setattr(grouprequest, p['instrumentname'], 1)
            else:
                setattr(grouprequest, p['instrumentname'], (currentinstrumentcount + 1))
        if content['groupname'] != '':
            grouprequest.groupname = content['groupname']
        else:
            #run the getgroupname function, which logically names the group
            grouprequest.groupname = getgroupname(grouprequest)
        #if we are on the conductorpage, instantly confirm this group (assign it to the period the user submitted)
        if conductorpage == True:
            grouprequest.periodid = thisperiod.periodid     
        
        #--------MATCHMAKING SECTION-----------
        #try to find an existing group request with the same configuration as the request, and open instrument slots for all the players
        instrumentlist = getconfig('Instruments').split(",")
        matchinggroups = session.query(group).filter(group.iseveryone == None, group.ismusical == 1, group.periodid == None, *[getattr(grouprequest,i) == getattr(group,i) for i in instrumentlist]).\
            order_by(group.requesttime).all()
        Match = False
        #if we found at least one matching group
        if matchinggroups is not None:
            #check each group that matched the instrumentation for player slots
            for m in matchinggroups:
                clash = False
                log("INSTRUMENTATION MATCH FOUND requested by %s at time %s" % (m.requesteduserid, m.requesttime))
                if (m.music is not None and m.music != '') or \
                    (content['music'] is not None and content['music'] != '' and content['music'] != 'null') or (content['music'] == m.music):
                    #for each specific player in the request, check if there's a free spot in the matching group
                    #for each player in the group request
                    for p in content['objects']:
                        #if it's a named player, not a blank drop-down
                        if p['userid'] != 'null' and p['userid'] != '':
                            #find a list of players that are already assigned to this group, and play the instrument requested by the grouprequest
                            instrumentclash = session.query(groupassignment).filter(groupassignment.instrumentname == p['instrumentname'],\
                                groupassignment.groupid == m.groupid).all()
                            #if the list of players already matches the group instrumentation for this instrument, this match fails and break out
                            if instrumentclash is not None and instrumentclash != []:
                                if len(instrumentclash) >= getattr(m, p['instrumentname']):
                                    log('Found group not suitable, does not have an open slot for this player.')
                                    clash = True
                                    break
                            #found out if this player is already playing in the found group and make a clash if they are
                            playerclash = session.query(groupassignment).filter(groupassignment.userid == p['userid'], groupassignment.groupid == m.groupid).all()
                            if playerclash is not None and playerclash != []:
                                log('Found group not suitable, already has this player playing in it. Found the following group assignment: %s' % playerclash)
                                clash = True
                                break
                    #if we didn't have a clash while iterating over this group, we have a match! set the grouprequest group to be the old group and break out
                    if clash == False:
                        log('Match found. Adding the players in this request to the already formed group.')
                        grouprequest = m
                        #if the original group doesn't have music already assigned, we can assign it music from the user request
                        if (grouprequest.music is None or grouprequest.music == '' or grouprequest.music == 'null') and (content['music'] != ''):
                            grouprequest.music = content['music']
                        match = True
                        break
                else:
                    log('Music doesnt match the found group. Requested group music: %s. Database group music: %s' % (content['music'], m.music))
        #if we didn't get a match, we need to create the grouprequest, we won't be using an old one
        if Match == False:
            log('No group already exists with the correct instrumentation slots. Creating a new group.')
            #add the grouprequest to the database
            session.add(grouprequest)    
        #If we have got to here, the user successfully created their group (or was matchmade). We need to increment their total.
        thisuser.grouprequestcount = thisuser.grouprequestcount + 1
        log('%s %s has now made %s group requests' % (thisuser.firstname, thisuser.lastname, thisuser.grouprequestcount))
        #for each player object in the players array in the JSON packet
        for p in content['objects']:
            #if we are on the conductorpage, you cannot submit blank players. Give the user an error and take them back to their home.
            if (p['userid'] == 'null' or p['userid'] == '') and conductorpage == True:
                url = ('/user/' + str(thisuser.userid) + '/')
                session.rollback()
                session.close()
                return jsonify(message = 'You cannot have any empty player boxes in the group, because this is the conductor version of the group request page.', url = 'none')
            #if the playerid is not null, we create a groupassignment for them and bind it to this group
            if p['userid'] != 'null' and p['userid'] != '':
                playeruser = session.query(user).filter(user.userid == p['userid']).first()
                if playeruser is not None:
                    playergroupassignment = groupassignment(userid = playeruser.userid, groupid = grouprequest.groupid, instrumentname = p['instrumentname'])
                    session.add(playergroupassignment)
                else:
                    url = ('/user/' + str(thisuser.userid) + '/')
                    session.rollback()
                    session.close()
                    return jsonify(message = 'Could not find one of your selected players in the database. Please refresh the page and try again.', url = url)
            #if none of the above are satisfied - that's ok. you're allowed to submit null playernames in the user request page, these will be 
            #allocated by the admin when the group is confirmed.
        
        #create the group and the groupassinments configured above in the database
        session.merge(thisuser)
        session.commit()
        #send the URL for the group that was just created to the user, and send them to that page
        url = ('/user/' + str(thisuser.userid) + '/group/' + str(grouprequest.groupid) + '/')
        log('Sending user to URL: %s' % url)
        session.close()
        return jsonify(message = 'none', url = url)

    """except Exception as ex:
        log('Failed to display page to user %s %s with exception: %s.' % (thisuser.firstname, thisuser.lastname, ex))
        session.rollback()
        session.close()
        return render_template('errorpage.html', \
                            thisuser=thisuser, \
                            campname=getconfig('Name'), favicon=getconfig('Favicon_URL'), instrumentlist=getconfig('Instruments').split(","), supportemailaddress=getconfig('SupportEmailAddress'), \
                            errormessage = 'Failed to display page with exception: %s.' % ex
                            )"""

@app.route('/user/<userid>/grouprequest/conductor/<periodid>/', methods=['GET', 'POST'])
def conductorgrouprequest(userid,periodid):
    
    session = Session()
    #gets the data associated with this user
    thisuser = session.query(user).filter(user.userid == userid).first()
    if thisuser is None:
        return ('Did not find user in database. You have entered an incorrect URL address.')
    if thisuser.isconductor != 1:
        return ('You are not a conductor and cannot visit this page.')
    session.close()
    return grouprequest(userid,periodid,None)

@app.route('/user/<userid>/grouprequest/music/<musicid>/', methods=['GET', 'POST'])
def musicgrouprequest(userid,musicid):
    return grouprequest(userid,None,musicid)


#This page is used by an "announcer" to edit the announcement that users see when they open their homes
@app.route('/user/<userid>/announcement/', methods=['GET', 'POST'])
def announcementpage(userid):
    
    session = Session()
    #gets the data associated with this user
    thisuser = session.query(user).filter(user.userid == userid).first()
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
                url = ('/user/' + str(thisuser.userid) + '/')
                session.close()
                #send the user back to their home
                return jsonify(message = 'none', url = url)

    except Exception as ex:
        log('Failed to display page to user %s %s with exception: %s.' % (thisuser.firstname, thisuser.lastname, ex))
        session.rollback()
        session.close()
        return render_template('errorpage.html', \
                            thisuser=thisuser, \
                            campname=getconfig('Name'), favicon=getconfig('Favicon_URL'), instrumentlist=getconfig('Instruments').split(","), supportemailaddress=getconfig('SupportEmailAddress'), \
                            errormessage = 'Failed to display page with exception: %s.' % ex
                            )

#This page shows the queued groups, it is only accessible by the admin
@app.route('/user/<userid>/groupqueue/')
def groupqueue(userid):
    session = Session()
    #gets the data associated with this user
    thisuser = session.query(user).filter(user.userid == userid).first()
    if thisuser is None:
        return ('Did not find user in database. You have entered an incorrect URL address.')
    try:
        if thisuser.isadmin != 1:
            session.close()
            return 'You do not have permission to view this page'
        else:
            queuedgroups = session.query(group.groupid, group.requesttime, group.status, group.groupname, period.periodname, period.starttime, period.endtime, user.firstname, user.lastname).\
                outerjoin(period).outerjoin(user).filter(group.status == "Queued", user.isactive == 1).order_by(group.requesttime).all()
            log("Found %s queued groups to show the user" % len(queuedgroups))
            session.close()
            return render_template('groupqueue.html', \
                                    queuedgroups=queuedgroups, \
                                    thisuser=thisuser, \
                                    campname=getconfig('Name'), favicon=getconfig('Favicon_URL'), instrumentlist=getconfig('Instruments').split(","), supportemailaddress=getconfig('SupportEmailAddress'), \
                                    )

    except Exception as ex:
        log('Failed to display page to user %s %s with exception: %s.' % (thisuser.firstname, thisuser.lastname, ex))
        session.rollback()
        session.close()
        return render_template('errorpage.html', \
                            thisuser=thisuser, \
                            campname=getconfig('Name'), favicon=getconfig('Favicon_URL'), instrumentlist=getconfig('Instruments').split(","), supportemailaddress=getconfig('SupportEmailAddress'), \
                            errormessage = 'Failed to display page with exception: %s.' % ex
                            )

#This page is for creating a public event. It comes up as an option for adminsitrators on their homes
@app.route('/user/<userid>/publicevent/<periodid>/', methods=['GET', 'POST'])
def publiceventpage(userid,periodid):

    session = Session()
    #gets the data associated with this user
    thisuser = session.query(user).filter(user.userid == userid).first()
    if thisuser is None:
        return ('Did not find user in database. You have entered an incorrect URL address.')
    try:
        if thisuser.isadmin != 1:
            session.close()
            return 'You do not have permission to view this page'
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
                session.add(event)
                session.commit()
                url = ('/user/' + str(thisuser.userid) + '/group/' + str(event.groupid) + '/')
                session.close()
                return jsonify(message = 'none', url = url)

    except Exception as ex:
        log('Failed to display page to user %s %s with exception: %s.' % (thisuser.firstname, thisuser.lastname, ex))
        session.rollback()
        session.close()
        return render_template('errorpage.html', \
                            thisuser=thisuser, \
                            campname=getconfig('Name'), favicon=getconfig('Favicon_URL'), instrumentlist=getconfig('Instruments').split(","), supportemailaddress=getconfig('SupportEmailAddress'), \
                            errormessage = 'Failed to display page with exception: %s.' % ex
                            )

#this page is the full report for any given period
@app.route('/user/<userid>/period/<periodid>/')
def periodpage(userid,periodid):
    session = Session()
    #gets the data associated with this user
    thisuser = session.query(user).filter(user.userid == userid).first()
    if thisuser is None:
        return ('Did not find user in database. You have entered an incorrect URL address.')
    try:
        thisperiod = session.query(period).filter(period.periodid == periodid).first()
        #find any public events on during this period
        publicevents = session.query(group.groupname,group.groupid).filter(group.iseveryone == 1).filter(group.periodid == periodid).all()
        #start with the players that are playing in groups in the period
        players = session.query(user.userid, user.firstname, user.lastname, period.starttime, period.endtime, group.groupname,\
            groupassignment.instrumentname, location.locationname, groupassignment.groupid).\
            join(groupassignment).join(group).join(period).outerjoin(location).\
            filter(user.arrival <= thisperiod.starttime, user.departure >= thisperiod.endtime, group.periodid == thisperiod.periodid, group.status == 'Confirmed', group.groupname != 'absent').order_by(group.groupid,groupassignment.instrumentname).all()
        #grab just the userids of those players to be used in the next query
        players_in_groups_query = session.query(user.userid).\
            join(groupassignment).join(group).join(period).\
            filter(user.isactive == 1, user.arrival <= thisperiod.starttime, user.departure >= thisperiod.endtime, group.periodid == thisperiod.periodid, group.status == 'Confirmed')
        #find all other players to be displayed to the user
        nonplayers = (session.query(user.userid, user.firstname, user.lastname).filter(~user.userid.in_(players_in_groups_query), user.isactive == 1, user.arrival <= thisperiod.starttime, user.departure >= thisperiod.endtime).all())
        thisperiod = session.query(period).filter(period.periodid == periodid).first()
        session.close()
        return render_template('periodpage.html', \
                                players=players, \
                                publicevents=publicevents, \
                                nonplayers=nonplayers, \
                                campname=getconfig('Name'), favicon=getconfig('Favicon_URL'), instrumentlist=getconfig('Instruments').split(","), supportemailaddress=getconfig('SupportEmailAddress'), \
                                thisuser=thisuser, \
                                thisperiod=thisperiod, \
                                )
    except Exception as ex:
        log('Failed to display page to user %s %s with exception: %s.' % (thisuser.firstname, thisuser.lastname, ex))
        session.rollback()
        session.close()
        return render_template('errorpage.html', \
                            thisuser=thisuser, \
                            campname=getconfig('Name'), favicon=getconfig('Favicon_URL'), instrumentlist=getconfig('Instruments').split(","), supportemailaddress=getconfig('SupportEmailAddress'), \
                            errormessage = 'Failed to display page with exception: %s.' % ex
                            )

#handles the admin page
@app.route('/user/<userid>/useradmin/')
def useradmin(userid):

    session = Session()
    #gets the data associated with this user
    thisuser = session.query(user).filter(user.userid == userid).first()
    if thisuser is None:
        return ('Did not find user in database. You have entered an incorrect URL address.')
    try:
        #check if this user is a conductor, if they are not, deny them.
        if thisuser.isadmin != 1 and thisuser.userid != getconfig('AdminUUID'):
            return ('You are not allowed to view this page.')
        else:
            #get the list of people that play instruments
            players_query = session.query(instrument.userid).filter(instrument.isactive == 1)
            #get the players that have not played yet in this camp, add a 0 playcount to them and append them to the list
            already_played_query = session.query(user.userid).join(groupassignment).join(group).filter(group.ismusical == 1, group.status == 'Confirmed', user.userid.in_(players_query))
            users = session.query(user.userid, user.isactive, user.firstname, user.lastname, sqlalchemy.sql.expression.literal_column("0").label("playcount")).\
                            filter(~user.userid.in_(already_played_query)).filter(user.userid.in_(players_query)).all()
            #append the players that have already played.
            for p in (session.query(user.userid, user.isactive, user.firstname, user.lastname, func.count(groupassignment.userid).label("playcount")).group_by(user.userid).outerjoin(groupassignment).outerjoin(group).\
                        filter(group.ismusical == 1, group.status == 'Confirmed', user.userid.in_(players_query)).order_by(func.count(groupassignment.userid)).all()):
                users.append(p)
            #get the inverse of that - the non-players and add it to the list
            for p in (session.query(user.userid, user.firstname, user.lastname, sqlalchemy.sql.expression.literal_column("'Non Player'").label("playcount")).filter(~user.userid.in_(players_query)).all()):
                users.append(p)
            return render_template('useradmin.html', \
                                thisuser=thisuser, \
                                users=users, \
                                campname=getconfig('Name'), favicon=getconfig('Favicon_URL'), instrumentlist=getconfig('Instruments').split(","), supportemailaddress=getconfig('SupportEmailAddress'), \
                                )
    except Exception as ex:
        log('Failed to display page to user %s %s with exception: %s.' % (thisuser.firstname, thisuser.lastname, ex))
        session.rollback()
        session.close()
        return render_template('errorpage.html', \
                            thisuser=thisuser, \
                            campname=getconfig('Name'), favicon=getconfig('Favicon_URL'), instrumentlist=getconfig('Instruments').split(","), supportemailaddress=getconfig('SupportEmailAddress'), \
                            errormessage = 'Failed to display page with exception: %s.' % ex
                            )

#handles the useredit page
@app.route('/user/<userid>/edituser/<targetuserid>/', methods=['GET', 'POST'])
def edituser(userid, targetuserid):
    session = Session()
    #gets the data associated with this user
    thisuser = session.query(user).filter(user.userid == userid).first()
    if thisuser is None:
        return ('Did not find user in database. You have entered an incorrect URL address.')
    try:
        if targetuserid is not None:
            targetuser = session.query(user).filter(user.userid == targetuserid).first()
            if targetuser is None:
                    return 'Could not find requested user in database'
            elif thisuser.isadmin != 1 and thisuser.userid != targetuser.userid:
                session.close()
                return 'You do not have permission to view this page'
        else:
            targetuser = user()
        targetuserinstruments = session.query(instrument).filter(instrument.userid == targetuser.userid).all()
        periods = session.query(period).all()
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
            if content['arrival'] >= content['departure']:
                        session.rollback()
                        session.close()
                        return jsonify(message = 'Your departure time must be after your arrival time.', url = 'none')
            if thisuser.isadmin == 1:
                if content['firstname'] == '' or content['firstname'] == 'null' or content['firstname'] == 'None' or \
                            content['lastname'] == '' or content['lastname'] == 'null' or content['lastname'] == 'None':
                    session.rollback()
                    session.close()
                    return jsonify(message = 'You cannot save a user without a firstname and lastname.', url = 'none')
                #is this user doesn't have an ID yet, they are new and we must set them up
                if targetuser.userid is None:
                    #assign them a userid from a randomly generated uuid
                    targetuser.userid = str(uuid.uuid4())
                    session.add(targetuser)

            #add the content in the packet to this group's attributes
            for key,value in content.iteritems():
                if (thisuser.isadmin != 1 and thisuser.isadmin != '1') and key != 'arrival' and key != 'departure' and key != 'isactive' and key != 'submittype' and key != 'objects':
                    session.rollback()
                    session.close()
                    return jsonify(message = 'Users are not allowed to edit this attribute. The page should not have given you this option.', url = 'none')
                elif not isinstance(value, list) and value is not None and value != 'null' and value != '' and value != 'None' and value != '<HIDDEN>':
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
                for key,value in i.iteritems():
                    if thisuser.isadmin != 1 and key != isactive and key != isprimary:
                        session.rollback()
                        session.close()
                        return jsonify(message = 'You have submitted illegal parameters for your instrument. No changes have been made to your instrument listings.', url = 'none')
                    elif key != 'instrumentid' and value != 'None':
                        setattr(thisinstrument,key,value)
                session.merge(thisinstrument)
            session.commit()

            if content['submittype'] == 'submit':
                url = '/user/' + str(thisuser.userid) + '/'
                message = 'none'
            elif content['submittype'] == 'save':
                if targetuserid is None:
                    url = ('/user/' + str(thisuser.userid) + '/edituser/' + str(targetuser.userid) + '/')
                    message = 'none'
                else:
                    if newinstrument == True:
                        url = 'refresh'
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
        log('Failed to display page to user %s %s with exception: %s.' % (thisuser.firstname, thisuser.lastname, ex))
        session.rollback()
        session.close()
        return render_template('errorpage.html', \
                            thisuser=thisuser, \
                            campname=getconfig('Name'), favicon=getconfig('Favicon_URL'), instrumentlist=getconfig('Instruments').split(","), supportemailaddress=getconfig('SupportEmailAddress'), \
                            errormessage = 'Failed to display page with exception: %s.' % ex
                            )

@app.route('/user/<userid>/newuser/', methods=['GET', 'POST'])
def newuser(userid):
    return edituser(userid,None)

@app.route('/user/<userid>/settings/', methods=['GET', 'POST'])
def settings(userid):
    return edituser(userid,userid)

#sends bulk emails to an array of users sent with the request
@app.route('/user/<userid>/email/', methods=['POST'])
def send_home_link_email(userid):

    session = Session()
    #gets the data associated with this user
    thisuser = session.query(user).filter(user.userid == userid).first()
    if thisuser is None:
        return ('Did not find user in database. You have entered an incorrect URL address.')
    try:
        if thisuser.isadmin != 1:
            session.close()
            return 'You do not have permission to view this page'
        content = request.json
        errors = ''
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
WARNING: DO NOT GIVE THIS LINK TO ANYONE ELSE. It is yours, and yours alone and contains your connection credentials.\n
A small rundown of how to use the web app:\n
    -Visit this page each day to see your schedule, including times, locations, and the instrument you're playing. Don't forget to refresh it, your phone may not refresh the page if you minimise it and come back to it later.
    -You can click into group names to to see possible substitute players and get further details, or a time period to see the full group listing for that time. Clicking the home button in the top left of your screen will always bring you back to your schedule on the current day.
    -You can look at your schedule for future and past days drop down date picker, and the forward and back links on your home screen.
    -If you're going to be absent for a session or meal, plesae notify us at least one day before by navigating to a future date, clicking the tools tab on your homepage, then clicking the "Mark me as absent" button next to the corresponding time.
    -You can request groups with the request group link on the left (on a mobile, click on the hamburger menu on the top left of the screen). Fill in your desired instrumentation, and any players that you'd like to play with and press submit. Leaving blanks for player names is fine, you'll be matched up with other players at the end of the day.\n
If you have any questions, please reply to this email or contact us on %s.\n
Thanks!\n
%s %s
%s""" % (targetuser.firstname, \
                getconfig('Name'), \
                getconfig('EmailIntroSentence'), \
                getconfig('Website_URL'), \
                targetuser.userid, \
                getconfig('SupportEmailAddress'), \
                thisuser.firstname, \
                thisuser.lastname, \
                getconfig('Name')\
                )
                message = send_email(targetuser.email, subject, body)
                if message == 'Failed to send email to user':
                    errors = errors + ('Failed to send email to %s %s\n' % (targetuser.firstname, targetuser.lastname))
        session.close()
        if errors != '':
            message = 'Completed with errors:\n' + errors
        return jsonify(message = message, url = 'none')

    except Exception as ex:
        log('Failed to display page to user %s %s with exception: %s.' % (thisuser.firstname, thisuser.lastname, ex))
        session.rollback()
        session.close()
        return render_template('errorpage.html', \
                            thisuser=thisuser, \
                            campname=getconfig('Name'), favicon=getconfig('Favicon_URL'), instrumentlist=getconfig('Instruments').split(","), supportemailaddress=getconfig('SupportEmailAddress'), \
                            errormessage = 'Failed to display page with exception: %s.' % ex
                            )

#Handles the conductor instrumentation page.
@app.route('/user/<userid>/instrumentation/<periodid>/', methods=['GET', 'POST'])
def instrumentation(userid,periodid):

    session = Session()
    #gets the data associated with this user
    thisuser = session.query(user).filter(user.userid == userid).first()
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
                                    )
    
            #The below runs when a user presses "Submit" on the instrumentation page. It creates a group object with the configuraiton selected by 
            #the user, and creates groupassignments if needed
            if request.method == 'POST':
                #format the packet received from the server as JSON
                content = request.json
                session = Session()
                log('Grouprequest received. Whole content of JSON returned is: %s' % content)
                #establish the 'grouprequest' group object. This will be built up from the JSON packet, and then added to the database
                grouprequest = group(ismusical = 1, requesteduserid = userid, periodid = thisperiod.periodid, status = "Queued", requesttime = datetime.datetime.now())
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
                    if (key == 'groupname' or key == 'music' or key == 'maximumlevel' or key == 'mininumlevel') and value == '':
                        url = 'none'
                        log('Instrumentation creation failed, misconfiguration')
                        session.close()
                        session.rollback()
                        return jsonify(message = 'Could not create instrumentation, you must enter a groupname, music, maximumlevel and mininumlevel', url = url)
                    setattr(grouprequest, key, value)
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
                url = ('/user/' + str(thisuser.userid) + '/group/' + str(grouprequest.groupid) + '/')
                log('Sending user to URL: %s' % url)
                session.close()
                return jsonify(message = 'none', url = url)

    except Exception as ex:
        log('Failed to display page to user %s %s with exception: %s.' % (thisuser.firstname, thisuser.lastname, ex))
        session.rollback()
        session.close()
        return render_template('errorpage.html', \
                            thisuser=thisuser, \
                            campname=getconfig('Name'), favicon=getconfig('Favicon_URL'), instrumentlist=getconfig('Instruments').split(","), supportemailaddress=getconfig('SupportEmailAddress'), \
                            errormessage = 'Failed to display page with exception: %s.' % ex
                            )

#Application setup page. This needs to be run at the start, just after the app has been deployed. The user uploads config files and user lists to populate the database.
@app.route('/user/<userid>/setup/', methods=["GET", "POST"])
def setup(userid):

    session = Session()
    #gets the data associated with this user
    thisuser = session.query(user).filter(user.userid == userid).first()
    if thisuser is None:
        session.close()
        return ('Did not find user in database. You have entered an incorrect URL address.')
    try:
        #check if this user is an admin or the Administrator superuser, if they are not, deny them.
        if thisuser.isadmin != 1 and thisuser.userid != getconfig('AdminUUID'):
            return ('You are not allowed to view this page.')
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
                        return dbbuild(file.read())
                    if filename == 'campers.csv':
                        return(importusers(file))
                    if filename == 'musiclibrary.csv':
                        return(importmusic(file))
    
    except Exception as ex:
        log('Failed to display page to user %s %s with exception: %s.' % (thisuser.firstname, thisuser.lastname, ex))
        session.rollback()
        session.close()
        return render_template('errorpage.html', \
                            thisuser=thisuser, \
                            campname=getconfig('Name'), favicon=getconfig('Favicon_URL'), instrumentlist=getconfig('Instruments').split(","), supportemailaddress=getconfig('SupportEmailAddress'), \
                            errormessage = 'Failed to display page with exception: %s.' % ex
                            )

#This page is viewable by the admin only, it lets them edit different objects in the database - grouptemplates, locations, periods, etc.
@app.route('/user/<userid>/objecteditor/<input>/', methods=["GET","POST","DELETE"])
def objecteditor(userid, input, objectid=None):

    session = Session()
    #gets the data associated with this user
    thisuser = session.query(user).filter(user.userid == userid).first()
    if thisuser is None:
        session.close()
        return ('Did not find user in database. You have entered an incorrect URL address.')
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
    else:
        session.close()
        return render_template('errorpage.html', \
                            thisuser=thisuser, \
                            campname=getconfig('Name'), favicon=getconfig('Favicon_URL'), instrumentlist=getconfig('Instruments').split(","), supportemailaddress=getconfig('SupportEmailAddress'), \
                            errormessage = 'Invalid input.'
                            )
    if request.method == 'GET':
        try:
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
            
        except Exception as ex:
            log('Failed to display page to user %s %s with exception: %s.' % (thisuser.firstname, thisuser.lastname, ex))
            session.rollback()
            session.close()
            return render_template('errorpage.html', \
                                thisuser=thisuser, \
                                campname=getconfig('Name'), favicon=getconfig('Favicon_URL'), instrumentlist=getconfig('Instruments').split(","), supportemailaddress=getconfig('SupportEmailAddress'), \
                                errormessage = 'Failed to display page with exception: %s.' % ex
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
                        session.add(object)
                    else:
                        log('Trying to find a %s object with id %s' % (table, o[table + 'id']))
                        object = objects_query.filter(getattr(globals()[table],(table + 'id')) == o[table + 'id']).first()
                        if object is None:
                            session.rollback()
                            session.close()
                            return jsonify(message = 'Could not find one of your requested objects. This is a malformed request packet.', url = 'none')
                    for key, value in o.iteritems():
                        if key != table + 'id':
                            log('Changing object %s key %s to %s' % (table, key, value))
                            setattr(object,key,value)
                    session.merge(object)
                    url = '/user/' + thisuser.userid + '/objecteditor/' + table + '/'
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
            url = '/user/' + thisuser.userid + '/objecteditor/' + table + '/'
            session.commit()
            session.close()
            return jsonify(message = 'none', url = url)
        except Exception as ex:
            session.rollback()
            session.close()
            return jsonify(message = 'Failed to delete object with exception %s' % ex, url = 'none')

@app.route('/js/<path:path>')
def send_js(path):
    return send_from_directory('js', path)

@app.route('/css/<path:path>')
def send_css(path):
    return send_from_directory('css', path)

@app.route('/img/<path:path>')
def send_png(path):
    return send_from_directory('img', path)