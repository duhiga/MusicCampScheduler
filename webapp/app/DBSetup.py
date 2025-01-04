#This file contains initial setup for the database
import sqlalchemy
import untangle
import time
import datetime
import csv
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, exists, Enum, types, UniqueConstraint, ForeignKeyConstraint, Text, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, aliased
from sqlalchemy.dialects.mysql.base import MSBinary
from sqlalchemy.schema import Column
from sqlalchemy.dialects.postgresql import UUID
import enum
import uuid
import os
from .config import *
from sqlalchemy import *
from sqlalchemy.orm import aliased
import math

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
    dietaryrequirements = Column(String, default='Normal')
    agecategory = Column(String, default='Adult')

    @property
    def serialize(self):
        return serialize_class(self, self.__class__)

    #adds this user to a group. The group object passed in must have at least a groupid and periodid
    def addtogroup(self, session, thisgroup, instrumentname=None):
        #check if this user plays this instrument (if an instrument was specified)
        if instrumentname is not None and session.query(instrument).filter(instrument.userid == self.userid, instrument.instrumentname == instrumentname).first() is None:
            log('ADDPLAYER: Found that player %s %s does not play instrument %s, cannot assign them to group %s' % (self.firstname,self.lastname,instrumentname,thisgroup.groupid))
            raise Exception('Found that player %s %s does not play instrument %s, cannot assign them to group %s' % (self.firstname,self.lastname,instrumentname,thisgroup.groupid))
        #if the user is already in this group, don't add another groupassignment, just log it
        if session.query(groupassignment).filter(groupassignment.userid == self.userid, groupassignment.groupid == thisgroup.groupid).first() is not None:
            log('ADDPLAYER: Found that player %s %s is already in group %s. Made no changes to this player.' % (self.firstname,self.lastname,thisgroup.groupid))
        #if the user is already playing in another group at this time, raise an exception
        elif thisgroup.periodid is not None and session.query(groupassignment).join(group).filter(groupassignment.userid == self.userid, group.periodid == thisgroup.periodid).first() is not None:
            log('ADDPLAYER: Found that player %s %s is already assigned to a group during this period.' % (self.firstname,self.lastname))
            raise Exception('Found that player %s %s is already assigned to a group during this period.' % (self.firstname,self.lastname))
        else:
            playergroupassignment = groupassignment(userid = self.userid, groupid = thisgroup.groupid, instrumentname = instrumentname)
            session.add(playergroupassignment)

    #marking a user absent for a period simply assigns them to a group called "absent" during that period
    def markabsent(self,session,thisperiod):
        absentgroup = session.query(group.groupid, group.periodid).join(period).filter(group.groupname == 'absent', period.periodid == thisperiod.periodid).first()
        if absentgroup is None:
            absentgroup = group(groupname = "absent", periodid = thisperiod.periodid)
            session.add(absentgroup)
            session.commit()
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
            log('GETUSER: Could not find user:%s logon:%s in database' % (userid,logon))
            raise Exception('Could not find user in database')
        else:
            return thisuser

class music(Base):
    __tablename__ = 'musics'

    musicid = Column(Integer, primary_key=True, unique=True)
    isactive = Column(Integer, default='1')
    composer = Column(Text(convert_unicode=True))
    musicname = Column(Text(convert_unicode=True))
    arrangement = Column(Text(convert_unicode=True))
    location = Column(Text(convert_unicode=True))
    boxid = Column(Text(convert_unicode=True))
    catalogdetail = Column(Text(convert_unicode=True))
    notes = Column(Text(convert_unicode=True))
    link = Column(Text(convert_unicode=True))
    
    @property
    def serialize(self):
        return serialize_class(self, self.__class__)

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

