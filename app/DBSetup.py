#This file contains initial setup for the database
import sqlalchemy
import untangle
import time
import datetime
import csv
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, exists, Enum, types, UniqueConstraint, ForeignKeyConstraint, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, aliased
from sqlalchemy.dialects.mysql.base import MSBinary
from sqlalchemy.schema import Column
from sqlalchemy.dialects.postgresql import UUID
import uuid
import os
from config import *
from sqlalchemy import *
from sqlalchemy.orm import aliased

engine = create_engine(getconfig('DATABASE_URL'))
Session = sessionmaker()
Session.configure(bind=engine)
Base = declarative_base()

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

class user(Base):
    __tablename__ = 'users'

    userid = Column(UUID, primary_key=True, unique=True)
    logonid = Column(UUID, unique=True)
    firstname = Column(String)
    lastname = Column(String)
    email = Column(String)
    arrival = Column(DateTime)
    departure = Column(DateTime)
    grouprequestcount = Column(Integer)
    isannouncer = Column(Integer)
    isconductor = Column(Integer)
    isadmin = Column(Integer)
    isactive = Column(Integer)

    @property
    def serialize(self):
        return serialize_class(self, self.__class__)

    def playsinstrument(self, session, thisinstrument):
        if session.query(userinstrument).filter(userinstrument.userid == self.userid, instrument.instrumentid == thisinstrument.instrumentid).first() is not None:
            return True
        else:
            return False

    def isplayingingroup(self, session, thisgroup):
        if session.query(groupassignment).filter(groupassignment.userid == self.userid, groupassignment.groupid == thisgroup.groupid).first() is not None:
            return True
        else:
            return False

    def isplayinginperiod(self, session, thisperiod):
        if thisgroup.periodid is not None and session.query(groupassignment).join(group).filter(groupassignment.userid == self.userid, group.periodid == thisgroup.periodid).first() is not None:
            return True
        else:
            return False

    #adds this user to a group. The group object passed in must have at least a groupid and periodid
    def addtogroup(self,session,thisgroup,thisinstrument=None):
        #check if this user plays this instrument (if an instrument was specified)
        if thisinstrument is not None and not self.playsinstrument(session, thisinstrument):
            log('ADDPLAYER: Found that player %s %s does not play instrument %s, cannot assign them to group %s' % (self.firstname,self.lastname,thisinstrument.instrumentname,thisgroup.groupid))
            raise Exception('Found that player %s %s does not play instrument %s, cannot assign them to group %s' % (self.firstname,self.lastname,thisinstrument.instrumentname,thisgroup.groupid))
        #if the user is already in this group, don't add another groupassignment, just log it
        if self.isplayingingroup(session,thisgroup):
            log('ADDPLAYER: Found that player %s %s is already in group %s. Made no changes to this player.' % (self.firstname,self.lastname,thisgroup.groupid))
        #if the user is already playing in another group at this time, raise an exception
        if thisgroup.periodid is not None and self.isplapyinginperiod(session, getperiod(session,thisgroup.periodid)):
            log('ADDPLAYER: Found that player %s %s is already assigned to a group during this period.' % (self.firstname,self.lastname))
            raise Exception('Found that player %s %s is already assigned to a group during this period.' % (self.firstname,self.lastname))
        else:
            playergroupassignment = groupassignment(userid = self.userid, groupid = thisgroup.groupid, instrumentid = thisinstrument.instrumentid)
            session.add(playergroupassignment)

    #marking a user absent for a period simply assigns them to a group called "absent" during that period
    def markabsent(self,session,thisperiod):
        absentgroup = session.query(group.groupid).join(period).filter(group.groupname == 'absent', period.periodid == thisperiod.periodid).first()
        self.addtogroup(session,absentgroup)

    #marking a user present searches for an absent listing for them, and removes it
    def markpresent(self,session,thisperiod):
        absentassignment = session.query(groupassignment).join(group).filter(group.groupname == 'absent', group.periodid == thisperiod.periodid, groupassignment.userid == self.userid).first()
        if absentassignment is not None:
            session.delete(absentassignment)

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

