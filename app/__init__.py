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
from DBSetup import *
from sqlalchemy import *
from config import *

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
            #if we don't find a player in this group, set the minimum level to be 1
            else: 
                level = 1
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
            #if we don't find a player in this group, set the maximum level to be the highest possible
            else:
                level = getconfig('MaximumLevel')
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

@app.route('/setup/', methods=["GET", "POST"])
def setup():
    global config
    if request.method == 'GET':
        return render_template('setup.html')
    if request.method == 'POST':
        # Get the name of the uploaded file
        file = request.files['file']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            if filename == 'config.xml':
                return dbbuild(file.read())
            if filename == 'campers.csv':
                return importusers(file)

#upon the URL request in the form domain/user/<userid> the user receives their home. The home contains the groups they 
#are playing in. Optionally, this page presents their home in the future or the past, and gives them further options.
@app.route('/user/<userid>/')
def home(userid,inputdate='n'):
    log('home fetch requested for user %s' % userid)
    log('date modifier is currently set to %s' % inputdate)
    session = Session()
    #gets the data associated with this user
    thisuser = session.query(user).filter(user.userid == userid).first()
    if thisuser is None:
        return ('Did not find user in database. You have entered an incorrect URL address.')       
    #find the number of times a user has played in groups in the past
    count = playcount(session, userid)
    #get the current announcement
    currentannouncement = session.query(announcement).order_by(desc(announcement.creationtime)).first()
    #get impontant datetimes
    today = datetime.datetime.combine(datetime.date.today(), datetime.time.min) #get today's date
    #if the suer has submitted a date, convert it to a datetime and use it as the display date
    if inputdate != 'n': 
        displaydate = datetime.datetime.strptime(inputdate, '%Y-%m-%d')
    #if the user has not submitted a date and today is before the start of camp, use the first day of camp as the display date
    elif today < datetime.datetime.strptime(getconfig('StartTime'), '%Y-%m-%d %H:%M'): 
        displaydate = datetime.datetime.strptime(getconfig('StartTime').split()[0], '%Y-%m-%d')
        log(displaydate)
    #if today is after the start of camp, use today as the display date
    else:
        displaydate = today
    
    previousday = displaydate + datetime.timedelta(days=-1)
    nextday = displaydate + datetime.timedelta(days=1)

    #get the information needed to fill in the user's schedule table
    periods = []
    #for each period in the requested day
    for p in session.query(period).filter(period.starttime > displaydate, period.endtime < nextday).all():
        #try to find a group assignment for the user
        log('Attempting to find group assignment for user for period %s with id %s' % (p.periodname, p.periodid))
        g = session.query(group.groupname, period.starttime, period.endtime, location.locationname, group.groupid, group.ismusical, \
                            group.iseveryone, period.periodid, period.periodname, groupassignment.instrumentname).\
                            join(period).join(groupassignment).join(user).join(instrument).outerjoin(location).\
                            filter(user.userid == userid, group.periodid == p.periodid, group.status == 'Confirmed').first()
        if g is not None:
            log('Found group assignment named %s' % g.groupname)
            periods.append(g)
        e = None
        #if we didn't find an assigned group...
        if g is None:
            log('Failed')
            #try to find an iseveryone group at the time of this period
            log('Attempting to find an "iseveryone" group for period %s with Id %s' % (p.periodname, p.periodid))
            e = session.query(group.groupname, period.starttime, period.endtime, location.locationname, group.groupid, group.ismusical, \
                            group.iseveryone, period.periodid, period.periodname).\
                            join(period).join(location).\
                            filter(group.iseveryone == 1, group.periodid == p.periodid).first()
        if e is not None:
            log('Found an "iseveryone" group named %s, from %s to %s' % (e.groupname, e.starttime, e.endtime))
            periods.append(e)
        #if we didn't find an assigned group or an iseveryone group...
        if e is None and g is None:
            #just add the period detalis
            log('Failed')
            log("Couldn't find a group during period %s. Adding the period details." % p.periodname)
            periods.append(p)

    session.close()

    return render_template('home.html', \
                        thisuser=thisuser, \
                        count=count, \
                        date=displaydate,\
                        periods=periods, \
                        previousday=datetime.datetime.strftime(previousday, '%Y-%m-%d'), \
                        nextday=datetime.datetime.strftime(nextday, '%Y-%m-%d'), \
                        today=today, \
                        campname=getconfig('Name'), \
                        supportemailaddress=getconfig('SupportEmailAddress'), \
                        currentannouncement=currentannouncement, \
                        )

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

