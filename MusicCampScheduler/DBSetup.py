#This file contains initial setup for the database
import sqlalchemy
import untangle
import time
import datetime
import csv
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, exists, Enum, types
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, aliased
from sqlalchemy.dialects.mysql.base import MSBinary
from sqlalchemy.schema import Column
from debug import *
import uuid
config = untangle.parse('config.xml')

#sets up debugging
debug = int(config.root.Application['Debug'])
def log1(string):
    if debug >= 1:
        print(string)
def log2(string):
    if debug >= 2:
        print(string)
print('Debug level set to %s' % debug)

if debug >= 3:
    engine = create_engine("sqlite:///" + config.root.Application['DBPath'], echo=True)
else:
    engine = create_engine("sqlite:///" + config.root.Application['DBPath'])
log2('sqlalchemy version: %s' % sqlalchemy.__version__)
Session = sessionmaker()
Session.configure(bind=engine)
Base = declarative_base()

def serialize_class(inst, cls):
    convert = dict()
    # add your coversions for things like datetime's 
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

    userid = Column(String, primary_key=True)
    firstname = Column(String)
    lastname = Column(String)
    arrival = Column(DateTime)
    departure = Column(DateTime)
    grouprequestcount = Column(Integer)
    isannouncer = Column(Integer)
    isconductor = Column(Integer)
    isadmin = Column(Integer)

    @property
    def serialize(self):
        return serialize_class(self, self.__class__)

    def __repr__(self):
        return "<user(userid='%s', firstname='%s', lastname='%s', age='%s', arrival='%s', departure='%s', isannouncer='%s', isconductor='%s', isadmin='%s')>" % (
            self.userid, self.firstname, self.lastname, self.age, self.arrival, self, departure, self.isannouncer, self.isconductor, self.isadmin)

#both group and grouptemplate tables and classes are initialized without the instrument columns
class group(Base):
    __tablename__ = 'groups'

    groupid = Column(Integer, primary_key=True)
    groupname = Column(String)
    locationid = Column(Integer, ForeignKey('locations.locationid'))
    requesttime = Column(DateTime)
    requesteduserid = Column(String, ForeignKey('users.userid'))
    periodid = Column(Integer, ForeignKey('periods.periodid'))
    minimumlevel = Column(Integer)
    music = Column(String)
    ismusical = Column(Integer)
    iseveryone = Column(Integer)
    status = Column(String)

    @property
    def serialize(self):
        return serialize_class(self, self.__class__)

class grouptemplate(Base):
    __tablename__ = 'grouptemplates'

    grouptemplateid = Column(Integer, primary_key=True)
    grouptemplatename = Column(String)
    size = Column(String)

    @property
    def serialize(self):
        return serialize_class(self, self.__class__)

#add columns to group and grouptemplate classes for each intsrument in the config file
instrumentlist = config.root.CampDetails['Instruments'].split(",")
for i in instrumentlist:
    log2('Setting up columns for %s in database' % i)
    setattr(group, i, Column(Integer))
    setattr(grouptemplate, i, Column(Integer))

class groupassignment(Base):
    __tablename__ = 'groupassignments'

    groupassignmentid = Column(Integer, primary_key=True)
    userid = Column(Integer, ForeignKey('users.userid'))
    groupid = Column(Integer, ForeignKey('groups.groupid'))
    instrument = Column(String, ForeignKey('instruments.instrumentname'))

    @property
    def serialize(self):
        return serialize_class(self, self.__class__)

    def __repr__(self):
        return "<groupassignment(groupassignmentid='%s', userid='%s', groupid='%s', instrument='%s')>" % (
            self.groupassignmentid,self.userid,self.groupid,self.instrument)

class instrument(Base):
    __tablename__ = 'instruments'

    instrumentid = Column(Integer, primary_key=True)
    userid = Column(Integer, ForeignKey('users.userid'))
    instrumentname = Column(String)
    grade = Column(Integer)
    isprimary = Column(Integer)

    @property
    def serialize(self):
        return serialize_class(self, self.__class__)

    def __repr__(self):
        return "<instrument(instrumentid='%s', userid='%s', instrumentname='%s', grade='%s', isprimary='%s')>" % (
            self.instrumentid,self.userid,self.instrumentname,self.grade,self.isprimary)

class location(Base):
    __tablename__ = 'locations'

    locationid = Column(Integer, primary_key=True)
    locationname = Column(String)
    capacity = Column(Integer)

    @property
    def serialize(self):
        return serialize_class(self, self.__class__)

    def __repr__(self):
        return "<location(locationid='%s', locationname='%s', capacity='%s')>" % (
            self.locationid,self.locationname,self.capacity)

class period(Base):
    __tablename__ = 'periods'

    periodid = Column(Integer, primary_key=True)
    starttime = Column(DateTime)
    endtime = Column(DateTime)
    periodname = Column(String)
    meal = Column(Integer)

    @property
    def serialize(self):
        return serialize_class(self, self.__class__)

    def __repr__(self):
        return "<period(periodid='%s', starttime='%s', endtime='%s', periodname='%s', meal='%s')>" % (
            self.periodid,self.starttime,self.endtime,self.periodname,self.meal)

class announcement(Base):
    __tablename__ = 'announcements'

    announcementid = Column(Integer, primary_key=True)
    creationtime = Column(DateTime)
    content = Column(String)

#create all tables if needed
Base.metadata.create_all(engine)