class music(Base):
    __tablename__ = 'musics'

    musicid = Column(Integer, primary_key=True, unique=True)
    composer = Column(Text(convert_unicode=True))
    musicname = Column(Text(convert_unicode=True))
    source = Column(Text(convert_unicode=True))
    notes = Column(Text(convert_unicode=True))
    link = Column(Text(convert_unicode=True))
    grouptemplateid = Column(Integer, ForeignKey('grouptemplates.grouptemplateid'))
    
    @property
    def serialize(self):
        return serialize_class(self, self.__class__)

    #returns true if the music is free during this period, optionally ignoring the input group
    def isfree(self,session,thisperiod,thisgroup=None):
        isfreequery = session.query(group).filter(group.periodid == thisperiod.periodid, group.musicid == self.musicid)
        if thisgroup is not None:
            isfreequery = isfreequery.filter(group.groupid != thisgroup.groupid)
        if isfreequery.first() is None:
            return True
        else:
            return False

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

class musicinstrument(Base):
    __tablename__ = 'musicinstruments'

    musicinstrumentid = Column(Integer, primary_key=True, unique=True)
    musicid = Column(Integer, ForeignKey('musics.musicid'))
    instrumentid = Column(Integer, ForeignKey('instruments.instrumentid'))

    @property
    def serialize(self):
        return serialize_class(self, self.__class__)