#both group and grouptemplate tables and classes are initialized without the instrument columns
class group(Base):
    __tablename__ = 'groups'

    groupid = Column(Integer, primary_key=True, unique=True)
    groupname = Column(String)
    groupdescription = Column(String)
    locationid = Column(Integer, ForeignKey('locations.locationid', ondelete='SET NULL'))
    requesttime = Column(DateTime)
    requesteduserid = Column(UUID, ForeignKey('users.userid', ondelete='SET NULL'))
    periodid = Column(Integer, ForeignKey('periods.periodid', ondelete='CASCADE'))
    minimumlevel = Column(Integer, default='0')
    maximumlevel = Column(Integer, default='0')
    musicid = Column(Integer, ForeignKey('musics.musicid',ondelete='SET NULL'), nullable=True)
    musicwritein = Column(String)
    ismusical = Column(Integer, default='0')
    iseveryone = Column(Integer, default='0')
    status = Column(String)
    lastchecked = Column(DateTime, default=func.current_date())
    version = Column(Integer, default=0)
    log = Column(Text(convert_unicode=True))

    @property
    def serialize(self):
        return serialize_class(self, self.__class__)

    #returns the total number of players that are needed for this group
    @property
    def totalinstrumentation(self):
        total = 0
        for i in getconfig('Instruments').split(","):
            total = total + int(getattr(self,i))
        return int(total)

    #returns a total number of players currently assigned to this group
    @property
    def totalallocatedplayers(self):
        s = Session()
        total = s.query(groupassignment).filter(groupassignment.groupid == self.groupid).count()
        s.close()
        return total

    #returns an array of instrument names that are contained in this group
    @property
    def instruments(self):
        instrumentation = []
        for i in getconfig('Instruments').split(","):
            if getattr(self,i) > 0:
                instrumentation.append(i)
        return instrumentation

    def addtolog(self,text):
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M') #get the time now and convert it to a string format
        if self.log is None or self.log == '':
            self.log = now + ';' + text
        else:
            self.log = self.log + ',' + now + ';' + text

    def getAverageLevel(self,session):
        debuglog('GETAVERAGELEVEL: Getting average level of group %s' % (self.groupid))
        levelob = session.query(
            func.avg(instrument.level
            ).label('averageLevel')
            ).join(user, user.userid == instrument.userid
            ).join(
                groupassignment,
                and_(
                    groupassignment.instrumentname == instrument.instrumentname,
                    user.userid == groupassignment.userid)
            ).filter(groupassignment.groupid == self.groupid).first()
        debuglog('GETAVERAGELEVEL: Found average level of group %s to be %s' % (self.groupid,levelob.averageLevel))
        return levelob.averageLevel

    #this function obtains the minimum level that players will be filled automatically into a group, depending on if it's explicitly set, or has players already assigned
    def getminlevel(self,session):
        debuglog('GETMINLEVEL: finding minimum level of group %s' % (self.groupid))
        #if the group is set to "auto", i.e. blank or 0, find the minimum level of all the players currently playing in the group
        if self.minimumlevel is None or self.minimumlevel == '' or self.minimumlevel == '0' or self.minimumlevel == 0:
            averageLevel = self.getAverageLevel(session)
            #if we find at least one player in this group, set the minimumlevel to be the average level rounded down
            if averageLevel is not None:
                # if the average level equals the maximum level possible, it is full of people of maximum level. Set the minimum auto assignment level to be the maximum
                if float(averageLevel) == float(getconfig('MaximumLevel')):
                    level = int(getconfig('MaximumLevel'))
                else:
                    # the minimum level will be the average level rounded down
                    level = int(math.ceil(averageLevel)) - 1
                    if level < 1:
                        level = 1
            #if we don't find a player in this group, set the minimum level to be 0 (not allowed to autofill)
            else: 
                level = 0
        #if this group's minimum level is explicitly set, use that setting
        else:
            level = self.minimumlevel
        debuglog('GETMINLEVEL: Found minimum level of group %s to be %s' % (self.groupid,level))
        return int(level)

    #this function obtains the max level, depending on if it's explicitly set, or has players already assigned
    def getmaxlevel(self,session):
        debuglog('GETMAXLEVEL: finding maximum level of group %s' % (self.groupid))
        #if the group is set to "auto", i.e. blank or 0, find the minimum level of all the players currently playing in the group
        if self.maximumlevel is None or self.maximumlevel == '' or self.maximumlevel == '0' or self.maximumlevel == 0:
            averageLevel = self.getAverageLevel(session)
            #if we find at least one player in this group, set the minimumlevel to be the average level, rounded up
            if averageLevel is not None:
                # the minimum level will be the average level rounded up
                level = int(math.ceil(averageLevel))
                if level < 1:
                    level = 1
            #if we don't find a player in this group, set the minimum level to be 0 (not allowed to autofill)
            else: 
                level = 0
        #if this group's minimum level is explicitly set, use that setting
        else:
            level = self.maximumlevel
        debuglog('GETMAXLEVEL: Found maximum level of group %s to be %s' % (self.groupid,level))
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
        elif self.periodid is None:
            raise Exception('Failed to confirm group %s becasue the group is missing a periodid' % self.groupname)
        elif self.groupname is None or self.groupname == '':
            raise Exception('Failed to confirm group becasue the group is missing a groupname')
        elif session.query(group).filter(group.periodid == self.periodid, group.locationid == self.locationid, group.groupid != self.groupid).first() is not None:
            raise Exception('Failed to confirm group %s becasue the group location is already in use by another group at this time' % self.groupname)
        elif self.musicid is not None and session.query(group).filter(group.musicid == self.musicid, group.periodid == self.periodid, group.groupid != self.groupid).first() is not None:
            raise Exception('Failed to confirm group %s because the group music is already in use by another group at this time' % self.groupname)

        #check if any players are playing in other groups
        if self.checkplayerclash:
            raise Exception('Failed to confirm group becasue at least one player is in another group at this time.')
        else:
            log('CONFIRMGROUP: Successfully confirmed group name:%s id:%s' % (self.groupname,self.groupid))
            self.status = 'Confirmed'
            
    #adds a single player to this group. The object passed in needs to have at least a userid
    def addplayer(self,session,player,instrumentname):
        #check if this user plays this instrument
        if session.query(instrument).filter(instrument.userid == player.userid, instrument.instrumentname == instrumentname).first() is None:
            log('ADDPLAYER: Found that player %s %s does not play instrument %s, cannot assign them to group %s' % (player.firstname,player.lastname,instrumentname,self.groupid))
            raise Exception('Found that player %s %s does not play instrument %s, cannot assign them to group %s' % (player.firstname,player.lastname,instrumentname,self.groupid))
        #if the player is already in this group, don't make another groupassignment, just log it.
        if session.query(groupassignment).filter(groupassignment.userid == player.userid, groupassignment.groupid == self.groupid).first() is not None:
            log('ADDPLAYER: Found that player %s %s is already in this group. Made no changes to this player.' % (player.firstname,player.lastname))
        #if the player is in another group at this time, raise an exception
        elif self.periodid is not None and session.query(groupassignment).join(group).filter(groupassignment.userid == player.userid, group.periodid == self.periodid).first() is not None:
            log('ADDPLAYER: Found that player %s %s is already assigned to a group during this period.' % (player.firstname,player.lastname))
            raise Exception('Found that player %s %s is already assigned to a group during this period.' % (player.firstname,player.lastname))
        #otherwise, create a groupassignment for them
        else:
            log('ADDPLAYER: Adding player %s %s to group playing instrument %s' % (player.firstname,player.lastname,instrumentname))
            playergroupassignment = groupassignment(userid = player.userid, groupid = self.groupid, instrumentname = instrumentname)
            session.add(playergroupassignment)

    #checks if this group can fit into a given period or not (checks player clashes with other groups)
    def checkplayerclash(self,session,selectedperiod):
        playersPlayingInPeriod = session.query(groupassignment.userid).join(group).filter(group.groupid != self.groupid).filter(group.periodid == selectedperiod.periodid)
        if session.query(groupassignment.userid).filter(groupassignment.groupid == self.groupid, groupassignment.userid.in_(playersPlayingInPeriod)).first() is not None:
            log('CHECKPLAYERCLASH: Found a player clash for group with id:%s and period id:%s' % (self.groupid,selectedperiod.periodid))
            return True
        else:
            log('CHECKPLAYERCLASH: Found that group id:%s can fit into period id:%s' % (self.groupid,selectedperiod.periodid))
            return False

    #adds a list of players to this group. The list must contain at least userids. Does not commit the group.
    def addplayers(self,session,playerlist):
        try:
            log('ADDPLAYERS: Adding a list of players to group name:%s id:%s' % (self.groupname, self.groupid))
            for player in playerlist:
                self.addplayer(session,player,player.instrumentname)
            log('ADDPLAYERS: Finished adding players to group')
        except Exception as ex:
            raise Exception(ex)

    def purgeoldplayers(self,session):
        log('GROUPPURGE: Purging old players from group name:%s id:%s' % (self.groupname,self.groupid))
        oldplayers = session.query(groupassignment
                        ).join(user
                        ).filter(
                            groupassignment.groupid == self.groupid,
                            or_(
                            user.departure < datetime.datetime.now(),
                            user.isactive != 1
                            )
                        ).all()
        for p in oldplayers:
            session.delete(p)
        return False

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

