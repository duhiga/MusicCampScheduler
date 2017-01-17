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

#both group and grouptemplate tables and classes are initialized without the instrument columns
class group(Base):
    __tablename__ = 'groups'

    groupid = Column(Integer, primary_key=True, unique=True)
    groupname = Column(String)
    groupdescription = Column(String)
    locationid = Column(Integer, ForeignKey('locations.locationid'))
    requesttime = Column(DateTime)
    requesteduserid = Column(UUID, ForeignKey('users.userid'))
    periodid = Column(Integer, ForeignKey('periods.periodid'))
    minimumlevel = Column(Integer)
    maximumlevel = Column(Integer)
    musicid = Column(Integer, ForeignKey('musics.musicid',ondelete='SET NULL'), nullable=True)
    musicwritein = Column(String)
    ismusical = Column(Integer)
    iseveryone = Column(Integer)
    status = Column(String)
    log = Column(Text(convert_unicode=True))

    @property
    def serialize(self):
        return serialize_class(self, self.__class__)

    def addtolog(self,text):
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M') #get the time now and convert it to a string format
        if self.log is None or self.log == '':
            self.log = now + ';' + text
        else:
            self.log = self.log + ',' + now + ';' + text

class grouptemplate(Base):
    __tablename__ = 'grouptemplates'

    grouptemplateid = Column(Integer, primary_key=True, unique=True)
    grouptemplatename = Column(String)
    size = Column(String)
    minimumlevel = Column(Integer)
    maximumlevel = Column(Integer)
    defaultlocationid = Column(Integer, ForeignKey('locations.locationid'))

    @property
    def serialize(self):
        return serialize_class(self, self.__class__)

#add the columns for each instrument in the application configuration to the group and grouptemplates tables
instrumentlist = getconfig('Instruments').split(",")
print('Setting up columns for instruments in database: %s' % getconfig('Instruments'))
for i in instrumentlist:
    setattr(group, i, Column(Integer, default='0'))
    setattr(grouptemplate, i, Column(Integer, default='0'))
    setattr(music, i, Column(Integer, default='0'))

class instrument(Base):
    __tablename__ = 'instruments'

    instrumentid = Column(Integer, primary_key=True, unique=True)
    userid = Column(UUID, ForeignKey('users.userid'))
    instrumentname = Column(String)
    grade = Column(Integer)
    isprimary = Column(Integer)
    isactive = Column(Integer)

    @property
    def serialize(self):
        return serialize_class(self, self.__class__)

class groupassignment(Base):
    __tablename__ = 'groupassignments'

    groupassignmentid = Column(Integer, primary_key=True, unique=True)
    userid = Column(UUID, ForeignKey('users.userid'))
    groupid = Column(Integer, ForeignKey('groups.groupid'))
    instrumentname = Column(String)

    @property
    def serialize(self):
        return serialize_class(self, self.__class__)

class location(Base):
    __tablename__ = 'locations'

    locationid = Column(Integer, primary_key=True, unique=True)
    locationname = Column(String)
    capacity = Column(Integer)

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

class announcement(Base):
    __tablename__ = 'announcements'

    announcementid = Column(Integer, primary_key=True, unique=True)
    creationtime = Column(DateTime)
    content = Column(Text(convert_unicode=True))

Base.metadata.create_all(engine)

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
        print('Found Administrator user did not match AdminUUID parameter. Updating the user details to match.')
        findadmin.logonid = getconfig('AdminUUID')
        session.merge(findadmin)
    #if we don't find one, this is the first boot of the app. Create the administrator user.
    else:
        print('Welcome to the music camp scheduler! This is the first boot of the app. Look in your applicaiton parameters for the AdminUUID parameter, then log in to the setup page with websitename/user/AdminUUID(replace this with your admin UUID)/setup/')
        admin = user(logonid = getconfig('AdminUUID'), userid = str(uuid.uuid4()), firstname = 'Administrator', lastname = 'A', isactive = 0, \
            arrival = datetime.datetime.strptime(getconfig('StartTime'), '%Y-%m-%d %H:%M'), departure = datetime.datetime.strptime(getconfig('EndTime'), '%Y-%m-%d %H:%M'))
        session.add(admin)
    session.commit()
session.close()
session.flush()

def createlocation(session,name,capacity):
    find_location = session.query(location).filter(location.locationname == name).first()
    if find_location is None:
        find_location = location(locationname = name, capacity = capacity)
        session.add(find_location)
        print('Created location: %s' % find_location.locationname)
    else:
        print('Location %s already exists.' % find_location.locationname)