#Database Build section. The below configures periods and groups depending on how the config.xml is configured.
if config.root.Application['DBBuildRequired'] == 'Y':
    
    #Grab the camp start and end times from the config file
    CampStartTime = datetime.datetime.strptime(config.root.CampDetails['StartTime'], '%Y-%m-%d %H:%M')
    CampEndTime = datetime.datetime.strptime(config.root.CampDetails['EndTime'], '%Y-%m-%d %H:%M')
    #Prepare for the loop, which will go through each day of camp and create an instance of each day's period
    ThisDay = datetime.datetime.strptime(datetime.datetime.strftime(CampStartTime, '%Y-%m-%d'), '%Y-%m-%d')
    log2('first thisDay is %s' % ThisDay)
    #start our session, then go through the loop
    session = Session()
    loop = 'start'
    for x in range(0,len(config.root.CampDetails.Location)):
        find_location = session.query(location).filter(location.locationname == config.root.CampDetails.Location[x]['Name']).first()
        if find_location is None:
            find_location = location(locationname = config.root.CampDetails.Location[x]['Name'],capacity = config.root.CampDetails.Location[x]['Capacity'])
            session.add(find_location)
    meallocation = session.query(location).filter(location.locationname == config.root.CampDetails['MealLocation']).first()
    #For each day covered by the camp start and end time
    while loop == 'start':
        log2('now looping for %s' % ThisDay)
        #For each period covered by the camp's configured period list
        for x in range(0,len(config.root.CampDetails.Period)):
            ThisStartTime = datetime.datetime.strptime((datetime.datetime.strftime(ThisDay, '%Y-%m-%d') + ' ' + config.root.CampDetails.Period[x]['StartTime']),'%Y-%m-%d %H:%M')
            ThisEndTime = datetime.datetime.strptime((datetime.datetime.strftime(ThisDay, '%Y-%m-%d') + ' ' + config.root.CampDetails.Period[x]['EndTime']),'%Y-%m-%d %H:%M')
            ThisPeriodName = config.root.CampDetails.Period[x]['Name']
            ThisPeriodMeal = config.root.CampDetails.Period[x]['Meal']
            find_period = session.query(period).filter(period.periodname == ThisPeriodName,period.starttime == ThisStartTime,period.endtime == ThisEndTime).first()
            #only create periods and groups if we are inside the specific camp start and end time
            if ThisStartTime < CampEndTime and ThisStartTime > CampStartTime:
                find_period = session.query(period).filter(period.periodname == ThisPeriodName,period.starttime == ThisStartTime,period.endtime == ThisEndTime).first()
                #if no period exists in the database, create it
                if find_period is None:
                    log2('Period not found. Creating period instance with details ' + datetime.datetime.strftime(ThisStartTime, '%Y-%m-%d %H:%M') + datetime.datetime.strftime(ThisStartTime, '%Y-%m-%d %H:%M') + ThisPeriodName)
                    find_period = period(periodname = ThisPeriodName,starttime = ThisStartTime,endtime = ThisEndTime,meal=ThisPeriodMeal)
                    session.add(find_period)
                find_mealgroup = session.query(group).filter(group.groupname == find_period.periodname,group.periodid == find_period.periodid,group.iseveryone == 1,group.ismusical == 0).first()
                #if no mealgroup exists in the database, create it
                if find_mealgroup is None and find_period.meal == 1:
                    find_mealgroup = group(groupname = find_period.periodname,periodid = find_period.periodid,iseveryone = 1,ismusical = 0,locationid = meallocation.locationid,status="Confirmed",requesttime=datetime.datetime.now(),requesteduserid='system')
                    session.add(find_mealgroup)
                find_absent_group = session.query(group).filter(group.groupname == 'absent',group.periodid == find_period.periodid).first()
                #if no absentgroup exists in the database, create it
                if find_absent_group is None:
                    find_absent_group = group(groupname = 'absent',periodid = find_period.periodid,ismusical=0,status="Confirmed",requesttime=datetime.datetime.now(),requesteduserid='system')
                    session.add(find_absent_group)
            #if we hit the camp's configured end time, then stop looping
            if ThisStartTime > CampEndTime:
                loop = 'stop'
        ThisDay = ThisDay + datetime.timedelta(days=1)    
    #create group templates
    for x in range(0,len(config.root.CampDetails.GroupTemplate)):
        log2(config.root.CampDetails.GroupTemplate[x])
        find_template = session.query(grouptemplate).filter(grouptemplate.grouptemplatename == config.root.CampDetails.GroupTemplate[x]['Name']).first()
        if find_template is None:
            template = grouptemplate()
            attributelist = [a for a in dir(template) if not a.startswith('_') and not callable(getattr(template,a)) and not a == 'grouptemplateid' and not a == 'metadata' and not a == 'serialize']
            log2('attributelist is:')
            log2(attributelist)
            for v in attributelist:
                log2('Attempting to change template property %s to %s' % (v, config.root.CampDetails.GroupTemplate[x]['%s' % v]))
                setattr(template, v, config.root.CampDetails.GroupTemplate[x]['%s' % v])
            setattr(template, 'grouptemplatename', config.root.CampDetails.GroupTemplate[x]['Name'])
            setattr(template, 'size', config.root.CampDetails.GroupTemplate[x]['Size'])
            session.add(template)

    session.commit()
    session.close()
    log2('Finished Database Build!')