class group(Base):
    __tablename__ = 'groups'

    groupid = Column(Integer, primary_key=True, unique=True)
    groupname = Column(String)
    groupdescription = Column(String)
    locationid = Column(Integer, ForeignKey('locations.locationid'))
    requesttime = Column(DateTime)
    requesteduserid = Column(UUID, ForeignKey('users.userid'))
    periodid = Column(Integer, ForeignKey('periods.periodid'))
    minimumlevel = Column(Integer, default='0')
    maximumlevel = Column(Integer, default='0')
    musicid = Column(Integer, ForeignKey('musics.musicid',ondelete='SET NULL'), nullable=True)
    musicwritein = Column(String)
    ismusical = Column(Integer, default='0')
    iseveryone = Column(Integer, default='0')
    status = Column(String)

    @property
    def serialize(self):
        return serialize_class(self, self.__class__)

    #returns the total number of players that are needed for this group
    def totalinstrumentation(self, session):
        return session.query(groupassignment).filter(groupassignment.groupid == self.groupid).count()

    #returns a total number of players currently assigned to this group
    def totalallocatedplayers(self, session):
        return session.query(groupassignment).filter(groupassignment.groupid == self.groupid, groupassignment.userid != None).count()

    #get groupassignment listings for all players in this group
    def players(self,session):
        return session.query(groupassignment).filter(groupassignment.groupid == thisgroup.groupid).all()

    #returns an array of instrument objects in this group
    def instruments(self, session):
        return session.query(instrument).outerjoin(groupassignment).filter(groupassignment.groupid == self.groupid).all()

    def addtolog(self,session,text):
        if text is not None and text != '':
            session.add(grouplog(groupid = self.groupid, message = text))

    def getlevelsquery(self,session):
        return session.query(
                        user.firstname, 
                        user.lastname, 
                        instrument.instrumentname, 
                        userinstrument.level
                    ).join(groupassignment
                    ).join(group
                    ).join(userinstrument, and_(groupassignment.instrumentid == userinstrument.instrumentid, 
                                                user.userid == userinstrument.userid)
                    ).outerjoin(instrument, userinstrument.userinstrumentid == instrument.instrumentid
                    ).filter(group.groupid == self.groupid
                    )

    #this function obtains the min level, depending on if it's explicitly set, or has players already assigned
    def getminlevel(self,session):
        log('GETMINLEVEL: Finding group minimum level')
        #if the group is set to "auto", i.e. blank or 0, find the minimum level of all the players currently playing in the group
        if self.minimumlevel == 0 or self.minimumlevel == '0':
            minimumlevelob = self.getlevelsquery(session).order_by(userinstrument.level).first()
            #if we find at least one player in this group, set the minimumlevel to be this players level minus the autoassignlimitlow
            if minimumlevelob is not None:
                log('GETMINLEVEL: Found minimum level in group %s to be %s %s playing %s with level %s' % (self.groupid, minimumlevelob.firstname, minimumlevelob.lastname, minimumlevelob.instrumentname, minimumlevelob.level))
                level = int(minimumlevelob.level) - int(getconfig('AutoAssignLimitLow'))
                if level < 1:
                    level = 1
            #if we don't find a player in this group, set the minimum level to be 0 (not allowed to autofill)
            else: 
                level = 0
        #if this group's minimum level is explicitly set, use that setting
        else:
            level = self.minimumlevel
        log('GETMINLEVEL: Found minimum level of group %s to be %s' % (self.groupid,level))
        return int(level)

    #this function obtains the max level, depending on if it's explicitly set, or has players already assigned
    def getmaxlevel(self,session):
        log('GETMAXLEVEL: Finding group maximum level')
        #if the group is set to "auto", i.e. blank or 0, find the maximum level of all the players currently playing in the group
        if self.maximumlevel == '0' or self.maximumlevel == 0:
            maximum = self.getlevelsquery(session).order_by(userinstrument.level).first()
            #if we find at least one player in this group, set the maximumlevel to be this players level plus the autoassignlimithigh
            if maximumlevelob is not None:
                log('GETMAXLEVEL: Found minimum level in group %s to be %s %s playing %s with level %s' % (self.groupid, minimumlevelob.firstname, minimumlevelob.lastname, minimumlevelob.instrumentname, minimumlevelob.level))
                level = int(minimumlevelob.level) + int(getconfig('AutoAssignLimitHigh'))
                if level > int(getconfig('AutoAssignLimitHigh')):
                    level = getconfig('MaximumLevel')
            #if we don't find a player in this group, set the maximum level to 0 (not allowed to autofill)
            else:
                level = 0
        #if this group's maximum level is explicitly set, use that setting
        else:
            level = self.maximumlevel
        log('GETMAXLEVEL: Found maximum level of group %s to be %s' % (self.groupid,level))
        return int(level)

    #deletes the group
    def delete(self, session):
        thisgroupassignments = session.query(groupassignment).filter(groupassignment.groupid == self.groupid).all()
        for a in thisgroupassignments:
            session.delete(a)
        session.commit()
        session.delete(self)
        session.commit()

    #checks if the group can be confirmed, and confirms the group
    def confirm(self, session):
        log('CONFIRMGROUP: Attempting to confirm group name:%s id:%s' % (self.groupname,self.groupid))
        if self.locationid is None:
            raise Exception('Failed to confirm group %s becasue the group is missing a locationid' % self.groupname)
        if self.periodid is None:
            raise Exception('Failed to confirm group %s becasue the group is missing a periodid' % self.groupname)
        if self.groupname is None or self.groupname == '':
            raise Exception('Failed to confirm group becasue the group is missing a groupname')
        thisperiod = getperiod(session,self.periodid)
        thislocation = getlocation(session,self.locationid)
        if not thislocation.isfree(session,thisperiod,self):
            raise Exception('Failed to confirm group %s becasue the group location is already in use by another group at this time' % self.groupname)
        if self.musicid is not None:
            thismusic = getmusic(session,self.musicid)
            if not thismusic.isfree(session,thisperiod,self):
                raise Exception('Failed to confirm group %s because the group music is already in use by another group at this time' % self.groupname)
        #check if any players are playing in other groups
        if self.playerclash(session,thisperiod):
            raise Exception('Failed to confirm group becasue at least one player is in another group at this time.')
        else:
            log('CONFIRMGROUP: Successfully confirmed group name:%s id:%s' % (self.groupname,self.groupid))
            self.status = 'Confirmed'
            
    #adds a single player to this group. The object passed in needs to have at least a userid
    def addplayer(self,session,thisuser,thisinstrument):
        #check if this user plays this instrument
        if not thisuser.playsinstrument(session,thisinstrument):
            log('ADDPLAYER: Found that player %s %s does not play instrument %s, cannot assign them to group %s' % (player.firstname,player.lastname,instrumentname,self.groupid))
            raise Exception('Found that player %s %s does not play instrument %s, cannot assign them to group %s' % (player.firstname,player.lastname,instrumentname,self.groupid))
        #if the player is already in this group, don't make another groupassignment, just log it.
        if thisuser.isplayingingroup(session,self):
            log('ADDPLAYER: Found that player %s %s is already in this group. Made no changes to this player.' % (player.firstname,player.lastname))
        #if the player is in another group at this time, raise an exception
        elif self.periodid is not None and thisuser.isplayinginperiod(session,getperiod(session,self.periodid)) is not None:
            log('ADDPLAYER: Found that player %s %s is already assigned to a group during this period.' % (player.firstname,player.lastname))
            raise Exception('Found that player %s %s is already assigned to a group during this period.' % (player.firstname,player.lastname))
        #otherwise, create a groupassignment for them
        else:
            log('ADDPLAYER: Adding player %s %s to group playing instrument %s' % (player.firstname,player.lastname,instrumentname))
            playergroupassignment = groupassignment(userid = thisuser.userid, groupid = self.groupid, instrumentid = thisinstrument.instrumentid)
            session.add(playergroupassignment)

    #checks if this group can fit into a given period or not (checks player clashes with other groups)
    def playerclash(self,session,thisperiod):
        playersPlayingInPeriod = session.query(groupassignment.userid).join(group).filter(group.groupid != self.groupid).filter(group.periodid == thisperiod.periodid)
        if session.query(groupassignment.userid).filter(groupassignment.groupid == self.groupid, groupassignment.userid.in_(playersPlayingInPeriod)).first() is not None:
            log('PLAYERCLASH: Found a player clash for group with id:%s and period id:%s' % (self.groupid,selectedperiod.periodid))
            return True
        else:
            log('PLAYERCLASH: Found that group id:%s can fit into period id:%s' % (self.groupid,selectedperiod.periodid))
            return False

    def purgeoldplayers(self,session):
        log('GROUPPURGE: Purging old players from group name:%s id:%s' % (self.groupname,self.groupid))
        oldplayers = session.query(groupassignment
                        ).join(user
                        ).filter(
                            groupassignment.groupid == self.groupid,
                            user.departure < datetime.datetime.now(),
                            user.isactive != 1
                        ).all()
        for p in oldplayers:
            session.delete(p)

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