#The group page displays all the people in a given group, along with possible substitutes
@app.route('/user/<userid>/group/<groupid>/')
def grouppage(userid,groupid):
    log('Group page requested by %s for groupID %s' % (userid,groupid))
    session = Session()
    #gets the data associated with this user
    thisuser = session.query(user).filter(user.userid == userid).first()
    if thisuser is None:
        return ('Did not find user in database. You have entered an incorrect URL address.')
    thisgroup = session.query(group).filter(group.groupid == groupid).first()
    thislocation = session.query(location).join(group).filter(group.groupid == groupid).first()
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
            filter(~user.userid.in_(everyone_playing_in_periodquery)).\
            filter(instrument.instrumentname.in_(instruments_in_group_query), instrument.grade >= minimumgrade, instrument.grade <= maximumgrade).\
            order_by(instrument.instrumentname)
    else:
        substitutes = None

    session.close()
    return render_template('group.html', \
                        period=thisperiod, \
                        campname=getconfig('Name'), \
                        thisgroup=thisgroup, \
                        players=players, \
                        substitutes=substitutes, \
                        thisuser=thisuser, \
                        thislocation=thislocation, \
                        instrumentlist=getconfig('Instruments').split(","), \
                        )

#Group editor page. Only accessable by admins. Navigate here from a group to edit group.
@app.route('/user/<userid>/group/<groupid>/edit/', methods=['GET', 'POST', 'DELETE'])
def groupedit(userid,groupid,periodid=None):
    
    log('Group editor page requested by %s for groupID %s' % (userid,groupid))
    session = Session()
    #gets the data associated with this user
    thisuser = session.query(user).filter(user.userid == userid).first()
    if thisuser is None:
        session.close()
        return ('Did not find user in database. You have entered an incorrect URL address.')
    if thisuser.isadmin != 1:
        session.close()
        return 'You do not have permission to do this.'
    thisgroup = session.query(group).filter(group.groupid == groupid).first()
    if thisgroup is None:
        return ('Did not find group in database. You have entered an incorrect URL address.')
    if request.method == 'GET':
        #THIS NEEDS TO BE CHANGED TO AN ASYNC AJAX CALL UPON CHANGE OF THE DROPDOWN FOR PERIOD
        currentperiod = session.query(period).filter(period.periodid == thisgroup.periodid).first()
        if periodid is not None:
            selectedperiod = session.query(period).filter(period.periodid == periodid).first()
        elif currentperiod is not None:
            selectedperiod = currentperiod
        else:
            selectedperiod = session.query(period).filter(period.meal != 1).order_by(period.starttime).first()
        thislocation = session.query(location).join(group).filter(group.groupid == groupid).first()
        #gets the list of players playing in the given group
        thisgroupplayers = session.query(user.userid, user.firstname, user.lastname, groupassignment.instrumentname).join(groupassignment).join(group).\
                                filter(group.groupid == groupid).order_by(groupassignment.instrumentname).all()
        thisgroupplayers_serialized = []
        for p in thisgroupplayers:
             thisgroupplayers_serialized.append({'userid': p.userid, 'firstname': p.firstname, 'lastname': p.lastname,
                'instrumentname': p.instrumentname})
        #Finds all players who are already playing in this period (except in this specific group)
        playersPlayingInPeriod = session.query(user.userid).join(groupassignment).join(group).filter(group.groupid != thisgroup.groupid).filter(group.periodid == selectedperiod.periodid)
        #finds all players who are available to play in this group (they aren't already playing in other groups)
        playersdump = session.query(user.userid,user.firstname,user.lastname,instrument.instrumentname,instrument.grade,instrument.isprimary).\
                    join(instrument).filter(~user.userid.in_(playersPlayingInPeriod)).all()
        playersdump_serialized = []
        for p in playersdump:
            playersdump_serialized.append({'userid': p.userid, 'firstname': p.firstname, 'lastname': p.lastname,
                'instrumentname': p.instrumentname, 'grade': p.grade, 'isprimary': p.isprimary})
        #UNFINISHED find the periods that the players in this group are unavailable
        #to do this, I think I need to join groups back onto itself. Need to look at documentation for this.

        #find the periods in which the players already in this group are available
        #UNFINISHED - finds every period instead as a workaround
        periods = session.query(period).order_by(period.starttime).all()
        locations = session.query(location).all()
        log('This groups status is %s' % thisgroup.status)

        session.close()
        return render_template('groupedit.html', \
                            currentperiod=currentperiod, \
                            selectedperiod=selectedperiod, \
                            campname=getconfig('Name'), \
                            thisgroup=thisgroup, \
                            thisgroupplayers=thisgroupplayers, \
                            thisuser=thisuser, \
                            periods=periods, \
                            thislocation=thislocation, \
                            locations=locations, \
                            instrumentlist=getconfig('Instruments').split(","), \
                            playersdump=playersdump, \
                            playersdump_serialized=playersdump_serialized, \
                            thisgroupplayers_serialized=thisgroupplayers_serialized, \
                            maximumlevel=int(getconfig('MaximumLevel')), \
                            )
    
    if request.method == 'DELETE':
        thisgroupassignments = session.query(groupassignment).filter(groupassignment.groupid == thisgroup.groupid).all()
        for a in thisgroupassignments:
            session.delete(a)
        session.commit()
        session.delete(thisgroup)
        session.commit()
        url = ('/user/' + str(thisuser.userid) + '/')
        log('Sending user to URL: %s' % url)
        session.close()
        return jsonify(message = 'none', url = url)

    if request.method == 'POST':
        #format the packet received from the server as JSON
        content = request.json
        session = Session()
        thisgroupassignments = session.query(groupassignment).filter(groupassignment.groupid == thisgroup.groupid).all()
        for a in thisgroupassignments:
            session.delete(a)
        #add the content in the packet to this group's attributes
        thisgroup.groupname = content['groupname']
        thisgroup.periodid = content['periodid']
        thisgroup.locationid = content['locationid']
        thisgroup.minimumlevel = content['minimumlevel']
        thisgroup.maximumlevel = content['maximumlevel']
        thisgroup.music = content['music']
        thisgroup.status = content['status']
        thisgroup.ismusical = content['ismusical']
        for i in getconfig('Instruments').split(","):
            log('Setting %s to %s' % (i,content[i]))
            setattr(thisgroup,i,content[i])
        foundempty = False
        foundfilled = True
        for p in content['players']:
                    if p['userid'] == '' or p['userid'] is None:
                        foundempty = True
                    #if the playerid is not null, we create a groupassignment for them and bind it to this group
                    else:
                        foundfilled = True
                        log('Attempting to find user %s' % p['userid'])
                        playeruser = session.query(user).filter(user.userid == p['userid']).first()
                        currentassignment = session.query(groupassignment.instrumentname, group.groupname, group.groupid).join(group).filter(groupassignment.userid == p['userid']).filter(group.periodid == content['periodid']).first()
                        if currentassignment is not None:
                            if currentassignment.groupid != thisgroup.groupid:
                                url = 'none'
                                session.close()
                                log('Found a clash for %s. They are alrdeay playing %s in %s. Refresh the page and try again.' % (playeruser.firstname, currentassignment.instrumentname, currentassignment.groupname))
                                return jsonify(message = ('Found a clash for %s. They are alrdeay playing %s in %s. Refresh the page and try again.' % (playeruser.firstname, currentassignment.instrumentname, currentassignment.groupname)), url = url)
                        if playeruser is not None:
                            playergroupassignment = groupassignment(userid = playeruser.userid, groupid = thisgroup.groupid, instrumentname = p['instrumentname'])
                            session.add(playergroupassignment)
                        else:
                            url = ('/user/' + str(thisuser.userid) + '/')
                            session.close()
                            return jsonify(message = 'Could not find one of your selected players in the database. Please refresh the page and try again.', url = url)
        if thisgroup.minimumlevel is None and foundfilled == False:
            session.rollback()
            session.close()
            return jsonify(message = 'You cannot have all empty players and an auto level. Set the level or at least one player.', url = 'none')
        if thisgroup.status == 'Confirmed' and (thisgroup.periodid == '' or thisgroup.groupname == '' or thisgroup.locationid == '' or foundempty == True):
            session.rollback()
            session.close()
            return jsonify(message = 'Confirmed groups must have a name, assigned period, assigned location and no empty player slots.', url = 'none')
        
        #----AUTOFILL SECTION----
        if content['autofill'] == '1':
            log('User selected to autofill the group')
            if content['periodid'] == '' or content['periodid'] is None:
                session.rollback()
                session.close()
                return jsonify(message = 'You must have a period selected before autofilling.', url = 'none')
            else:
                #get the minimum level of this group
                mingrade = getgrouplevel(session,thisgroup,'min')
                maxgrade = getgrouplevel(session,thisgroup,'max')
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
                            possible_players_query = session.query(user.userid).outerjoin(instrument).filter(~user.userid.in_(everyone_playing_in_period_query)).\
                                filter(instrument.grade >= mingrade, instrument.grade <= maxgrade).filter(instrument.instrumentname == i)
                            log('Found %s possible players of a requested %s for instrument %s.' % (len(possible_players_query.all()), requiredplayers, i))
                            if len(possible_players_query.all()) > 0:
                                #get the players that have already played in groups at this camp, and inverse it to get the players with playcounts of zero. Limit the query to just the spots we have left.
                                already_played_query = session.query(user.userid).join(groupassignment).join(group).filter(group.ismusical == 1).\
                                    filter(groupassignment.userid.in_(possible_players_query))
                                final_list = session.query(user.userid,sqlalchemy.sql.expression.literal_column("0").label("playcount")).filter(user.userid.in_(possible_players_query)).\
                                                filter(~user.userid.in_(already_played_query)).limit(requiredplayers).all()
                                #append the players that have already played. Keep the query limited to just the number we need.
                                if len(final_list) < requiredplayers:
                                    for p in (session.query(user.userid, func.count(groupassignment.userid).label("playcount")).group_by(user.userid).outerjoin(groupassignment).outerjoin(group).\
                                            filter(group.ismusical == 1).filter(groupassignment.userid.in_(possible_players_query)).order_by(func.count(groupassignment.userid)).limit(requiredplayers - len(final_list)).all()):
                                        final_list.append(p)
                                log('Players in final list with playcounts:')
                                #add groupassignments for the final player list
                                for pl in final_list:
                                    log('Selected %s with playcount %s to play %s' % (pl.userid, pl.playcount, i))
                                    playergroupassignment = groupassignment(userid = pl.userid, groupid = thisgroup.groupid, instrumentname = i)
                                    session.add(playergroupassignment)
                url = '/user/' + str(thisuser.userid) + '/group/' + str(thisgroup.groupid) + '/edit/'
        else:
            url = '/user/' + str(thisuser.userid) + '/group/' + str(thisgroup.groupid) + '/'
        session.merge(thisgroup)
        session.commit()
        session.close()
        return jsonify(message = 'none', url = url)
        