class grouptemplate(Base):
    __tablename__ = 'grouptemplates'

    grouptemplateid = Column(Integer, primary_key=True, unique=True)
    grouptemplatename = Column(String)
    size = Column(String)
    minimumlevel = Column(Integer)
    maximumlevel = Column(Integer)
    defaultlocationid = Column(Integer, ForeignKey('locations.locationid', ondelete='SET NULL'))

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

class instrument(Base):
    __tablename__ = 'instruments'

    instrumentid = Column(Integer, primary_key=True, unique=True)
    userid = Column(UUID, ForeignKey('users.userid', ondelete='CASCADE'))
    instrumentname = Column(String)
    level = Column(Integer)
    isprimary = Column(Integer)
    isactive = Column(Integer)

    @property
    def serialize(self):
        return serialize_class(self, self.__class__)

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

class groupassignment(Base):
    __tablename__ = 'groupassignments'

    groupassignmentid = Column(Integer, primary_key=True, unique=True)
    userid = Column(UUID, ForeignKey('users.userid', ondelete='CASCADE'))
    groupid = Column(Integer, ForeignKey('groups.groupid', ondelete='CASCADE'))
    instrumentname = Column(String)

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

class location(Base):
    __tablename__ = 'locations'

    locationid = Column(Integer, primary_key=True, unique=True)
    locationname = Column(String)
    capacity = Column(Integer, default='0')
    autoallocate = Column(Integer, default='1')

    @property
    def serialize(self):
        return serialize_class(self, self.__class__)

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

    def getmealstats(self, session, getNumbers = False):
        if (self.meal != 1):
            return null
        else:
            mealstats = {
                'name':self.periodname,
                'periodid': self.periodid,
                'starttime':self.starttime,
                'endtime':self.endtime,
            }
            absentusers_subquery = session.query(user.userid
                ).join(groupassignment
                ).join(group
                ).filter(
                    group.groupname == 'absent',
                    group.periodid == self.periodid
                    )
            #find the users that are present and not marked absent
            if getNumbers:
                mealstats['totals'] = {
                    'byDietaryRequirement': session.query(
                            user.agecategory,
                            user.dietaryrequirements,
                            func.count(user.agecategory + user.dietaryrequirements).label("count")
                        ).filter(
                            user.arrival <= self.starttime, 
                            user.departure >= self.starttime, 
                            user.isactive == 1,
                            ~user.userid.in_(absentusers_subquery)
                        ).group_by(user.agecategory, user.dietaryrequirements
                        ).order_by(user.agecategory, user.dietaryrequirements
                        ).all(),
                    'byAgeCategory': session.query(
                            user.agecategory,
                            func.count(user.agecategory).label("count")
                        ).filter(
                            user.arrival <= self.starttime, 
                            user.departure >= self.starttime, 
                            user.isactive == 1,
                            ~user.userid.in_(absentusers_subquery)
                        ).group_by(user.agecategory
                        ).order_by(user.agecategory
                        ).all()
                }
                mealstats['total'] = 0
                for category in mealstats['totals']['byAgeCategory']:
                    mealstats['total'] = int(mealstats['total']) + int(category.count)
            return mealstats

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

