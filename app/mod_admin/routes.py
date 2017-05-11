from flask import Blueprint, render_template, request
from app import Session
from app.models import *
from sqlalchemy import *

admin = Blueprint('admin', __name__, template_folder='templates')

#Group editor page. Only accessable by admins. Navigate here from a group to edit group.
@admin.route('/user/<logonid>/group/<groupid>/edit/', methods=['GET', 'POST', 'DELETE'])
def editgroup(logonid,groupid,periodid=None):

    try:
        session = Session()
        thisuser = getuser(session,logonid,True)
        log('GROUPEDIT: user firstname:%s lastname:%s method:%s' % (thisuser.firstname, thisuser.lastname, request.method))
    except Exception as ex:
        session.close()
        return str(ex)

    try:
        if thisuser.isadmin != 1:
            session.close()
            raise Exception('You do not have permission to do this')
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
                for p in thisgroupplayers:
                    if p.departure <= tomorrow:
                        a = session.query(groupassignment).filter(groupassignment.userid == p.userid, groupassignment.groupid == thisgroup.groupid).first()
                        log('GROUPEDIT: Found user %s %s with departure before tomorrow, removing them from this group.' % (p.firstname, p.lastname))
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
            log('GROUPEDIT: Last Arrival time of players in this group: %s' % lastarrival)
            log('GROUPEDIT: First Departure time of players in this group: %s' % firstdeparture)
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
                log('GROUPEDIT: This is a periodless group. Selecting a period for the group.')
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
                playersdump = session.query(user.userid,user.firstname,user.lastname,instrument.instrumentname,instrument.level,instrument.isprimary).\
                            join(instrument).filter(~user.userid.in_(playersPlayingInPeriod), user.isactive == 1, user.arrival <= selectedperiod.starttime, user.departure >= selectedperiod.endtime, instrument.isactive == 1).all()
            else:
                playersdump = session.query(user.userid,user.firstname,user.lastname,instrument.instrumentname,instrument.level,instrument.isprimary).\
                            join(instrument).filter(user.isactive == 1, instrument.isactive == 1).all()
            playersdump_serialized = []
            for p in playersdump:
                playersdump_serialized.append({'userid': p.userid, 'firstname': p.firstname, 'lastname': p.lastname,
                    'instrumentname': p.instrumentname, 'level': p.level, 'isprimary': p.isprimary})

            #Get a list of the available music not being used in the period selected
            if selectedperiod is not None:
                musics_used_query = session.query(music.musicid).join(group).join(period).filter(period.periodid == selectedperiod.periodid, group.groupid != thisgroup.groupid)
                musics = session.query(music).filter(~music.musicid.in_(musics_used_query)).all()
            else:
                musics = session.query(music).all()
            musics_serialized = [i.serialize for i in musics]

            #get a list of the locations not being used in this period
            if selectedperiod is not None:
                locations_used_query = session.query(location.locationid).join(group).join(period).filter(period.periodid == selectedperiod.periodid, group.groupid != thisgroup.groupid, location.locationname != 'None')
                locations = session.query(location).filter(~location.locationid.in_(locations_used_query)).all()
            else:
                locations = session.query(location).all()
            log('GROUPEDIT: This groups status is %s' % thisgroup.status)

            #find all group templates to show in a dropdown
            grouptemplates = session.query(grouptemplate).all()
            grouptemplates_serialized = [i.serialize for i in grouptemplates]

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
                                thismusic=getmusic(session,thisgroup.musicid), \
                                instrumentlist_string=getconfig('Instruments'), \
                                groupmin=thisgroup.getminlevel(session), \
                                groupmax=thisgroup.getmaxlevel(session), \
                                requestor=requestor, \
                                )
            session.close()
            return template

        if request.method == 'DELETE':
            if groupid is not None:
                thisgroup.delete(session)
                url = ('/user/' + str(thisuser.logonid) + '/')
                message = 'none'
                flash(u'Group Deleted','message')
                log('Sending user to URL: %s' % url)
                session.close()
                return jsonify(message = message, url = url)
            else:
                raise Exception('You must have a period selected before autofilling.')
            
        if request.method == 'POST':
            #format the packet received from the server as JSON
            content = request.json
            if content['groupname'] == '' or content['groupname'] == 'null' or content['groupname'] is None:
                raise Exception('You must give this group a name before saving or autofilling.')
            if content['periodid'] != '' and content['periodid'] != 'null' and content['periodid'] is not None:
                thisperiod = session.query(period).filter(period.periodid == content['periodid']).first()
            else:
                raise Exception('Could not find a period with the selected id. Refresh the page and try again.')
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

            if content['locationid'] is not None and content['locationid'] != '':
                location_clash = session.query(location.locationname, group.groupid).join(group).join(period).filter(period.periodid == thisperiod.periodid, location.locationid == content['locationid'], group.groupid != thisgroup.groupid).first()
                if location_clash is not None:
                    log('Group %s is already using this location %s' % (location_clash.groupid, location_clash.locationname))
                    raise Exception('This location is already being used at this time. Select another.')

            if content['musicid'] != '' and content['musicid'] != 'null' and content['musicid'] is not None:
                music_clash = session.query(music.musicname, music.composer, group.groupid).join(group).join(period).filter(period.periodid == thisperiod.periodid, music.musicid == content['musicid'], group.groupid != thisgroup.groupid).first()
                if music_clash is not None:
                    log('Group %s is already using this music %s %s' % (music_clash.groupid, music_clash.composer, music_clash.musicname))
                    raise Exception('This music is already being used at this time. You cannot schedule in this period.')

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
                            raise Exception('Found a clash for %s. They are already playing %s in %s. Refresh the page and try again.' % (playeruser.firstname, currentassignment.instrumentname, currentassignment.groupname))
                    #if we found a player and no clash, we can assign this player to the group
                    if playeruser is None:
                        url = ('/user/' + str(thisuser.logonid) + '/')
                        raise Exception(message = 'Could not find one of your selected players in the database. Please refresh the page and try again.')
                    else:
                        #if the player is inactive or not attending camp at this time, they should never have been shown to the admin and chosen - this could happen if they were set to inactive while the admin had the page open
                        if playeruser.isactive != 1 or playeruser.arrival > thisperiod.starttime or playeruser.departure < thisperiod.endtime:
                            raise Exception('The user %s %s is set to inactive and they cannot be assigned. Refresh the page and try again with a different user.' % (playeruser.firstname, playeruser.lastname))
                        else:
                            playergroupassignment = groupassignment(userid = playeruser.userid, groupid = thisgroup.groupid, instrumentname = p['instrumentname'])
                            session.add(playergroupassignment)

            if thisgroup.status == 'Confirmed' and (
                    thisgroup.periodid == '' or thisgroup.periodid is None or
                    thisgroup.groupname == '' or thisgroup.groupname is None or
                    thisgroup.locationid == '' or thisgroup.locationid is None
                    ):
                raise Exception(message = 'Confirmed groups must have a name, assigned period, assigned location and no empty player slots.')

            if content['submittype'] == 'autofill':
                log('GROUPEDIT: User selected to autofill the group')
                log('GROUPEDIT: Primary_only switch set to %s' % content['primary_only'])
                if content['periodid'] == '' or content['periodid'] is None:
                    raise Exception('You must select a period before autofilling')
                else:
                    if thisperiod is not None:
                        #get the optimal list of players to be filled into this group
                        final_list = autofill(session,thisgroup,thisperiod,int(content['primary_only']))
                        #create group assignments for each player in the final_list
                        thisgroup.addplayers(session,final_list)

            #Check for empty instrument slots if group is set to confirmed - if there are empties we have to switch it back to queued
            if thisgroup.status == 'Confirmed':
                for i in getconfig('Instruments').split(","):
                    log('This group has a required %s number of %s and an assigned %s.' % (i, getattr(thisgroup,i), session.query(user).join(groupassignment).filter(groupassignment.groupid == thisgroup.groupid, groupassignment.instrumentname == i).count()))
                    if thisgroup.locationid is None or thisgroup.locationid == '' or thisgroup.totalinstrumentation != thisgroup.totalallocatedplayers:
                        thisgroup.status = 'Queued'
                        session.merge(thisgroup)
                        session.commit()
                        url = '/user/' + str(thisuser.logonid) + '/group/' + str(thisgroup.groupid) + '/edit/'
                        session.close()
                        flash(u'Changes Partially Saved','message')
                        return jsonify(message = 'Your group is not confirmed because there are empty instrument slots or your location is blank. Your other changes have been saved.', url = url)
            session.merge(thisgroup)
            session.commit()
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
            return errorpage(thisuser,'Failed to display page. %s' % ex)
        else:
            return jsonify(message = message, url = 'none')
        
