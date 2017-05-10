import sqlalchemy
import datetime
from datetime import date, timedelta
from sqlalchemy import *
from app.config import *
from app.models import *

#get the information needed to fill in the user's schedule table
def getschedule(session,thisuser,date):
    #find the start of the next day
    nextday = date + datetime.timedelta(days=1)

    schedule = []
    #for each period in the requested day
    for p in session.query(period).filter(period.starttime > date, period.endtime < nextday).order_by(period.starttime).all():
        #try to find a group assignment for the user
        g = session.query(group.groupname, period.starttime, period.endtime, location.locationname, group.groupid, group.ismusical, \
                                group.iseveryone, music.musicid, period.periodid, period.periodname, instrument.instrumentname, \
                                period.meal, group.groupdescription, music.composer, music.musicname, group.musicwritein
                            ).join(period
                            ).join(groupassignment
                            ).join(user
                            ).join(instrument
                            ).outerjoin(location
                            ).outerjoin(music
                            ).filter(user.userid == thisuser.userid, 
                                    group.periodid == p.periodid, 
                                    group.status == 'Confirmed'
                            ).first()
        if g is not None:
            schedule.append(periodschedule(
                                groupname = g.groupname,
                                starttime = g.starttime,
                                endtime = g.endtime,
                                locationname = g.locationname,
                                groupid = g.groupid,
                                ismusical = g.ismusical,
                                iseveryone = g.iseveryone,
                                periodname = g.periodname,
                                periodid = g.periodid,
                                instrumentname = g.instrumentname,
                                meal = g.meal, 
                                groupdescription = g.groupdescription, 
                                composer = g.composer, 
                                musicname = g.musicname, 
                                musicwritein = g.musicwritein))

        #if we didn't find an assigned group...
        if g is None:
            #try to find an iseveryone group at the time of this period
            e = session.query(group.groupname, period.starttime, period.endtime, location.locationname, group.groupid, group.ismusical, \
                            group.iseveryone, period.periodid, period.periodname, period.meal, group.groupdescription).\
                            join(period).join(location).\
                            filter(group.iseveryone == 1, group.periodid == p.periodid).first()
            if e is not None:
                schedule.append(periodschedule(
                                groupname = e.groupname,
                                starttime = e.starttime,
                                endtime = e.endtime,
                                locationname = e.locationname,
                                groupid = e.groupid,
                                ismusical = e.ismusical,
                                iseveryone = e.iseveryone,
                                periodname = e.periodname,
                                periodid = e.periodid,
                                meal = e.meal, 
                                groupdescription = e.groupdescription))
            #if we didn't find an assigned group or an iseveryone group...
            if e is None and g is None:
                #just add the period detalis
                schedule.append(periodschedule(
                                starttime = p.starttime,
                                endtime = p.endtime,
                                periodname = p.periodname,
                                periodid = p.periodid))

    return schedule