@app.route('/user/<userid>/group/<groupid>/period/<periodid>/edit/')
def groupeditperiod(userid,groupid,periodid):
    return groupedit(userid,groupid,periodid)

@app.route('/user/<userid>/grouphistory/')
def grouphistory(userid):
    session = Session()
    #gets the data associated with this user
    thisuser = session.query(user).filter(user.userid == userid).first()
    now = datetime.datetime.now() #get the time now
    if thisuser is None:
        return ('Did not find user in database. You have entered an incorrect URL address.')
    groups = session.query(group.groupname, group.groupid, period.periodid, period.starttime, period.endtime, groupassignment.instrumentname, group.status, location.locationname).\
                join(groupassignment).outerjoin(period).outerjoin(location).filter(groupassignment.userid == thisuser.userid).order_by(period.starttime)
    log(groups)
    return render_template('grouphistory.html', \
                            thisuser=thisuser, \
                            groups = groups, \
                            campname=getconfig('Name'), \
                            now=now, \
                            )

#Handles the group request page. If a user visits the page, it gives them a form to create a new group request. Pressing submit 
#sends a post containing configuration data. Their group request is queued until an adminsitrator approves it and assigns it to 
#a period.
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
    #if this user isn't a conductor and/or they didn't request the conductor page and they've already surpassed their group-per-day limit, deny them.
    #UNTESTED!!! WHEN DOING A TRIAL RUN THIS NEEDS TO BE TESTED.
    if conductorpage == False:
        if thisuser.grouprequestcount == 0 or thisuser.grouprequestcount == None or thisuser.grouprequestcount == '':
            thisuser.grouprequestcount = 0
            alreadyrequestedratio = 0
        log('User has requested %s groups since the start of camp. Maximum allowance is %s per day, and there have been %s days of camp so far.' \
            % (thisuser.grouprequestcount, getconfig('DailyGroupRequestLimit'), \
            (now - datetime.datetime.strptime(getconfig('StartTime'), '%Y-%m-%d %H:%M')).days))
        alreadyrequestedratio = (thisuser.grouprequestcount + 1)/(int(getconfig('DailyGroupRequestLimit'))*\
            (now - datetime.datetime.strptime(getconfig('StartTime'), '%Y-%m-%d %H:%M')).days)
        log('Ratio is currently at %s. If it is above one, the user is denied access to request another group.' % alreadyrequestedratio)
        if int(alreadyrequestedratio) >= 1:
            session.close()
            return ('You have already requested the maximum number of groups you can request in a single day. Please come back tomorrow!')
        
    #The below runs when a user visits the grouprequest page
    if request.method == 'GET':
        
        if conductorpage == True:
            #Finds all players who aren't already playing in this period
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
        #find the instruments this user plays
        thisuserinstruments = session.query(instrument).filter(instrument.userid == userid).all()
        thisuserinstruments_serialized = [i.serialize for i in thisuserinstruments]
        log(thisuserinstruments_serialized)

        #if this is the conductorpage, the user will need a list of the locations that are not being used in the period selected
        if conductorpage == True:
            locations_used_query = session.query(location.locationid).join(group).join(period).filter(period.periodid == periodid)
            locations = session.query(location).filter(~location.locationid.in_(locations_used_query)).all()
        else: 
            locations = None

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
        log(grouptemplates_serialized)
        session.close()
        return render_template('grouprequest.html', \
                            thisuser=thisuser, \
                            thisuserinstruments=thisuserinstruments, \
                            thisuserinstruments_serialized=thisuserinstruments_serialized, \
                            playerlimit = getconfig('SmallGroupPlayerLimit'), \
                            grouptemplates = grouptemplates, \
                            grouptemplates_serialized=grouptemplates_serialized, \
                            campname=getconfig('Name'), \
                            instrumentlist=getconfig('Instruments').split(","), \
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
        log('Grouprequest received. Whole content of JSON returned is: %s' % content)
        #establish the 'grouprequest' group object. This will be built up from the JSON packet, and then added to the database
        #a minimumlevel and maximumlevel of 0 indicates that they will be automatically be picked on group confirmation
        grouprequest = group(music = content['music'], ismusical = 1, requesteduserid = userid, requesttime = datetime.datetime.now(), minimumlevel = 0, maximumlevel = 0)
        #if the conductorpage is false, we need to set the status to queued
        if conductorpage == False:
            grouprequest.status = "Queued"
        #if the conductorpage is true, we expect to also receive a locationid from the JSON packet, so we add it to the grouprequest, we also confirm the request
        if conductorpage == True:
            grouprequest.locationid = content['locationid']
            grouprequest.status = "Confirmed"
        #for each player object in the players array in the JSON packet
        for p in content['players']:
            log('Incrementing group counter for instrument %s' % p['instrumentname'])
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
                    (content['music'] is not None and content['music'] != '' and content['music'] != 'null') or \
                    (content['music'] == m.music):
                    #for each specific player in the request, check if there's a free spot in the matching group
                    #for each player in the group request
                    for p in content['players']:
                        #if it's a named player, not a blank drop-down
                        if p['playerid'] != 'null':
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
                            playerclash = session.query(groupassignment).filter(groupassignment.userid == p['playerid'], groupassignment.groupid == m.groupid).all()
                            if playerclash is not None and playerclash != []:
                                log('Found group not suitable, already has this player playing in it. Found the following group assignment: %s' % playerclash)
                                clash = True
                                break
                    #if we didn't have a clash while iterating over this grou, we have a match! set the grouprequest group to be the old group and break out
                    if clash == False:
                        log('Match found. Adding the players in this request to the already formed group.')
                        grouprequest = m
                        #if the original group doesn't have music already assigned, we can assign it music from the user request
                        if grouprequest.music is not None and grouprequest.music != '' and grouprequest.music != 'null':
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
        for p in content['players']:
            #if we are on the conductorpage, you cannot submit blank players. Give the user an error and take them back to their home.
            if p['playerid'] == 'null' and conductorpage == True:
                url = ('/user/' + str(thisuser.userid) + '/')
                session.close()
                return jsonify(message = 'Something went wrong. You are not allowed to have null players in a conductor group request.', url = url)
            #if the playerid is not null, we create a groupassignment for them and bind it to this group
            if p['playerid'] != 'null':
                playeruser = session.query(user).filter(user.userid == p['playerid']).first()
                if playeruser is not None:
                    playergroupassignment = groupassignment(userid = playeruser.userid, groupid = grouprequest.groupid, instrumentname = p['instrumentname'])
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
        log('Sending user to URL: %s' % url)
        session.close()
        return jsonify(message = 'none', url = url)

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

#This page is used by an "announcer" to edit the announcement that users see when they open their homes
@app.route('/user/<userid>/announcement/', methods=['GET', 'POST'])
def announcementpage(userid):
    
    session = Session()
    #gets the data associated with this user
    thisuser = session.query(user).filter(user.userid == userid).first()
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
                                    campname=getconfig('Name'), \
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

#This page shows the queued groups, it is only accessible by the admin
@app.route('/user/<userid>/groupqueue/')
def groupqueue(userid):
    session = Session()
    #gets the data associated with this user
    thisuser = session.query(user).filter(user.userid == userid).first()
    if thisuser.isadmin != 1:
        session.close()
        return 'You do not have permission to view this page'
    else:
        queuedgroups = session.query(group.groupid, group.requesttime, group.status, group.groupname, period.starttime, period.endtime, user.firstname, user.lastname).\
            outerjoin(period).outerjoin(user).filter(group.status == "Queued").order_by(group.requesttime).all()
        log("Found %s queued groups to show the user" % len(queuedgroups))
        session.close()
        return render_template('groupqueue.html', \
                                queuedgroups=queuedgroups, \
                                thisuser=thisuser, \
                                campname=getconfig('Name'), \
                                )

#This page is for creating a public event. It comes up as an option for adminsitrators on their homes
@app.route('/user/<userid>/publicevent/<periodid>/', methods=['GET', 'POST'])
def publiceventpage(userid,periodid):
    session = Session()
    #gets the data associated with this user
    thisuser = session.query(user).filter(user.userid == userid).first()
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
                                    campname=getconfig('Name'), \
                                    )
        
        #if the user pressed "submit" on the public event page
        if request.method == 'POST':
            if request.json['location'] == '' or request.json['name'] == '':
                session.rollback()
                url = ('none')
                session.close()
                return jsonify(message = 'Submission failed. You must submit both an event name and location.', url = url)
            event = group(periodid = periodid, iseveryone = 1, groupname =  request.json['name'], requesteduserid = thisuser.userid,\
                ismusical = 0, locationid = request.json['location'], status = "Confirmed")
            session.add(event)
            session.commit()
            url = ('/user/' + str(thisuser.userid) + '/group/' + str(event.groupid) + '/')
            session.close()
            return jsonify(message = 'none', url = url)