@admin.route('/user/<logonid>/group/<groupid>/period/<periodid>/edit/', methods=['GET', 'POST', 'DELETE'])
def editgroupperiod(logonid,groupid,periodid):
    return editgroup(logonid,groupid,periodid)

#This page is used by an "announcer" to edit the announcement that users see when they open their homes
@admin.route('/user/<logonid>/announcement/', methods=['GET', 'POST'])
def announcementpage(logonid):
    
    try:
        session = Session()
        thisuser = getuser(session,logonid,True)
        log('ANNOUNCEMENT: user firstname:%s lastname:%s method:%s' % (thisuser.firstname, thisuser.lastname, request.method))
    except Exception as ex:
        session.close()
        return str(ex)

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
            return errorpage(thisuser,'Failed to display page. %s' % ex)
        else:
            return jsonify(message = message, url = 'none')

#This page shows the queued groups, it is only accessible by the admin
@admin.route('/user/<logonid>/groupscheduler/', methods=['GET', 'POST'])
def groupscheduler(logonid):

    try:
        session = Session()
        thisuser = getuser(session,logonid,True)
        log('GROUPSCHEDULER: user firstname:%s lastname:%s method:%s' % (thisuser.firstname, thisuser.lastname, request.method))
    except Exception as ex:
        session.close()
        return str(ex)

    try:
        if request.method == 'GET':
            if thisuser.isadmin != 1:
                session.close()
                return 'You do not have permission to view this page'
            else:
                groups = session.query(*[c for c in group.__table__.c]
                                ).add_columns(
                                    period.periodid,
                                    period.periodname, 
                                    period.starttime, 
                                    period.endtime, 
                                    user.firstname, 
                                    user.lastname,
                                    music.composer,
                                    music.musicname
                                ).outerjoin(period
                                ).outerjoin(user
                                ).outerjoin(music
                                ).filter(
                                    group.groupname != 'absent',
                                    group.iseveryone != 1
                                ).order_by(
                                    group.status.desc(),
                                    group.periodid.nullslast(),
                                    group.requesttime
                                ).all()
                log("GROUPSCHEDULER: Found %s queued groups to show the user" % len(groups))
                #find all periods after now so the admin can choose which they want to fill with groups
                periods = session.query(period).filter(period.starttime > datetime.datetime.now()).all()
                session.close()
                return render_template('groupscheduler.html', \
                                        groups=groups, \
                                        periods=periods, \
                                        thisuser=thisuser, \
                                        now=datetime.datetime.now(), \
                                        campname=getconfig('Name'), favicon=getconfig('Favicon_URL'), instrumentlist=getconfig('Instruments').split(","), supportemailaddress=getconfig('SupportEmailAddress'), \
                                        )
        if request.method == 'POST':
            log('GROUPSCHEDULER: POST received with submittype %s' % request.json['submittype'])
            if request.json['submittype'] == 'reset':
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
            elif request.json['submittype'] == 'fillall':
                log('FILLALL: Admin has initiated a fill_all action for period id:%s' % request.json['periodid'])
                #first, check if the period they selected is valid and in the future
                if request.json['periodid'] is None or request.json['periodid'] == '':
                    raise Exception('You must choose a period before requesting the fill-all.')
                else:
                    thisperiod = getperiod(session,request.json['periodid'])
                    log('FILLALL: Filling period name:%s id:%s' % (thisperiod.periodname,thisperiod.periodid))
                if thisperiod is None:
                    raise Exception('Could not find the requested period, or the selected period is in the past. Refresh the page and try again.')

                #iterate through the groups that already have this period assigned. If we fail to allocate on just one of these, we need to break out and inform the admin
                possiblegroups = session.query(group
                            ).outerjoin(period
                            ).filter(
                                or_(
                                    group.periodid == thisperiod.periodid, 
                                    group.periodid == None
                                    ), 
                                group.status == "Queued"
                            ).order_by(
                                group.periodid.nullslast(),
                                group.requesttime
                            ).all()
                log('FILLALL: Found %s groups to be filled' % len(possiblegroups))
                for g in possiblegroups:
                    #first, purge any players that have since left the camp or are marked inactive
                    g.purgeoldplayers(session)
                    #then, if this group is empty, has no allocated period and was requested by a player that is old, delete it
                    requesteduser = getuser(session,g.requesteduserid)
                    if g.periodid is None and \
                            g.totalallocatedplayers == 0 and \
                            (requesteduser.isactive != 1 or requesteduser.departure < datetime.datetime.now()):
                        log('FILLALL: Group name:%s id:%s is an orphan group and will now be deleted' % (g.groupname,g.groupid))
                        g.delete(session)
                    #then, check if any of the players in this group are already playing in this period
                    elif g.checkplayerclash(session,thisperiod):
                        log('FILLALL: Found that group %s cannot be autofilled because players already in this group are already playing in this period. Skipping this group.')
                    else:
                        log('FILLALL: Attempting autofill, location allocation and confirmation for group name:%s id:%s' % (g.groupname,g.groupid))
                        #see if we can assign the group a location for this period
                        if g.locationid is None or g.locationid == '':
                            #get the instruments in this group to check against the location restrictions
                            instruments = g.instruments
                            #get the locations already being used in this period
                            locations_used_query = session.query(location.locationid).join(group).join(period).filter(period.periodid == thisperiod.periodid)
                            #get the location with the minimum capacity that fits this group, is currently free, and does not void any instrument restrictions
                            thislocation = session.query(
                                                    location
                                                ).filter(
                                                    ~location.locationid.in_(locations_used_query),
                                                    location.capacity >= g.totalinstrumentation,
                                                    *[getattr(location,i) > 0 for i in instruments]
                                                ).order_by(
                                                    location.capacity
                                                ).first()
                        else:
                            thislocation = getlocation(session,g.locationid)
                        #if we could not find a suitable location, break out and send the user a message informing them
                        if thislocation is None:
                            log('FILLALL: No suitable location exists for group with name %s and id %s. Can not autofill this group.' % (g.groupname,g.groupid))
                            if g.periodid is not None:
                                message = 'Fill-All failed at group "%s". Could not find a suitable location for this group. Try editing other groups in the period to make room, or reduce the number of players in the group.' % g.groupname
                                url = 'refresh'
                                session.commit()
                                session.close()
                                flash(u'Period Partially Filled', 'message')
                                return jsonify(message = message, url = url )
                        else:
                            #find how many players can be autofilled into this group
                            players = autofill(session,g,thisperiod)
                            #if the autofill didn't completely fill the group and this group already has an assigned period, we need to break out and inform the admin that they need to do this group manually
                            if g.totalinstrumentation != g.totalallocatedplayers + len(players) and g.periodid is not None:
                                message = 'Fill-All failed at group "%s". This is because the group requires %s players, but the autofill algorythm only found %s players. Select this group and fill it manually, then attempt to fill-all again.' % (g.groupname,g.totalinstrumentation,g.totalallocatedplayers+len(players))
                                url = 'refresh'
                                log('FILLALL: Autofill failed to completely fill group name:%s id:%s totalinstrumentation:%s totalallocatedplayers:%s. Found only %s players to autofill. Sending an error to the admin.' % (g.groupname,g.groupid,g.totalinstrumentation,g.totalallocatedplayers,len(players)))
                                session.commit()
                                session.close()
                                flash(u'Period Partially Filled', 'message')
                                return jsonify(message = message, url = url)
                            #if this group doesn't have an assigned period and can't be assigned to the selected period - just skip it.
                            elif g.totalinstrumentation != g.totalallocatedplayers + len(players):
                                log('FILLALL: Found that group %s cannot be autofilled with current players in the pool. Skipping this group.')
                            else:
                                #if we got here, this group is good to go
                                #assign the location as found in a previous query
                                g.locationid = thislocation.locationid
                                #assign the period as selected
                                g.periodid = thisperiod.periodid
                                #allocate the players
                                g.addplayers(session,players)
                                #confirm the group
                                g.status = "Confirmed"
                                session.merge(g)
                                session.commit()
                                log('FILLALL: Group confirmed - Status:%s Name:%s Locationid:%s Periodid:%s TotalPlayers:%s TotalSetInstrumentation:%s' % (g.status,g.groupname,g.locationid,g.periodid,g.totalallocatedplayers,g.totalinstrumentation))
                    
                session.commit()
                session.close()
                log('FILLALL: Fill-all operitaion successful')
                flash(u'Period Sucessfully Filled', 'success')
                return jsonify(message = 'none', url = 'refresh')
                    
    except Exception as ex:
        log('Failed to execute %s for user %s %s with exception: %s.' % (request.method, thisuser.firstname, thisuser.lastname, ex))
        message = ('Failed to execute %s with exception: %s. Try refreshing the page and trying again or contact camp administration.' % (request.method, ex))
        session.rollback()
        session.close()
        if request.method == 'GET':
            return errorpage(thisuser,'Failed to display page. %s' % ex)
        else:
            return jsonify(message = message, url = 'none')