class grouplog(Base):
    __tablename__ = 'grouplogs'

    logid = Column(Integer, primary_key=True, unique=True)
    groupid = Column(Integer, ForeignKey('groups.groupid'))
    timestamp = Column(DateTime, default=datetime.datetime.now())
    message = Column(Text(convert_unicode=True))

    @property
    def serialize(self):
        return serialize_class(self, self.__class__)

class grouptemplate(Base):
    __tablename__ = 'grouptemplates'

    grouptemplateid = Column(Integer, primary_key=True, unique=True)
    grouptemplatename = Column(String)
    size = Column(String)
    defaultminimumlevel = Column(Integer)
    delautmaximumlevel = Column(Integer)
    defaultlocationid = Column(Integer, ForeignKey('locations.locationid'))

    @property
    def serialize(self):
        return serialize_class(self, self.__class__)

class grouptemplateinstrument(Base):
    __tablename__ = 'grouptemplateinstruments'

    grouptemplateinstrumentid = Column(Integer, primary_key=True, unique=True)
    grouptemplateid = Column(Integer, ForeignKey('grouptemplates.grouptemplateid'))
    instrumentid = Column(Integer, ForeignKey('instruments.instrumentid'))

    @property
    def serialize(self):
        return serialize_class(self, self.__class__)

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

class userinstrument(Base):
    __tablename__ = 'userinstruments'

    userinstrumentid = Column(Integer, primary_key=True, unique=True)
    userid = Column(UUID, ForeignKey('users.userid'))
    instrumentid = Column(Integer, ForeignKey('instruments.instrumentid'))
    level = Column(Integer)
    isprimary = Column(Integer)
    isactive = Column(Integer)

    @property
    def serialize(self):
        return serialize_class(self, self.__class__)

#gets a userinstrument object from a instrumentid
def getuserinstrument(session,instrumentid):
    if instrumentid is None:
        return None
    else:
        thisuserinstrument = session.query(instrument).filter(instrument.instrumentid == instrumentid).first()
        if thisinstrument is None:
            log('GETUSERINSTRUMENT: Exception - Could not find instrument %s in database' % (instrumentid))
            raise Exception('Could not find instrument in database')
        else:
            return thisuserinstrument

class groupassignment(Base):
    __tablename__ = 'groupassignments'

    groupassignmentid = Column(Integer, primary_key=True, unique=True)
    userid = Column(UUID, ForeignKey('users.userid'), nullable=True, default=None)
    groupid = Column(Integer, ForeignKey('groups.groupid'))
    instrumentid = Column(Integer, ForeignKey('instruments.instrumentid'))

    @property
    def serialize(self):
        return serialize_class(self, self.__class__)

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