#this page is the full report for any given period
@app.route('/user/<userid>/period/<periodid>/')
def periodpage(userid,periodid):
    session = Session()
    #gets the data associated with this user
    thisuser = session.query(user).filter(user.userid == userid).first()
    if thisuser is None:
        return ('Did not find user in database. You have entered an incorrect URL address.')
    #find any public events on during this period
    publicevents = session.query(group.groupname,group.groupid).filter(group.iseveryone == 1).filter(group.periodid == periodid).all()
    #start with the players that are playing in groups in the period
    players = session.query(user.userid, user.firstname, user.lastname, period.starttime, period.endtime, group.groupname,\
        groupassignment.instrumentname, location.locationname, groupassignment.groupid).\
        join(groupassignment).join(group).join(period).outerjoin(location).\
        filter(group.periodid == periodid).order_by(group.groupname,groupassignment.instrumentname).all()
    #grab just the userids of those players to be used in the next query
    players_in_groups_query = session.query(user.userid).\
        join(groupassignment).join(group).join(period).\
        filter(group.periodid == periodid)
    #find all other players to be displayed to the user
    nonplayers = (session.query(user.userid, user.firstname, user.lastname).filter(~user.userid.in_(players_in_groups_query)).all())
    thisperiod = session.query(period).filter(period.periodid == periodid).first()
    session.close()
    return render_template('period.html', \
                            players=players, \
                            publicevents=publicevents, \
                            nonplayers=nonplayers, \
                            campname=getconfig('Name'), \
                            thisuser=thisuser, \
                            period=thisperiod, \
                            instrumentlist=getconfig('Instruments').split(","), \
                            )