#This page is for creating a public event. It comes up as an option for adminsitrators on their homes
@admin.route('/user/<logonid>/publicevent/<periodid>/', methods=['GET', 'POST'])
def publiceventpage(logonid,periodid):

    try:
        session = Session()
        thisuser = getuser(session,logonid,True)
        log('PUBLICEVENT: user firstname:%s lastname:%s method:%s' % (thisuser.firstname, thisuser.lastname, request.method))
    except Exception as ex:
        session.close()
        return str(ex)

    try:
        if thisuser.isadmin != 1:
            raise Exception(thisuser,'You do not have permission to view this page')
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
                    raise Exception('Submission failed. You must submit both an event name and location.')
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
            return errorpage(thisuser,'Failed to display page. %s' % ex)
        else:
            return jsonify(message = message, url = 'none')

#handles the admin page
@admin.route('/user/<logonid>/useradmin/')
def useradmin(logonid):

    try:
        session = Session()
        thisuser = getuser(session,logonid,True)
        log('USERADMIN: user firstname:%s lastname:%s method:%s' % (thisuser.firstname, thisuser.lastname, request.method))
    except Exception as ex:
        session.close()
        return str(ex)

    #try:
    #check if this user is a conductor, if they are not, deny them.
    if thisuser.isadmin != 1 and thisuser.logonid != getconfig('AdminUUID'):
        raise Exception('You are not allowed to view this page.')
    else:
        #get the list of people that play instruments
        """players_query = session.query(instrument.userid).filter(instrument.isactive == 1)"""
        #get the userids and their associated primary instruments
        """primaryinstruments_subquery = session.query(
                            instrument.userid.label('primaryinstruments_userid'),
                            instrument.instrumentname.label('instrumentname')
                        ).filter(
                            instrument.isactive == 1, 
                            instrument.isprimary == 1
                        ).subquery()"""

        #make a query that totals the nmber of times each potential user has played at camp.
        """playcounts_subquery = session.query(
                            user.userid.label('playcounts_userid'),
                            func.count(user.userid).label("playcount")
                        ).group_by(
                            user.userid
                        ).outerjoin(groupassignment, groupassignment.userid == user.userid
                        ).outerjoin(group, group.groupid == groupassignment.groupid
                        ).filter(
                            groupassignment.instrumentname != 'Conductor', 
                            group.ismusical == 1, 
                            group.periodid != None,
                        ).subquery()"""

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
                            #primaryinstruments_subquery.c.instrumentname,
                            #playcounts_subquery.c.playcount,
                        #).outerjoin(primaryinstruments_subquery, primaryinstruments_subquery.c.primaryinstruments_userid == user.userid
                        #).outerjoin(playcounts_subquery, playcounts_subquery.c.playcounts_userid == user.userid
                        ).order_by(
                            user.firstname,
                            user.lastname
                        ).all()

        return render_template('useradmin.html', \
                            thisuser=thisuser, \
                            users=users, \
                            campname=getconfig('Name'), favicon=getconfig('Favicon_URL'), instrumentlist=getconfig('Instruments').split(","), supportemailaddress=getconfig('SupportEmailAddress'), \
                            )
    """except Exception as ex:
        log('Failed to execute %s for user %s %s with exception: %s.' % (request.method, thisuser.firstname, thisuser.lastname, ex))
        message = ('Failed to execute %s with exception: %s. Try refreshing the page and trying again or contact camp administration.' % (request.method, ex))
        session.rollback()
        session.close()
        if request.method == 'GET':
            return errorpage(thisuser,'Failed to display page. %s' % ex)
        else:
            return jsonify(message = message, url = 'none')"""