class instrument(Base):
    __tablename__ = 'instruments'

    instrumentid = Column(Integer, primary_key=True, unique=True)
    instrumentname = Column(Text(convert_unicode=True))
    order = Column(Integer, unique=True)

    @property
    def serialize(self):
        return serialize_class(self, self.__class__)

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
        thisinstrument = session.query(instrument).filter(instrument.instrumentname == instrumentname.capitalize().replace(" ", "")).first()
        if thisinstrument is None:
            log('GETINSTRUMENTBYNAME: Exception - Could not find instrument %s in database' % (instrumentid))
            raise Exception('Could not find instrument in database')
        else:
            return thisinstrument

class location(Base):
    __tablename__ = 'locations'

    locationid = Column(Integer, primary_key=True, unique=True)
    locationname = Column(String)
    capacity = Column(Integer, default='0')
    autoallocate = Column(Integer, default='1')

    @property
    def serialize(self):
        return serialize_class(self, self.__class__)

    #returns true if the location is free during this period, optionally ignoring the input group
    def isfree(self,session,thisperiod,thisgroup=None):
        isfreequery = session.query(group).filter(group.periodid == thisperiod.periodid, group.locationid == self.locationid)
        if thisgroup is not None:
            isfreequery = isfreequery.filter(group.groupid != thisgroup.groupid)
        if isfreequery.first() is None:
            return True
        else:
            return False

#gets a location object from a locationid
def getlocation(session,locationid):
    if locationid is None:
        return None
    else:
        thislocation = session.query(location).filter(location.locationid == locationid).first()
        if thislocation is None:
            log('GETLOCATION: Exception - Could not find location %s in database' % (locationid))
            raise Exception('Could not find location in database')
        else:
            return thislocation

#this table controls if instruments are able to be placed into a location, for example - you may only have access to a piano in one room
class locationinstrument(Base):
    __tablename__ = 'locationinstruments'

    locationinstrumentid = Column(Integer, primary_key=True, unique=True)
    instrumentid = Column(Integer, ForeignKey('instruments.instrumentid'))
    isdisabled = Column(Integer)

    @property
    def serialize(self):
        return serialize_class(self, self.__class__)

class period(Base):
    __tablename__ = 'periods'

    periodid = Column(Integer, primary_key=True, unique=True)
    starttime = Column(DateTime)
    endtime = Column(DateTime)
    periodname = Column(String)
    meal = Column(Integer)

    @property
    def serialize(self):
        return serialize_class(self, self.__class__)

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

class announcement(Base):
    __tablename__ = 'announcements'

    announcementid = Column(Integer, primary_key=True, unique=True)
    creationtime = Column(DateTime)
    content = Column(Text(convert_unicode=True))

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

Base.metadata.create_all(engine)

#The schedule class is not a table, it's used when getting user schedules
class periodschedule:

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

    @property
    def serialize(self):
        return ({'groupname': self.groupname,
                'starttime': self.starttime,
                'endtime': self.endtime,
                'locationname': self.locationname,
                'groupid': self.groupid,
                'ismusical': self.ismusical,
                'iseveryone': self.iseveryone,
                'periodid': self.periodid,
                'periodname': self.periodname,
                'instrumentname': self.instrumentname,
                'meal': self.meal,
                'groupdescription': self.groupdescription,
                'composer': self.composer,
                'musicname': self.musicname,
                'musicwritein': self.musicwritein})

#this section manages the admin user. This will be the user that the admin will use to set up the database from the webapp
session = Session()
#try to find a user named 'Administrator' whos ID matches the app's configured AdminUUID
admin = session.query(user).filter(user.logonid == getconfig('AdminUUID'), user.firstname == 'Administrator').first()
#if we don't find one, it means that this is the first boot, or the AdminUUID has been changed
if admin is None:
    #try to find a user called Administrator
    findadmin = session.query(user).filter(user.firstname == 'Administrator').first()
    #if we find one, it means that someone has changed the AdminUUID parameter. Update this user to match it.
    if findadmin is not None:
        log('Found Administrator user did not match AdminUUID parameter. Updating the user details to match.')
        findadmin.logonid = getconfig('AdminUUID')
        session.merge(findadmin)
    #if we don't find one, this is the first boot of the app. Create the administrator user.
    else:
        log('Welcome to the music camp scheduler! This is the first boot of the app. Look in your applicaiton parameters for the AdminUUID parameter, then log in to the setup page with websitename/user/AdminUUID(replace this with your admin UUID)/setup/')
        admin = user(logonid = getconfig('AdminUUID'), userid = str(uuid.uuid4()), firstname = 'Administrator', lastname = 'A', isactive = 0, \
            arrival = datetime.datetime.strptime(getconfig('StartTime'), '%Y-%m-%d %H:%M'), departure = datetime.datetime.strptime(getconfig('EndTime'), '%Y-%m-%d %H:%M'))
        session.add(admin)
    session.commit()
