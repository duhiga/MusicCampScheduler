from flask import Blueprint, render_template, request, flash
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
        
        #if this camper is inactive, has not arrived at camp yet, or is departing before the end of tomorrow
        if (thisuser.isactive != 1) and periodid is None:
            session.close()
            return errorpage(thisuser,'Your account is currently set to inactive. Inactive users cannot request groups. Is this is a mistake, navigate to your settings and set yourself to active.')
        if (thisuser.departure < today(2)) and periodid is None:
            session.close()
            return errorpage(thisuser,"You are set to depart camp in less than one days' time, so you cannot request a group. If this is incorrect, you can change your departure time in your settings.")

        #check if this user is really a conductor and actually requested a conductorpage for a specific period
        if thisuser.isconductor == 1 and periodid is not None:
            conductorpage = True
            thisperiod = session.query(period).filter(period.periodid == periodid).first()
            if thisperiod is None:
                return ('Did not find period in database. Something has gone wrong.')
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
            log('GROUPREQUEST: User is allowed total %s requests.' % (((now() - thisuser.arrival).days + 2) * float(getconfig('DailyGroupRequestLimit')) + float(getconfig('BonusGroupRequests'))))
            if thisuser.grouprequestcount >= (((now() - thisuser.arrival).days + 2) * float(getconfig('DailyGroupRequestLimit')) + float(getconfig('BonusGroupRequests'))):
                log('GROUPREQUEST: This user is denied access to request another group.')
                session.close()
                return errorpage(thisuser,"You have requested %s groups throughout the camp, and you're allowed %s per day (as well as %s welcome bonus requests!). You've reached your limit for today. Come back tomorrow!" % \
                    (thisuser.grouprequestcount, getconfig('DailyGroupRequestLimit'), getconfig('BonusGroupRequests')))
        
        #The below runs when a user visits the grouprequest page
        if request.method == 'GET':
        
            #checks if the requested music exists and sets it up for the page
            if musicid is not None:
                requestedmusic = session.query(music).filter(music.musicid == musicid).first()
                if requestedmusic is None:
                    return errorpage(thisuser,"You have requested music that could not be found in the database. Talk to the administrator.")
            else:
                requestedmusic = None
            if conductorpage:
                musics = thisperiod.getfreemusics(session)
                grouptemplates = getgrouptemplates(session, 'S')
                render = render_template('grouprequest.html',
                                thisuser=thisuser,
                                playerlimit = int(getconfig('GroupRequestPlayerLimit')),
                                grouptemplates = grouptemplates,
                                grouptemplates_serialized=[i.serialize for i in grouptemplates],
                                campname=getconfig('Name'), favicon=getconfig('Favicon_URL'), instruments=getinstruments(session), supportemailaddress=getconfig('SupportEmailAddress'),
                                instruments_serialized=[i.serialize for i in getinstruments(session)],
                                players=json.dumps([ob.__dict__ for ob in thisperiod.getfreeplayers(session)]),
                                conductorpage=True,
                                thisperiod=thisperiod,
                                locations=thisperiod.getfreelocations(session),
                                musics=musics,
                                musics_serialized=[i.serialize for i in musics],
                                requestedmusic=requestedmusic,
                                )
            else:
                musics = getmusic(session)
                grouptemplates = getgrouptemplates(session, 'S', thisuser)
                thisuserinstruments = session.query(userinstrument.instrumentid, instrument.instrumentname
                                            ).join(instrument
                                            ).filter(userinstrument.userid == thisuser.userid
                                            ).all()
                render = render_template('grouprequest.html',
                                thisuser=thisuser,
                                thisuserinstruments=thisuserinstruments,
                                thisuserinstruments_serialized=[i.serialize for i in thisuser.getinstruments(session)],
                                playerlimit = int(getconfig('GroupRequestPlayerLimit')),
                                grouptemplates = grouptemplates,
                                grouptemplates_serialized=[i.serialize for i in grouptemplates],
                                campname=getconfig('Name'), favicon=getconfig('Favicon_URL'), instruments=getinstruments(session), supportemailaddress=getconfig('SupportEmailAddress'),
                                instruments_serialized=[i.serialize for i in getinstruments(session)],
                                players=json.dumps([ob.__dict__ for ob in getplayers(session)]),
                                conductorpage=False,
                                thisperiod=thisperiod,
                                locations=None,
                                musics=musics,
                                musics_serialized=[i.serialize for i in musics],
                                requestedmusic=requestedmusic,
                                )
            
            session.close()
            return render

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
            grouprequest = group(ismusical = 1, requesteduserid = thisuser.userid, requesttime = now(), minimumlevel = 0, maximumlevel = 0)
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

