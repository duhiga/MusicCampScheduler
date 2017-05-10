from flask import Blueprint, render_template, request
from app import Session
from app.models import *
import sqlalchemy
from sqlalchemy import *

lists = Blueprint('lists', __name__, template_folder='templates')

#The group page displays all the people in a given group, along with possible substitutes
@lists.route('/user/<logonid>/group/<groupid>/')
def grouppage(logonid,groupid):

    try:
        session = Session()
        thisuser = getuser(session,logonid,True)
        log('GROUPPAGE: user firstname:%s lastname:%s method:%s' % (thisuser.firstname, thisuser.lastname, request.method))
    except Exception as ex:
        session.close()
        return str(ex)

    try:
        thisgroup = getgroup(session,groupid)
        thislocation = getlocation(session,thisgroup.locationid)
        thisperiod = getperiod(session,thisgroup.periodid)
        if thisgroup.musicid is not None:
            thismusic = getmusic(session, thisgroup.musicid)
        else:
            thismusic = None

        #gets the list of players playing in the given group
        players = session.query(user.userid, 
									user.firstname, 
									user.lastname, 
									instrument.instrumentname
								).join(groupassignment
								).join(group
								).join(instrument, groupassignment.instrumentid == instrument.instrumentid
								).filter(group.groupid == groupid
								).order_by(instrument.order
								).all()
        
        #find the substitutes for this group
        if thisgroup.status == 'Confirmed' and thisgroup.iseveryone != 1 and thisgroup.groupname != 'absent':
            minimumlevel = thisgroup.getminlevel(session)
            maximumlevel = thisgroup.getmaxlevel(session)
            #get the list of instruments played in this group and removes duplicates to be used as a subquery later
            instruments_in_group_query = session.query(groupassignment.instrumentid
								).join(group
								).filter(group.groupid == thisgroup.groupid
								).group_by(groupassignment.instrumentid)
            log('GROUPPAGE: Found instruments in group to be %s' % instruments_in_group_query.all())
            #get the userids of everyone that's already playing in something this period
            everyone_playing_in_periodquery = session.query(user.userid
								).join(groupassignment
								).join(group
								).join(period
								).filter(period.periodid == thisgroup.periodid)
            #combine the last two queries with another query, finding everyone that both plays an instrument that's found in this
            #group AND isn't in the list of users that are already playing in this period.
            substitutes = session.query(
                                    instrument.instrumentname, 
                                    user.userid, 
                                    user.firstname, 
                                    user.lastname
								).outerjoin(userinstrument
                                ).join(user
                                ).filter(
                                    ~user.userid.in_(everyone_playing_in_periodquery), 
                                    user.isactive == 1, 
                                    user.arrival <= thisperiod.starttime, 
                                    user.departure >= thisperiod.endtime,
                                    userinstrument.instrumentid.in_(instruments_in_group_query), 
                                    userinstrument.level >= minimumlevel, 
                                    userinstrument.level <= maximumlevel, 
                                    userinstrument.isactive == 1
                                ).order_by(instrument.instrumentname)
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
                                        errormessage = 'Failed to display page. %s' % ex
                                        )
        else:
            return jsonify(message = message, url = 'none')

#this page is the full report for any given period
@lists.route('/user/<logonid>/period/<periodid>/')
def periodpage(logonid,periodid):

    try:
        session = Session()
        thisuser = getuser(session,logonid,True)
        log('PERIODPAGE: user firstname:%s lastname:%s method:%s' % (thisuser.firstname, thisuser.lastname, request.method))
    except Exception as ex:
        session.close()
        return str(ex)

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
							instrument.instrumentname, 
							location.locationname, 
							groupassignment.groupid
						).join(groupassignment
						).join(group
						).join(period
						).join(instrument, groupassignment.instrumentid == instrument.instrumentid
						).outerjoin(location
						).filter(
							user.arrival <= thisperiod.starttime, 
							user.departure >= thisperiod.endtime, 
							group.periodid == thisperiod.periodid, 
							group.status == 'Confirmed', 
							group.groupname != 'absent'
						).order_by(
							group.groupid,
							instrument.order
						).all()

        #grab just the userids of those players to be used in the next query
        players_in_groups_query = session.query(user.userid
						).join(groupassignment
						).join(group
						).join(period
						).filter(user.isactive == 1, 
							user.arrival <= thisperiod.starttime, 
							user.departure >= thisperiod.endtime, 
							group.periodid == thisperiod.periodid, 
							group.status == 'Confirmed')

        #find all other players to be displayed to the user
        unallocatedplayers = session.query(user.userid, 
							user.firstname, 
							user.lastname, 
							instrument.instrumentname
						).join(userinstrument
						).join(instrument
						).filter(~user.userid.in_(players_in_groups_query), 
							user.isactive == 1, 
							user.arrival <= thisperiod.starttime, 
							user.departure >= thisperiod.endtime, 
							userinstrument.isprimary == 1
						).all()

		#get just the userids of the previous query to be used in the next query
        unallocatedplayers_query = session.query(user.userid
						).join(userinstrument
						).join(instrument
						).filter(~user.userid.in_(players_in_groups_query), 
							user.isactive == 1, 
							user.arrival <= thisperiod.starttime, 
							user.departure >= thisperiod.endtime, 
							userinstrument.isprimary == 1)
		
		#get the rest of the users that the previous queries haven't found
        nonplayers = session.query(user.userid, 
							user.firstname, 
							user.lastname, 
							sqlalchemy.sql.expression.literal_column("'Non Player'").label("instrumentname")
						).filter(~user.userid.in_(players_in_groups_query), 
							~user.userid.in_(unallocatedplayers_query), 
							user.isactive == 1, 
							user.arrival <= 
							thisperiod.starttime, 
							user.departure >= thisperiod.endtime
						).all()

        thisperiod = getperiod(session,periodid)
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
            return errorpage(thisuser,'Failed to display page. %s' % ex)
        else:
            return jsonify(message = message, url = 'none')