session.close()
session.flush()

#Database Build section. The below configures periods and groups depending on how the config.xml is configured.
def dbbuild(configfile):
    #try:
    log('Initiating initial database build from config file')
    conf = untangle.parse(configfile)
    #Grab the camp start and end times from the config file
    CampStartTime = datetime.datetime.strptime(getconfig('StartTime'), '%Y-%m-%d %H:%M')
    CampEndTime = datetime.datetime.strptime(getconfig('EndTime'), '%Y-%m-%d %H:%M')
    #Prepare for the loop, which will go through each day of camp and create an instance of each day's period
    ThisDay = datetime.datetime.strptime(datetime.datetime.strftime(CampStartTime, '%Y-%m-%d'), '%Y-%m-%d')
    #start our session, then go through the loop
    session = Session()

    #create the instrument objects, and keep the order written in the config file
    iorder = 0
    for i in conf.root.CampDetails['Instruments'].split(","):
        thisinstrument = session.query(instrument).filter(instrument.instrumentname == i).first()
        if thisinstrument is None:
            thisinstrument = instrument(instrumentname = i, order = iorder)
            session.add(thisinstrument)
            log('Created instrument: %s' % i)
            iorder = iorder + 1
    session.commit()

    #create locations in the database
    find_location = session.query(location).filter(location.locationname == 'None').first()
    if find_location is None:
        session.add(location(locationname = 'None', autoallocate = 0))
        log('Created location: None')
    for x in range(0,len(conf.root.CampDetails.Location)):
        find_location = session.query(location).filter(location.locationname == conf.root.CampDetails.Location[x]['Name']).first()
        if find_location is None:
            newlocation = location(
                locationname=conf.root.CampDetails.Location[x]['Name'],
                capacity=conf.root.CampDetails.Location[x]['Capacity']
                )
            log('Created location: %s' % newlocation.locationname)
            if conf.root.CampDetails.Location[x]['AutoAllocate'] is not None:
                newlocation.autoallocate = conf.root.CampDetails.Location[x]['AutoAllocate']
            session.add(newlocation)
            #create instrument restrictions in the locationinstrument table for disabled instruments
            if conf.root.CampDetails.Location[x]['DisabledInstruments'] is not None:
                for i in conf.root.CampDetails.Location[x]['DisabledInstruments'].split(','):
                    thislocationinstrument = session.query(locationinstrument).join(instrument).filter(instrument.instrumentname == i).first()
                    if thislocationinstrument is not None:
                        thislocationinstrument = locationinstrument(instrumentname = i, isdisabled = 1) 
                        session.add(thislocationinstrument)  
    session.commit()

    loop = 'start'
    #For each day covered by the camp start and end time
    while loop == 'start':
        log('Creating initial groups for %s' % ThisDay)
        #For each period covered by the camp's configured period list
        for x in range(0,len(conf.root.CampDetails.Period)):
            ThisStartTime = datetime.datetime.strptime((datetime.datetime.strftime(ThisDay, '%Y-%m-%d') + ' ' + conf.root.CampDetails.Period[x]['StartTime']),'%Y-%m-%d %H:%M')
            ThisEndTime = datetime.datetime.strptime((datetime.datetime.strftime(ThisDay, '%Y-%m-%d') + ' ' + conf.root.CampDetails.Period[x]['EndTime']),'%Y-%m-%d %H:%M')
            ThisPeriodName = conf.root.CampDetails.Period[x]['Name']
            ThisPeriodMeal = conf.root.CampDetails.Period[x]['Meal']
            find_period = session.query(period).filter(period.periodname == ThisPeriodName,period.starttime == ThisStartTime,period.endtime == ThisEndTime).first()
            #only create periods and groups if we are inside the specific camp start and end time
            if ThisStartTime <= CampEndTime and ThisStartTime >= CampStartTime:
                find_period = session.query(period).filter(period.periodname == ThisPeriodName,period.starttime == ThisStartTime,period.endtime == ThisEndTime).first()
                #if no period exists in the database, create it
                if find_period is None:
                    find_period = period(periodname = ThisPeriodName,starttime = ThisStartTime,endtime = ThisEndTime,meal=ThisPeriodMeal)
                    session.add(find_period)
                    log('Created period: %s at %s with meal switch set to %s' % (find_period.periodname, find_period.starttime, find_period.meal))
                #check if this period has public events that need to be created
                for x in range(0,len(conf.root.CampDetails.PublicEvent)):
                    find_event = session.query(group).filter(group.groupname == conf.root.CampDetails.PublicEvent[x]['Name'],group.periodid == find_period.periodid,group.iseveryone == 1,group.ismusical == 0).first()
                    if find_event is None and find_period.periodname == conf.root.CampDetails.PublicEvent[x]['Period']:
                        log('right before locationname search')
                        find_location = session.query(location).filter(location.locationname == conf.root.CampDetails.PublicEvent[x]['Location']).first()
                        if find_location is None:
                            log('User input a location that does not exist when configuring event %s' % conf.root.CampDetails.PublicEvent[x]['Name'])
                        else:
                            find_event = group(groupname = conf.root.CampDetails.PublicEvent[x]['Name'],periodid = find_period.periodid,iseveryone = 1,ismusical = 0,locationid = find_location.locationid,status="Confirmed",requesttime=datetime.datetime.now())
                            if conf.root.CampDetails.PublicEvent[x]['Description'] is not None:
                                find_event.groupdescription = conf.root.CampDetails.PublicEvent[x]['Description']
                            session.add(find_event)
                            log('Created public event: %s during period %s at %s' % (find_event.groupname, find_period.periodname, find_period.starttime))
                #if no absentgroup exists in the database, create it
                find_absent_group = session.query(group).filter(group.groupname == 'absent',group.periodid == find_period.periodid).first()
                if find_absent_group is None:
                    find_absent_group = group(groupname = 'absent',periodid = find_period.periodid,ismusical=0,status="Confirmed",requesttime=datetime.datetime.now(),minimumlevel=0,maximumlevel=0)
                    session.add(find_absent_group)
                    log('Created group: placeholder for absentees at %s' % (find_period.starttime))
            #if we hit the camp's configured end time, then stop looping
            if ThisStartTime > CampEndTime:
                loop = 'stop'
        ThisDay = ThisDay + datetime.timedelta(days=1)  
    session.commit()
        
    #create group templates
    for x in range(0,len(conf.root.CampDetails.GroupTemplate)):
        find_template = session.query(grouptemplate).filter(grouptemplate.grouptemplatename == conf.root.CampDetails.GroupTemplate[x]['Name']).first()
        if find_template is None:
            template = grouptemplate()
            setattr(template, 'grouptemplatename', conf.root.CampDetails.GroupTemplate[x]['Name'])
            setattr(template, 'size', conf.root.CampDetails.GroupTemplate[x]['Size'])
            setattr(template, 'minimumlevel', conf.root.CampDetails.GroupTemplate[x]['MinimumLevel'])
            setattr(template, 'maximumlevel', conf.root.CampDetails.GroupTemplate[x]['MaximumLevel'])
            if conf.root.CampDetails.GroupTemplate[x]['DefaultLocation'] is not None:
                defaultloc = session.query(location).filter(location.locationname == conf.root.CampDetails.GroupTemplate[x]['DefaultLocation']).first()
                log('Found group default location for %s to be %s' % (template.grouptemplatename, defaultloc.locationname))
                setattr(template, 'defaultlocationid', defaultloc.locationid)
            else:
                noneloc = session.query(location).filter(location.locationname == 'None').first()
                log('No default location set for template %s. Setting default location to be %s' % (template.grouptemplatename, noneloc.locationname))
                setattr(template, 'defaultlocationid', noneloc.locationid)
            session.add(template)
            session.flush()
            for i in session.query(instrument).all():
                if conf.root.CampDetails.GroupTemplate[x][i.instrumentname] is not None:
                    for x in range(0,int(conf.root.CampDetails.GroupTemplate[x][i.instrumentname])):
                        session.add(grouptemplateinstrument(grouptemplateid = template.grouptemplateid, instrumentid = i.instrumentid))
            log('Created grouptemplate: %s with size %s' % (template.grouptemplatename, template.size))
    session.commit()
    session.close()
    log('Finished database build')
    return 'Success'
    
    """except Exception as ex:
        session.rollback()
        session.close()
        return ('Failed to import with exception: %s.' % ex)"""