#add the columns for each instrument in the application configuration to the group, grouptemplate, music and location tables
instrumentlist = getconfig('Instruments').split(",")
log('Setting up columns for instruments in database: %s' % getconfig('Instruments'))
for i in instrumentlist:
    setattr(group, i, Column(Integer, default='0'))
    setattr(grouptemplate, i, Column(Integer, default='0'))
    setattr(music, i, Column(Integer, default='0'))
    setattr(location, i, Column(Integer, default='1'))

log('Synchronising database schema...')
try:
    Base.metadata.create_all(engine)
    log('Sucessfully synchronised database schema')
except Exception as ex:
        log('Failed to synchronise database schema with exception: %s.' % ex)

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
    try:
        log('Initiating initial database build from config file')
        conf = untangle.parse(configfile)
        #Grab the camp start and end times from the config file
        CampStartTime = datetime.datetime.strptime(getconfig('StartTime'), '%Y-%m-%d %H:%M')
        CampEndTime = datetime.datetime.strptime(getconfig('EndTime'), '%Y-%m-%d %H:%M')
        #Prepare for the loop, which will go through each day of camp and create an instance of each day's period
        ThisDay = datetime.datetime.strptime(datetime.datetime.strftime(CampStartTime, '%Y-%m-%d'), '%Y-%m-%d')
        #start our session, then go through the loop
        session = Session()
        loop = 'start'
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
                if conf.root.CampDetails.Location[x]['DisabledInstruments'] is not None:
                    for i in conf.root.CampDetails.Location[x]['DisabledInstruments'].split(','):
                        setattr(newlocation,i,0)
                session.add(newlocation)
        session.commit()
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
        #create group templates
        session.commit()
        for x in range(0,len(conf.root.CampDetails.GroupTemplate)):
            find_template = session.query(grouptemplate).filter(grouptemplate.grouptemplatename == conf.root.CampDetails.GroupTemplate[x]['Name']).first()
            if find_template is None:
                template = grouptemplate()
                attributelist = [a for a in dir(template) if not a.startswith('_') and not callable(getattr(template,a)) and not a == 'grouptemplateid' and not a == 'metadata' and not a == 'serialize']
                for v in attributelist:
                    if conf.root.CampDetails.GroupTemplate[x]['%s' % v] is not None:
                        setattr(template, v, conf.root.CampDetails.GroupTemplate[x]['%s' % v])
                    else:
                        setattr(template, v, 0)
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
                session.commit()
                log('Created grouptemplate: %s with size %s' % (template.grouptemplatename, template.size))
        session.commit()
        session.close()
        log('Finished database build')
        return 'Success'
    
    except Exception as ex:
        session.rollback()
        session.close()
        return ('Failed to import with exception: %s.' % ex)