#Database Build section. The below configures periods and groups depending on how the config.xml is configured.
def dbbuild(configfile):
    try:
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
        createlocation(session,'None',0)
        for x in range(0,len(conf.root.CampDetails.Location)):
            createlocation(session,conf.root.CampDetails.Location[x]['Name'], conf.root.CampDetails.Location[x]['Capacity'])
        session.commit()
        #For each day covered by the camp start and end time
        while loop == 'start':
            print('Creating initial groups for %s' % ThisDay)
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
                        print('Created period: %s at %s with meal switch set to %s' % (find_period.periodname, find_period.starttime, find_period.meal))
                    #check if this period has public events that need to be created
                    for x in range(0,len(conf.root.CampDetails.PublicEvent)):
                        find_event = session.query(group).filter(group.groupname == conf.root.CampDetails.PublicEvent[x]['Name'],group.periodid == find_period.periodid,group.iseveryone == 1,group.ismusical == 0).first()
                        if find_event is None and find_period.periodname == conf.root.CampDetails.PublicEvent[x]['Period']:
                            print('right before locationname search')
                            find_location = session.query(location).filter(location.locationname == conf.root.CampDetails.PublicEvent[x]['Location']).first()
                            if find_location is None:
                                print('User input a location that does not exist when configuring event %s' % conf.root.CampDetails.PublicEvent[x]['Name'])
                            else:
                                find_event = group(groupname = conf.root.CampDetails.PublicEvent[x]['Name'],periodid = find_period.periodid,iseveryone = 1,ismusical = 0,locationid = find_location.locationid,status="Confirmed",requesttime=datetime.datetime.now())
                                if conf.root.CampDetails.PublicEvent[x]['Description'] is not None:
                                    find_event.groupdescription = conf.root.CampDetails.PublicEvent[x]['Description']
                                session.add(find_event)
                                print('Created public event: %s during period %s at %s' % (find_event.groupname, find_period.periodname, find_period.starttime))
                    #if no absentgroup exists in the database, create it
                    find_absent_group = session.query(group).filter(group.groupname == 'absent',group.periodid == find_period.periodid).first()
                    if find_absent_group is None:
                        find_absent_group = group(groupname = 'absent',periodid = find_period.periodid,ismusical=0,status="Confirmed",requesttime=datetime.datetime.now(),minimumlevel=0,maximumlevel=0)
                        session.add(find_absent_group)
                        print('Created group: placeholder for absentees at %s' % (find_period.starttime))
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
                    print('Found group default location for %s to be %s' % (template.grouptemplatename, defaultloc.locationname))
                    setattr(template, 'defaultlocationid', defaultloc.locationid)
                else:
                    noneloc = session.query(location).filter(location.locationname == 'None').first()
                    print('No default location set for template %s. Setting default location to be %s' % (template.grouptemplatename, noneloc.locationname))
                    setattr(template, 'defaultlocationid', noneloc.locationid)
                session.add(template)
                session.commit()
                print('Created grouptemplate: %s with size %s' % (template.grouptemplatename, template.size))
        session.commit()
        session.close()
        print('Finished database build')
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
        reader = csv.reader(file)
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
                print('Created user: %s %s' % (thisuser.firstname, thisuser.lastname))
                session.commit()
                if row[4] is not '':
                    instrument1 = instrument(userid = thisuser.userid, instrumentname = row[4].capitalize().replace(" ", ""), grade = row[5], isprimary = 1, isactive = 1)
                    session.add(instrument1)
                    print('Created instrument listing: %s at level %s for %s' % (instrument1.instrumentname, instrument1.grade, thisuser.firstname))
                if row[6] is not '':
                    instrument2 = instrument(userid = thisuser.userid, instrumentname = row[6].capitalize().replace(" ", ""), grade = row[7], isprimary = 0, isactive = 1)
                    session.add(instrument2)
                    print('Created instrument listing: %s at level %s for %s' % (instrument2.instrumentname, instrument2.grade, thisuser.firstname))
                if row[8] is not '':
                    instrument3 = instrument(userid = thisuser.userid, instrumentname = row[8].capitalize().replace(" ", ""), grade = row[9], isprimary = 0, isactive = 1)
                    session.add(instrument3)
                    print('Created instrument listing: %s at level %s for %s' % (instrument3.instrumentname, instrument3.grade, thisuser.firstname))
                if row[10] is not '':
                    instrument4 = instrument(userid = thisuser.userid, instrumentname = row[10].capitalize().replace(" ", ""), grade = row[11], isprimary = 0, isactive = 1)
                    session.add(instrument4)
                    print('Created instrument listing: %s at level %s for %s' % (instrument4.instrumentname, instrument4.grade, thisuser.firstname))
            rownum += 1
        session.commit()
        userscount = session.query(user).count()
        session.close()
        return ('Success')
    except Exception as ex:
        session.rollback()
        session.close()
        return ('Failed to import with exception: %s.' % ex)

def importmusic(file):
    try:
        session = Session()
        reader = csv.reader(file)
        headers = reader.next()
        print(headers)
        for row in reader:
            thismusic = music()
            for header in headers:
                if header in getconfig('Instruments').split(",") and row[headers.index(header)] == '':
                    setattr(thismusic,header,0)
                elif row[headers.index(header)] != '':
                    setattr(thismusic,header,row[headers.index(header)])
                matchingtemplate = session.query(grouptemplate).filter(*[getattr(thismusic,i) == getattr(grouptemplate,i) for i in instrumentlist]).first()
                if matchingtemplate is not None:
                    print('Found a template matching this music: %s' % matchingtemplate.grouptemplatename)
                    thismusic.grouptemplateid = matchingtemplate.grouptemplateid
            session.add(thismusic)
        session.commit()
        session.close()
        return ('Success')
    except Exception as ex:
        session.rollback()
        session.close()
        return ('Failed to import with exception: %s.' % ex)