def importusers(file):
    #try:
    session = Session()
    CampStartTime = datetime.datetime.strptime(getconfig('StartTime'), '%Y-%m-%d %H:%M')
    CampEndTime = datetime.datetime.strptime(getconfig('EndTime'), '%Y-%m-%d %H:%M')
    #the below reads the camp input file and creates the users and instrument bindings it finds there.
    #ifile  = open(file, "rb")
    reader = csv.reader(file, delimiter=',')
    rownum = 0
    for row in reader:
        # Save header row.
        if rownum == 0:
            header = row
        else:
            thisuser = user()
            thisuser.userid = str(uuid.uuid4())
            thisuser.logonid = str(uuid.uuid4())
            thisuser.isactive = 1
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
            if row[15] is not '':
                thisuser.email = row[15]
            session.add(thisuser)
            log('Created user: %s %s' % (thisuser.firstname, thisuser.lastname))
            session.commit()
            if row[4] is not '':
                instrument1 = userinstrument(userid = thisuser.userid, instrumentid = getinstrumentbyname(session,row[4]).instrumentid, level = row[5], isprimary = 1, isactive = 1)
                session.add(instrument1)
                log('Created instrument listing: %s at level %s for %s' % (getinstrument(session,instrument1.instrumentid).instrumentname, instrument1.level, thisuser.firstname))
            if row[6] is not '':
                instrument2 = userinstrument(userid = thisuser.userid, instrumentid = getinstrumentbyname(session,row[6]).instrumentid, level = row[7], isprimary = 0, isactive = 1)
                session.add(instrument2)
                log('Created instrument listing: %s at level %s for %s' % (getinstrument(session,instrument2.instrumentid).instrumentname, instrument2.level, thisuser.firstname))
            if row[8] is not '':
                instrument3 = userinstrument(userid = thisuser.userid, instrumentid = getinstrumentbyname(session,row[8]).instrumentid, level = row[9], isprimary = 0, isactive = 1)
                session.add(instrument3)
                log('Created instrument listing: %s at level %s for %s' % (getinstrument(session,instrument3.instrumentid).instrumentname, instrument3.level, thisuser.firstname))
            if row[10] is not '':
                instrument4 = userinstrument(userid = thisuser.userid, instrumentid = getinstrumentbyname(session,row[10]).instrumentid, level = row[11], isprimary = 0, isactive = 1)
                session.add(instrument4)
                log('Created instrument listing: %s at level %s for %s' % (getinstrument(session,instrument4.instrumentid).instrumentname, instrument4.level, thisuser.firstname))
        rownum += 1
    session.commit()
    userscount = session.query(user).count()
    session.close()
    return ('Success')
    """except Exception as ex:
        session.rollback()
        session.close()
        log('IMPORTUSERS: Failed to import with exception: %s.' % ex)
        return ('Failed to import with exception: %s.' % ex)"""

