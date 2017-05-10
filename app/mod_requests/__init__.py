from flask import Blueprint, render_template, request
from app import Session
from app.models import *
import sqlalchemy
from sqlalchemy import *
import datetime

requests = Blueprint('requests', __name__, template_folder='templates')

#Handles the group request page. If a user visits the page, it gives them a form to create a new group request. Pressing submit 
#sends a post containing configuration data. Their group request is queued until an adminsitrator approves it and assigns it to 
#a period.
@requests.route('/user/<logonid>/grouprequest/', methods=['GET', 'POST'])
def grouprequest(logonid,periodid=None,musicid=None):
    
    try:
        session = Session()
        thisuser = getuser(session,logonid,True)
        log('GROUPREQUEST: user firstname:%s lastname:%s method:%s' % (thisuser.firstname, thisuser.lastname, request.method))
    except Exception as ex:
        session.close()
        return str(ex)
    try:
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
        thisuserinstruments = session.query(instrument
											).outerjoin(userinstrument
											).filter(userinstrument.userid == thisuser.userid, 
												userinstrument.isactive == 1
											).all()
        thisuserinstruments_serialized = [i.serialize for i in thisuserinstruments]

        #check if this user is really a conductor and actually requested a conductorpage for a specific period
        if thisuser.isconductor == 1 and periodid is not None:
            conductorpage = True
            thisperiod = session.query(period).filter(period.periodid == periodid).first()
            if thisperiod is None:
                return ('Did not find period in database. Something has gone wrong.')
        elif thisuserinstruments is None:
            session.close()
            return errorpage(thisuser,'Failed to display page. %s' % ex)
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
                playersdump = session.query(user.userid,user.firstname,user.lastname,instrument.instrumentname,instrument.level,instrument.isprimary).\
                    join(instrument).filter(~user.userid.in_(playersPlayingInPeriod), user.isactive == 1, user.arrival <= thisperiod.starttime, user.departure >= thisperiod.endtime).all()
            else:
                #find all the instruments that everyone plays and serialize them to prepare to inject into the javascript
                playersdump = session.query(user.userid,user.firstname,user.lastname,instrument.instrumentname,instrument.level,instrument.isprimary).\
                    join(instrument).filter(user.userid != thisuser.userid, user.isactive == 1, instrument.isactive == 1).all()
            playersdump_serialized = []
            for p in playersdump:
                playersdump_serialized.append({'userid': p.userid, 'firstname': p.firstname, 'lastname': p.lastname,
                                                'instrumentname': p.instrumentname, 'level': p.level, 'isprimary': p.isprimary})

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
                            instrumentclash = session.query(groupassignment).filter(groupassignment.instrumentname == p['instrumentname'], groupassignment.groupid == m.groupid).all()
                            #if the list of players already matches the group instrumentation for this instrument, this match fails and break out
                            if instrumentclash is not None and instrumentclash != []:
                                if len(instrumentclash) >= getattr(m, p['instrumentname']):
                                    log('MATCHMAKING: Found group not suitable, does not have an open slot for this player.')
                                    clash = True
                                    break
                            #find out if this group's level is unsuitable for this player on this instrument and make a clash if they are
                            playerinstrument = session.query(instrument).filter(instrument.userid == p['userid'], instrument.instrumentname == p['instrumentname']).first()
                            if groupmin < playerinstrument.level < groupmax:
                                log('MATCHMAKING: Found group not suitable, the current players are of unsuitable level. Current min: %s, Current max: %s, this players level: %s.' % (groupmin,groupmax,playerinstrument.level))
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
                        grouprequest.addplayer(session,playeruser,p['instrumentname'])
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
            return errorpage(thisuser,'Failed to display page. %s' % ex)
        else:
            return jsonify(message = message, url = 'none')
        

@requests.route('/user/<logonid>/grouprequest/conductor/<periodid>/', methods=['GET', 'POST'])
def conductorgrouprequest(logonid,periodid):
    
    try:
        session = Session()
        thisuser = getuser(session,logonid,True)
        log('CONDUCTORGROUPREQUEST: user firstname:%s lastname:%s method:%s' % (thisuser.firstname, thisuser.lastname, request.method))
    except Exception as ex:
        session.close()
        return str(ex)

    try:
        if thisuser.isconductor != 1:
            log('CONDUCTORGROUPREQUEST: user %s %s is not allowed to view this page' % (thisuser.firstname, thisuser.lastname))
            raise Exception('You are not a conductor and cannot visit this page.')
        else:
            session.close()
            return grouprequest(logonid,periodid,None)

    except Exception as ex:
        log('Failed to execute %s for user %s %s with exception: %s.' % (request.method, thisuser.firstname, thisuser.lastname, ex))
        message = ('Failed to execute %s with exception: %s. Try refreshing the page and trying again or contact camp administration.' % (request.method, ex))
        session.rollback()
        session.close()
        if request.method == 'GET':
            return errorpage(thisuser,'Failed to display page. %s' % ex)
        else:
            return jsonify(message = message, url = 'none')

@requests.route('/user/<logonid>/grouprequest/music/<musicid>/', methods=['GET', 'POST'])
def musicgrouprequest(logonid,musicid):
    return grouprequest(logonid,None,musicid)