@requests.route('/user/<logonid>/musiclibrary/')
def musiclibrary(logonid):

    try:
        session = Session()
        thisuser = getuser(session,logonid,True)
        log('MUSICLIBRARY: user firstname:%s lastname:%s method:%s' % (thisuser.firstname, thisuser.lastname, request.method))
    except Exception as ex:
        session.close()
        return str(ex)

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
            return errorpage(thisuser,'Failed to display page. %s.' % ex)
        else:
            return jsonify(message = message, url = 'none')

@requests.route('/user/<logonid>/musiclibrary/details/<musicid>/')
def musicdetails(logonid,musicid):

    try:
        session = Session()
        thisuser = getuser(session,logonid,True)
        log('MUSICDETAILS: user firstname:%s lastname:%s method:%s' % (thisuser.firstname, thisuser.lastname, request.method))
    except Exception as ex:
        session.close()
        return str(ex)

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
            return errorpage(thisuser,'Failed to display page. %s' % ex)
        else:
            return jsonify(message = message, url = 'none')

@requests.route('/user/<logonid>/musiclibrary/new/', methods=['GET', 'POST'])
def newmusic(logonid):

    try:
        session = Session()
        thisuser = getuser(session,logonid,True)
        log('NEWMUSIC: user firstname:%s lastname:%s method:%s' % (thisuser.firstname, thisuser.lastname, request.method))
    except Exception as ex:
        session.close()
        return str(ex)

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
            return errorpage(thisuser,'Failed to display page. %s' % ex)
        else:
            return jsonify(message = message, url = 'none')

#Handles the conductor instrumentation page.
@requests.route('/user/<logonid>/instrumentation/<periodid>/', methods=['GET', 'POST'])
def instrumentation(logonid,periodid):

    try:
        session = Session()
        thisuser = getuser(session,logonid,True)
        log('INSTRUMENTATION: user firstname:%s lastname:%s method:%s' % (thisuser.firstname, thisuser.lastname, request.method))
    except Exception as ex:
        session.close()
        return str(ex)

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

                locations = thisperiod.getfreelocations(session)
                musics = thisperiod.getfreemusics(session)
                musics_serialized = [i.serialize for i in musics]
                #get a list of conductors to fill the dropdown on the page
                conductors = thisperiod.getfreeconductors(session)
                #get the list of instruments from the config file
                instrumentlist = getinstruments(session)
                #find all large group templates and serialize them to prepare to inject into the javascript
                grouptemplates = session.query(grouptemplate).filter(grouptemplate.size == 'L').all()
                grouptemplates_serialized = [i.serialize for i in grouptemplates]
                session.close()
                return render_template('instrumentation.html', \
                                    thisuser=thisuser, \
                                    grouptemplates = grouptemplates, \
                                    conductors=conductors, \
                                    grouptemplates_serialized=grouptemplates_serialized, \
                                    campname=getconfig('Name'), favicon=getconfig('Favicon_URL'), instrumentlist=instrumentlist, supportemailaddress=getconfig('SupportEmailAddress'), \
                                    thisperiod=thisperiod, \
                                    locations=locations, \
                                    maximumlevel=int(getconfig('MaximumLevel')), \
                                    musics=musics, \
                                    musics_serialized=musics_serialized, \
                                    )

            #The below runs when a user presses "Submit" on the instrumentation page. It creates a group object with the configuraiton selected by 
            #the user, and creates groupassignments if needed
            if request.method == 'POST':
                #format the packet received from the server as JSON
                content = request.json
                session = Session()
                log('Grouprequest received. Whole content of JSON returned is: %s' % content)
                #establish the 'grouprequest' group object. This will be built up from the JSON packet, and then added to the database
                grouprequest = group(ismusical = 1, 
                                    requesteduserid = thisuser.userid, 
                                    periodid = thisperiod.periodid, 
                                    status = "Queued", 
                                    requesttime = now())
                #check if a group already exists for this period with the same name
                namecheck = session.query(group).filter(group.groupname == content['groupname'], group.periodid == thisperiod.periodid).first()
                if namecheck is not None:
                    raise Exception('Could not create instrumentation, there is already a group named %s in this period.' % namecheck.groupname)
                #for each player object in the players array in the JSON packet
                for key, value in content.items():
                    if (key == 'groupname' or key == 'maximumlevel' or key == 'mininumlevel') and value == '':
                        raise Exception('Could not create instrumentation, you must enter a groupname, music, maximumlevel and mininumlevel')
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
                            grouprequest.addplayer(session,getuser(session,content['conductoruserid']),'Conductor')
                        else:
                            raise Exception('Could not create instrumentation, %s is already assigned to a group during this period.' % userconductor.firstname)
                    else:
                        raise Exception('The user requested as the conductor is not set up to be a conductor in the database.')
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
            return errorpage(thisuser,'Failed to display page. %s' % ex)
        else:
            return jsonify(message = message, url = 'none')