#Handles the conductor instrumentation page.
@app.route('/user/<userid>/instrumentation/<periodid>/', methods=['GET', 'POST'])
def instrumentation(userid,periodid):
    session = Session()
    #gets the data associated with this user
    thisuser = session.query(user).filter(user.userid == userid).first()
    if thisuser is None:
        return ('Did not find user in database. You have entered an incorrect URL address.')
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
            conductors = session.query(user).join(instrument, user.userid == instrument.userid).filter(instrument.instrumentname == 'Conductor').all()
            #get the list of instruments from the config file
            instrumentlist = getconfig('Instruments').split(",")
            #find all large group templates and serialize them to prepare to inject into the javascript
            grouptemplates = session.query(grouptemplate).filter(grouptemplate.size == 'L').all()
            grouptemplates_serialized = [i.serialize for i in grouptemplates]
            log(grouptemplates_serialized)
            session.close()
            return render_template('instrumentation.html', \
                                thisuser=thisuser, \
                                grouptemplates = grouptemplates, \
                                conductors=conductors, \
                                grouptemplates_serialized=grouptemplates_serialized, \
                                campname=getconfig('Name'), \
                                instrumentlist = getconfig('Instruments').split(","), \
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
                setattr(grouprequest, key, value)
            #create the group and the groupassinments configured above in the database
            session.add(grouprequest)
            #if the user plays the "conductor" instrument (i.e. they are actually a conductor) assign them to this group
            if content['conductoruserid'] is not None and content['conductoruserid'] != 'null' and content['conductoruserid'] != '':
                userconductor = session.query(user).join(instrument, user.userid == instrument.userid).filter(user.userid == content['conductoruserid'], instrument.instrumentname == "Conductor").first()
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

#Shows the godpage to the user. Godpage contains all user names and links to all their homes. Right now uses a shared password,
#but would be better if tied to a user's admin account. However, there's no easy way to currently see what the userid of the admin is
#after it's been created. Hmm... a conundrum.
@app.route('/godpage/<password>/')
def godpage(password):
    if password != getconfig('SecretKey'):
        return 'Wrong password'
    else:
        session = Session()
        users = session.query(user).all()
        session.close()
        return render_template('godpage.html', \
                                #user=thisuser, \
                                users=users, \
                                campname=getconfig('Name'), \
                                )

@app.route('/godpage/<password>/importusers/')
def BETAdbbuild(password):
    if password != getconfig('SecretKey'):
        return 'Wrong password'
    else:
        DBSetup.dbbuild()
        session = Session()
        #the below reads the camp input file and creates the users and instrument bindings it finds there.
        ifile  = open('uploads/campers.csv', "rb")
        reader = csv.reader(ifile)
        rownum = 0
        for row in reader:
            log('If youre seeing this, its looped again')
            # Save header row.
            if rownum == 0:
                header = row
                log('Now in the header row')
            else:
                log(row)
                thisuser = user()
                thisuser.userid = str(uuid.uuid4())
                thisuser.grouprequestcount = 0
                thisuser.firstname = row[0]
                thisuser.lastname = row[1][:1] #[:1] means just get the first letter
                if row[12] is not '':
                    thisuser.isannouncer = row[12]
                if row[13] is not '':
                    thisuser.isconductor = row[13]
                if row[14] is not '':
                    thisuser.isadmin = row[14]
                if row[2] is not '':
                    thisuser.arrival = row[2]
                if row[2] is '':
                    thisuser.arrival = CampStartTime
                if row[3] is not '':
                    thisuser.departure = row[3]
                if row[3] is '':
                    thisuser.departure = CampEndTime
                session.add(thisuser)
                if row[4] is not 'Non-Player':
                    instrument1 = instrument(userid = thisuser.userid, instrumentname = row[4].capitalize().replace(" ", ""), grade = row[5], isprimary = 1)
                    session.add(instrument1)
                if row[6] is not '':
                    instrument2 = instrument(userid = thisuser.userid, instrumentname = row[6].capitalize().replace(" ", ""), grade = row[7], isprimary = 0)
                    session.add(instrument2)
                if row[8] is not '':
                    instrument3 = instrument(userid = thisuser.userid, instrumentname = row[8].capitalize().replace(" ", ""), grade = row[9], isprimary = 0)
                    session.add(instrument3)
                if row[10] is not '':
                    instrument4 = instrument(userid = thisuser.userid, instrumentname = row[10].capitalize().replace(" ", ""), grade = row[11], isprimary = 0)
                    session.add(instrument4)
                log('Created user named %s %s' % (thisuser.firstname, thisuser.lastname))
            rownum += 1
        ifile.close()
        session.commit()
        userscount = session.query(user).count()
        session.close()
        return ('Created users. There are now %s total users in the database.' % userscount)

#the below creates a new user. The idea for this is that you could concatenate a string up in Excel with your user's details and click 
#on all the links to create them.
@app.route('/new/user/<firstname>/<lastname>/<age>/<arrival>/<departure>/<isannouncer>/<isconductor>/<isadmin>/')
def new_user(firstname,lastname,age,arrival,departure,isannouncer,isconductor,isadmin):
    session = Session()
    arrival = datetime.datetime.strptime(arrival, '%Y-%m-%d %H:%M')
    departure = datetime.datetime.strptime(departure, '%Y-%m-%d %H:%M')
    log('user is staying at camp starting %s and ending %s' % (arrival,departure))
    userid = str(uuid.uuid4())
    newuser = user(userid=userid, firstname=firstname, lastname=lastname, age=age, arrival=arrival, departure=departure, isannouncer=isannouncer, isconductor=isconductor, isadmin=isadmin)
    session.add(newuser)
    absentgroups = session.query(group.groupid).join(period).filter(or_(period.starttime < arrival, period.starttime > departure)).all()
    for g in absentgroups:
        log('assigning user to absent group with id %s' % g.groupid)
        ga = groupassignment(userid = userid, groupid = g.groupid, instrumentname = 'absent')
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
        log('User submitted grade of %s' % grade)
        session.close()
        return ('incorrect grade. Grade should be between 1 and 5.')
    elif not (int(isprimary) == 0 or int(isprimary) == 1):
        log('User submitted isprimary of %s' % isprimary)
        session.close()
        return ('incorrect isprimary value. isprimary should be a 0 or a 1.')
    elif int(isprimary) == 1 and checkprimary is not None:
        session.close()
        return ('This user already has a primary instrument. Cannot create another primary instrument record.')
    else:
        thisinstrumentname = instrument(userid = thisuser.userid, instrumentname = instrumentname, grade = grade, isprimary = isprimary)
        session.add(thisinstrument)
        session.commit()
        return ('intsrument link created for user with id %s' % thisuser.userid)
        session.close()
    return ('something went wrong. you should never get this message. Inside new_instrument method with no caught errors.')

@app.route('/js/<path:path>')
def send_js(path):
    return send_from_directory('js', path)

@app.route('/css/<path:path>')
def send_css(path):
    return send_from_directory('css', path)

@app.route('/png/<path:path>')
def send_png(path):
    return send_from_directory('png', path)