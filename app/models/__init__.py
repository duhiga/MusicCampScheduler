from app.config import *
log('Importing Model Classes')

#import all models in this folder
log('Importing Base')
from .base import Base
log('Importing announcement')
from .announcement import announcement
log('Importing group')
from .group import group
log('Importing groupassignment')
from .groupassignment import groupassignment
log('Importing grouptemplate')
from .grouptemplate import grouptemplate
log('Importing instrument')
from .instrument import instrument
log('Importing location')
from .location import location
log('Importing music')
from .music import music
log('Importing period')
from .period import period
log('Importing user')
from .user import user

def serialize_class(inst, cls):
    convert = dict()
    # add your coversions for things like datetimes
    # and what-not that aren't serializable.
    d = dict()
    for c in cls.__table__.columns:
        v = getattr(inst, c.name)
        if c.type in convert.keys() and v is not None:
            try:
                d[c.name] = convert[c.type](v)
            except:
                d[c.name] = "Error:  Failed to covert using ", str(convert[c.type])
        elif v is None:
            d[c.name] = str()
        else:
            d[c.name] = v
    return d

#gets a user object from a userid, or a logodin if the logon flag is set to true
def getuser(session,userid,logon=False):
    if userid is None:
        return None
    else:
        if logon:
            thisuser = session.query(user).filter(user.logonid == userid).first()
        else:
            thisuser = session.query(user).filter(user.userid == userid).first()
        if thisuser is None:
            log('GETUSER: Exception - Could not find user:%s logon:%s in database' % (userid,logon))
            raise Exception('Could not find user in database')
        else:
            return thisuser

#gets a music object from a musicid
def getmusic(session,musicid):
    if musicid is None:
        return None
    else:
        thismusic = session.query(music).filter(music.musicid == musicid).first()
        if thismusic is None:
            log('GETMUSIC: Exception - Could not find music %s in database' % (musicid))
            raise Exception('Could not find music in database')
        else:
            return thismusic

#gets a group object from a groupid
def getgroup(session,groupid):
    if groupid is None:
        return None
    else:
        thisgroup = session.query(group).filter(group.groupid == groupid).first()
        if thisgroup is None:
            log('GETGROUP: Exception - Could not find group %s in database' % (groupid))
            raise Exception('Could not find group in database')
        else:
            return thisgroup



#gets a grouptemplate object from a grouptemplateid
def getgrouptemplate(session,grouptemplateid):
    if grouptemplateid is None:
        return None
    else:
        thisgrouptemplate = session.query(grouptemplate).filter(grouptemplate.grouptemplateid == grouptemplateid).first()
        if thisgrouptemplate is None:
            log('GETGROUPTEMPLATE: Exception - Could not find grouptemplate %s in database' % (grouptemplateid))
            raise Exception('Could not find grouptemplate in database')
        else:
            return thisgrouptemplate

#gets a instrument object from a instrumentid
def getinstrument(session,instrumentid):
    if instrumentid is None:
        return None
    else:
        thisinstrument = session.query(instrument).filter(instrument.instrumentid == instrumentid).first()
        if thisinstrument is None:
            log('GETINSTRUMENT: Exception - Could not find instrument %s in database' % (instrumentid))
            raise Exception('Could not find instrument in database')
        else:
            return thisinstrument

#gets a groupassignment object from a groupassignmentid
def getgroupassignment(session,groupassignmentid):
    if groupassignmentid is None:
        return None
    else:
        thisgroupassignment = session.query(groupassignment).filter(groupassignment.groupassignmentid == groupassignmentid).first()
        if thisgroupassignment is None:
            log('GETGROUPASSIGNMENT: Exception - Could not find groupassignment %s in database' % (groupassignmentid))
            raise Exception('Could not find groupassignment in database')
        else:
            return thisgroupassignment

#gets a location object from a locationid
def getlocation(session,locationid):
    if locationid is None:
        return None
    else:
        if locationid is None:
            return None
        else:
            thislocation = session.query(location).filter(location.locationid == locationid).first()
            if thislocation is None:
                log('GETLOCATION: Exception - Could not find location %s in database' % (locationid))
                raise Exception('Could not find location in database')
            else:
                return thislocation

#gets a period object from a periodid
def getperiod(session,periodid):
    if periodid is None:
        return None
    else:
        thisperiod = session.query(period).filter(period.periodid == periodid).first()
        if thisperiod is None:
            log('GETPERIOD: Exception - Could not find period %s in database' % (periodid))
            raise Exception('Could not find period in database')
        else:
            return thisperiod

#gets a announcement object from a announcementid
def getannouncement(session,announcementid):
    if announcementid is None:
        return None
    else:
        thisannouncement = session.query(announcement).filter(announcement.announcementid == announcementid).first()
        if thisannouncement is None:
            log('GETANNOUNCEMENT: Exception - Could not find announcement %s in database' % (announcementid))
            raise Exception('Could not find announcement in database')
        else:
            return thisannouncement

"""
#add the columns for each instrument in the application configuration to the group, grouptemplate, music and location tables
instrumentlist = getconfig('Instruments').split(",")
log('Setting up columns for instruments in database: %s' % getconfig('Instruments'))
for i in instrumentlist:
    setattr(group, i, Column(Integer, default='0'))
    setattr(grouptemplate, i, Column(Integer, default='0'))
    setattr(music, i, Column(Integer, default='0'))
    setattr(location, i, Column(Integer, default='1'))
"""