def importmusic(file):
    try:
        session = Session()
        reader = csv.reader(file, delimiter=',')
        headers = []
        headerfound = False
        for row in reader:
            #if this is the first iteration, the headers should be here
            if not headerfound:
                for column in row:
                    headers.append(column)
                log('IMPORTMUSIC: Headers for this import:')
                log(headers)
                headerfound = True
            #if it's not the first iteration, it's a data row
            else:
                thismusic = music()
                for idx, item in enumerate(row):
                    if headers[idx] in getconfig('Instruments').split(",") and item == '':
                        setattr(thismusic,headers[idx],0)
                    elif item != '':
                        setattr(thismusic,headers[idx],item)
                matchingtemplate = session.query(grouptemplate).filter(*[getattr(thismusic,i) == getattr(grouptemplate,i) for i in instrumentlist]).first()
                if matchingtemplate is not None:
                    log('Found a template matching this music: %s' % matchingtemplate.grouptemplatename)
                    thismusic.grouptemplateid = matchingtemplate.grouptemplateid
                session.add(thismusic)
        session.commit()
        session.close()
        return ('Success')
    except Exception as ex:
        session.rollback()
        session.close()
        log('IMPORTMUSIC: Failed to import with exception: %s.' % ex)
        return ('Failed to import with exception: %s.' % ex)