def importusers(file):
    try:
        session = Session()
        CampStartTime = datetime.datetime.strptime(getconfig('StartTime'), '%Y-%m-%d %H:%M')
        CampEndTime = datetime.datetime.strptime(getconfig('EndTime'), '%Y-%m-%d %H:%M')
        #the below reads the camp input file and creates the users and instrument bindings it finds there.
        #ifile  = open(file, "rb")
        reader = csv.reader(file, delimiter=',')
        rownum = 0
        for row in reader:
            # if this isn't the header row, extract the data
            if rownum != 0:
                thisuser = user()
                thisuser.userid = str(uuid.uuid4())
                thisuser.logonid = str(uuid.uuid4())
                thisuser.isactive = 1
                thisuser.grouprequestcount = 0
                thisuser.firstname = row[0]
                thisuser.lastname = row[1][:2] #[:2] means just get the first two letters
                if row[12] != '':
                    thisuser.isannouncer = row[12]
                if row[13] != '':
                    thisuser.isconductor = row[13]
                if row[14] != '':
                    thisuser.isadmin = row[14]
                if row[2] != '':
                    thisuser.arrival =  datetime.datetime.strptime(row[2], "%d/%m/%Y %H:%M")
                if row[2] == '':
                    thisuser.arrival = CampStartTime
                if row[3] != '':
                    thisuser.departure =  datetime.datetime.strptime(row[3], "%d/%m/%Y %H:%M")
                if row[3] == '':
                    thisuser.departure = CampEndTime
                if row[15] != '':
                    thisuser.email = row[15]
                if row[16] != '':
                    thisuser.agecategory = row[16]
                if row[17] != '':
                    thisuser.dietaryrequirements = row[17]
                session.add(thisuser)
                log('Created user: %s %s' % (thisuser.firstname, thisuser.lastname))
                session.commit()
                if row[4] != '':
                    instrument1 = instrument(userid = thisuser.userid, instrumentname = row[4].capitalize().replace(" ", ""), level = row[5], isprimary = 1, isactive = 1)
                    session.add(instrument1)
                    log('Created instrument listing: %s at level %s for %s' % (instrument1.instrumentname, instrument1.level, thisuser.firstname))
                if row[6] != '':
                    instrument2 = instrument(userid = thisuser.userid, instrumentname = row[6].capitalize().replace(" ", ""), level = row[7], isprimary = 0, isactive = 1)
                    session.add(instrument2)
                    log('Created instrument listing: %s at level %s for %s' % (instrument2.instrumentname, instrument2.level, thisuser.firstname))
                if row[8] != '':
                    instrument3 = instrument(userid = thisuser.userid, instrumentname = row[8].capitalize().replace(" ", ""), level = row[9], isprimary = 0, isactive = 1)
                    session.add(instrument3)
                    log('Created instrument listing: %s at level %s for %s' % (instrument3.instrumentname, instrument3.level, thisuser.firstname))
                if row[10] != '':
                    instrument4 = instrument(userid = thisuser.userid, instrumentname = row[10].capitalize().replace(" ", ""), level = row[11], isprimary = 0, isactive = 1)
                    session.add(instrument4)
                    log('Created instrument listing: %s at level %s for %s' % (instrument4.instrumentname, instrument4.level, thisuser.firstname))
            rownum += 1
        session.commit()
        session.close()
        return ('Success')
    except Exception as ex:
        session.rollback()
        session.close()
        log('IMPORTUSERS: Failed to import with exception: %s.' % ex)
        return ('Failed to import with exception: %s.' % ex)

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