#handles the useredit page
@admin.route('/user/<logonid>/edituser/<targetuserid>/', methods=['GET', 'POST'])
def edituser(logonid, targetuserid):

    try:
        session = Session()
        thisuser = getuser(session,logonid,True)
        log('EDITUSER: user firstname:%s lastname:%s method:%s' % (thisuser.firstname, thisuser.lastname, request.method))
    except Exception as ex:
        session.close()
        return str(ex)

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
            return errorpage(thisuser,'Failed to display page. %s' % ex)
        else:
            return jsonify(message = message, url = 'none')

@admin.route('/user/<logonid>/newuser/', methods=['GET', 'POST'])
def newuser(logonid):
    return edituser(logonid,None)

@admin.route('/user/<logonid>/settings/', methods=['GET', 'POST'])
def settings(logonid):
    return edituser(logonid,'self')

#sends bulk emails to an array of users sent with the request
@admin.route('/user/<logonid>/email/', methods=['POST'])
def sendlinkemail(logonid):

    try:
        session = Session()
        thisuser = getuser(session,logonid,True)
        log('SENDLINKEMAIL: user firstname:%s lastname:%s method:%s' % (thisuser.firstname, thisuser.lastname, request.method))
    except Exception as ex:
        session.close()
        return str(ex)

    try:
        if thisuser.isadmin != 1:
            session.close()
            return errorpage(thisuser,'You do not have permission to view this page')
        content = request.json
        log('SENDLINKEMAIL: Content received: %s' % content)
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
            return errorpage(thisuser,'Failed to display page. %s' % ex)
        else:
            return jsonify(message = message, url = 'none')