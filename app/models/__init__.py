from app.config import *
import json

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

#gets a userinstrument object from a instrumentid
def getuserinstrument(session,instrumentid):
    if instrumentid is None:
        return None
    else:
        thisuserinstrument = session.query(instrument).filter(instrument.instrumentid == instrumentid).first()
        if thisuserinstrument is None:
            log('GETUSERINSTRUMENT: Exception - Could not find instrument %s in database' % (instrumentid))
            raise Exception('Could not find instrument in database')
        else:
            return thisuserinstrument

#gets a music object from a musicid
def getmusic(session,musicid=None):
    music_query = session.query(music)
    if musicid is not None:
        thismusic = music_query.filter(music.musicid == musicid).first()
    else:
        thismusic = music_query.all()
    if thismusic is None:
        log('GETMUSIC: Exception - Could not find music in database' % (musicid))
        raise Exception('Could not find music in database')
    else:
        return thismusic

#gets a group object from a groupid
def getgroup(session,groupid=None):
    group_query = session.query(group)
    if groupid is not None:
        thisgroup = group_query.filter(group.groupid == groupid).first()
    else:
        thisgroup = group_query.all()
    if thisgroup is None:
        log('GETgroup: Exception - Could not find group in database' % (groupid))
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

#retrieves a list of group templates. By default retrieves all group templates.
#size: optional parameter restricting the retrieved templates to a single size, either small or large
#user: optional parameter restricting the retrieved templates to those a specified user can actually play in
def getgrouptemplates(session,size=None,thisuser=None):
    try:
        gtquery = session.query(grouptemplate)
        if thisuser is not None:
            gtquery = gtquery.join(grouptemplateinstrument
                    ).join(instrument
                    ).join(userinstrument
                    ).join(user
                    ).filter(user.userid == thisuser.userid)
        if size is not None:
            gtquery = gtquery.filter(grouptemplate.size == size)
        return gtquery.all()
    except Exception as ex:
        log('GETGROUPTEMPLATE: Exception - failed to find templates')
        raise Exception('Could not retrieve templates')

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

def getinstrumentbyname(session,instrumentname):
    if instrumentname is None:
        return None
    else:
        thisinstrument = session.query(instrument).filter(instrument.instrumentname == instrumentname).first()
        if thisinstrument is None:
            
            raise Exception('Could not find instrument %s in database' % instrumentname)
        else:
            return thisinstrument

#returns all instruments as instrument obejcts
def getinstruments(session):
    return session.query(instrument).all()

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

#The schedule class is not a table, it's used when getting user schedules
class periodschedule(object):

    def __init__(self,
                    groupname = None,
                    starttime = None,
                    endtime = None,
                    locationname = None,
                    groupid = None,
                    ismusical = None,
                    iseveryone = None,
                    periodid = None,
                    periodname = None,
                    instrumentname = None,
                    meal = None,
                    groupdescription = None,
                    composer = None,
                    musicname = None,
                    musicwritein = None):
        self.groupname = groupname
        self.starttime = starttime
        self.endtime = endtime
        self.locationname = locationname
        self.groupid = groupid
        self.ismusical = ismusical
        self.iseveryone = iseveryone
        self.periodid = periodid
        self.periodname = periodname
        self.instrumentname = instrumentname
        self.meal = meal
        self.groupdescription = groupdescription
        self.composer = composer
        self.musicname = musicname
        self.musicwritein = musicwritein

#The player class is not a table, it's used when retrieving players
class player(object):

    def __init__(self,
                    userid = None,
                    firstname = None,
                    lastname = None,
                    instrumentid = None,
                    instrumentname = None,
                    level = None,
                    isprimary = None):
        self.userid = userid
        self.firstname = firstname
        self.lastname = lastname
        self.instrumentid = instrumentid
        self.instrumentname = instrumentname
        self.level = level
        self.isprimary = isprimary

#converts a SQLAlchemy object from a row retrieved to a player class
def converttoplayer(o):
    return player(
        userid = o.userid,
        firstname = o.firstname,
        lastname = o.lastname,
        instrumentid = o.instrumentid,
        instrumentname = o.instrumentname,
        level = o.level,
        isprimary = o.isprimary
    )

def getplayers(session):
        playersdump = session.query(user.userid,
                        user.firstname,
                        user.lastname,
                        instrument.instrumentid,
                        instrument.instrumentname,
                        userinstrument.level,
                        userinstrument.isprimary
                    ).join(userinstrument
                    ).join(instrument
                    ).filter(user.isactive == 1, 
                        userinstrument.isactive == 1,
                        user.departure >= today(1)
                    ).all()
        players = []
        for p in playersdump:
            players.append(converttoplayer(p))
        return players

#import all models in this folder
from .base import Base
from .announcement import announcement
from .group import group
from .groupassignment import groupassignment
from .grouplog import grouplog
from .grouptemplate import grouptemplate
from .grouptemplateinstrument import grouptemplateinstrument
from .instrument import instrument
from .location import location
from .locationinstrument import locationinstrument
from .music import music
from .musicinstrument import musicinstrument
from .period import period
from .userinstrument import userinstrument
from .user import user