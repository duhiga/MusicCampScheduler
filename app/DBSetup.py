#This file contains initial setup for the database
import sqlalchemy
import untangle
import time
import datetime
import csv
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, exists, Enum, types, UniqueConstraint, ForeignKeyConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, aliased
from sqlalchemy.dialects.mysql.base import MSBinary
from sqlalchemy.schema import Column
import uuid
import os
from config import *

#sets up debugging
def log(string):
    print(string)

engine = create_engine(getconfig('DATABASE_URL'))
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

    userid = Column(String, primary_key=True, unique=True)
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

    groupid = Column(Integer, primary_key=True, unique=True)
    groupname = Column(String)
    locationid = Column(Integer, ForeignKey('locations.locationid'))
    requesttime = Column(DateTime)
    requesteduserid = Column(String, ForeignKey('users.userid'))
    periodid = Column(Integer, ForeignKey('periods.periodid'))
    minimumlevel = Column(Integer)
    maximumlevel = Column(Integer)
    music = Column(String)
    ismusical = Column(Integer)
    iseveryone = Column(Integer)
    status = Column(String)

    @property
    def serialize(self):
        return serialize_class(self, self.__class__)

class grouptemplate(Base):
    __tablename__ = 'grouptemplates'

    grouptemplateid = Column(Integer, primary_key=True, unique=True)
    grouptemplatename = Column(String)
    size = Column(String)
    minimumlevel = Column(Integer)
    maximumlevel = Column(Integer)

    @property
    def serialize(self):
        return serialize_class(self, self.__class__)

#add the columns for each instrument in the application configuration to the group and grouptemplates tables
instrumentlist = getconfig('Instruments').split(",")
for i in instrumentlist:
    log('Setting up columns for %s in database' % i)
    setattr(group, i, Column(Integer))
    setattr(grouptemplate, i, Column(Integer))

class instrument(Base):
    __tablename__ = 'instruments'

    instrumentid = Column(Integer, primary_key=True, unique=True)
    userid = Column(String, ForeignKey('users.userid'))
    instrumentname = Column(String)
    grade = Column(Integer)
    isprimary = Column(Integer)

    @property
    def serialize(self):
        return serialize_class(self, self.__class__)

    def __repr__(self):
        return "<instrument(instrumentid='%s', userid='%s', instrumentname='%s', grade='%s', isprimary='%s')>" % (
            self.instrumentid,self.userid,self.instrumentname,self.grade,self.isprimary)

class groupassignment(Base):
    __tablename__ = 'groupassignments'

    groupassignmentid = Column(Integer, primary_key=True, unique=True)
    userid = Column(String, ForeignKey('users.userid'))
    groupid = Column(Integer, ForeignKey('groups.groupid'))
    instrumentname = Column(String)
    #__table_args__ = (ForeignKeyConstraint([userid, instrumentname],[instrument.userid, instrument.instrumentname]), {})

    @property
    def serialize(self):
        return serialize_class(self, self.__class__)

    def __repr__(self):
        return "<groupassignment(groupassignmentid='%s', userid='%s', groupid='%s', instrument='%s')>" % (
            self.groupassignmentid,self.userid,self.groupid,self.instrumentname)

class location(Base):
    __tablename__ = 'locations'

    locationid = Column(Integer, primary_key=True, unique=True)
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

    periodid = Column(Integer, primary_key=True, unique=True)
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

    announcementid = Column(Integer, primary_key=True, unique=True)
    creationtime = Column(DateTime)
    content = Column(String)

Base.metadata.create_all(engine)

#Database Build section. The below configures periods and groups depending on how the config.xml is configured.
def dbbuild(configfile):
    conf = untangle.parse(configfile)
    #Grab the camp start and end times from the config file
    CampStartTime = datetime.datetime.strptime(getconfig('StartTime'), '%Y-%m-%d %H:%M')
    CampEndTime = datetime.datetime.strptime(getconfig('EndTime'), '%Y-%m-%d %H:%M')
    #Prepare for the loop, which will go through each day of camp and create an instance of each day's period
    ThisDay = datetime.datetime.strptime(datetime.datetime.strftime(CampStartTime, '%Y-%m-%d'), '%Y-%m-%d')
    log('first thisDay is %s' % ThisDay)
    #start our session, then go through the loop
    session = Session()
    loop = 'start'
    for x in range(0,len(conf.root.CampDetails.Location)):
        find_location = session.query(location).filter(location.locationname == conf.root.CampDetails.Location[x]['Name']).first()
        if find_location is None:
            find_location = location(locationname = conf.root.CampDetails.Location[x]['Name'],capacity = conf.root.CampDetails.Location[x]['Capacity'])
            session.add(find_location)
    meallocation = session.query(location).filter(location.locationname == conf.root.CampDetails['MealLocation']).first()
    #For each day covered by the camp start and end time
    while loop == 'start':
        log('now looping for %s' % ThisDay)
        #For each period covered by the camp's configured period list
        for x in range(0,len(conf.root.CampDetails.Period)):
            ThisStartTime = datetime.datetime.strptime((datetime.datetime.strftime(ThisDay, '%Y-%m-%d') + ' ' + conf.root.CampDetails.Period[x]['StartTime']),'%Y-%m-%d %H:%M')
            ThisEndTime = datetime.datetime.strptime((datetime.datetime.strftime(ThisDay, '%Y-%m-%d') + ' ' + conf.root.CampDetails.Period[x]['EndTime']),'%Y-%m-%d %H:%M')
            ThisPeriodName = conf.root.CampDetails.Period[x]['Name']
            ThisPeriodMeal = conf.root.CampDetails.Period[x]['Meal']
            find_period = session.query(period).filter(period.periodname == ThisPeriodName,period.starttime == ThisStartTime,period.endtime == ThisEndTime).first()
            #only create periods and groups if we are inside the specific camp start and end time
            if ThisStartTime < CampEndTime and ThisStartTime > CampStartTime:
                find_period = session.query(period).filter(period.periodname == ThisPeriodName,period.starttime == ThisStartTime,period.endtime == ThisEndTime).first()
                #if no period exists in the database, create it
                if find_period is None:
                    log('Period not found. Creating period instance with details ' + datetime.datetime.strftime(ThisStartTime, '%Y-%m-%d %H:%M') + datetime.datetime.strftime(ThisStartTime, '%Y-%m-%d %H:%M') + ThisPeriodName)
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
                    find_absent_group = group(groupname = 'absent',periodid = find_period.periodid,ismusical=0,status="Confirmed",requesttime=datetime.datetime.now(),minimumlevel=0,maximumlevel=0)
                    session.add(find_absent_group)
            #if we hit the camp's configured end time, then stop looping
            if ThisStartTime > CampEndTime:
                loop = 'stop'
        ThisDay = ThisDay + datetime.timedelta(days=1)    
    #create group templates
    for x in range(0,len(conf.root.CampDetails.GroupTemplate)):
        log(conf.root.CampDetails.GroupTemplate[x])
        find_template = session.query(grouptemplate).filter(grouptemplate.grouptemplatename == conf.root.CampDetails.GroupTemplate[x]['Name']).first()
        if find_template is None:
            template = grouptemplate()
            attributelist = [a for a in dir(template) if not a.startswith('_') and not callable(getattr(template,a)) and not a == 'grouptemplateid' and not a == 'metadata' and not a == 'serialize']
            log('attributelist is:')
            log(attributelist)
            for v in attributelist:
                log('Attempting to change template property %s to %s' % (v, conf.root.CampDetails.GroupTemplate[x]['%s' % v]))
                setattr(template, v, conf.root.CampDetails.GroupTemplate[x]['%s' % v])
            setattr(template, 'grouptemplatename', conf.root.CampDetails.GroupTemplate[x]['Name'])
            setattr(template, 'size', conf.root.CampDetails.GroupTemplate[x]['Size'])
            setattr(template, 'minimumlevel', conf.root.CampDetails.GroupTemplate[x]['MinimumLevel'])
            session.add(template)
    session.commit()
    session.close()
    log('Finished Database Build!')
    return 'Database Build Successful'

def importusers(file):
    session = Session()
    CampStartTime = datetime.datetime.strptime(getconfig('StartTime'), '%Y-%m-%d %H:%M')
    CampEndTime = datetime.datetime.strptime(getconfig('EndTime'), '%Y-%m-%d %H:%M')
    #the below reads the camp input file and creates the users and instrument bindings it finds there.
    #ifile  = open(file, "rb")
    reader = csv.reader(file)
    rownum = 0
    for row in reader:
        log('If youre seeing this, its looped again')
        # Save header row.
        if rownum == 0:
            header = row
            log('Now in the header row')
        else:
            log(row)
            thisuser = user()
            thisuser.userid = str(uuid.uuid4())
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
            session.add(thisuser)
            session.commit()
            if row[4] is not 'Non-Player':
                instrument1 = instrument(userid = thisuser.userid, instrumentname = row[4].capitalize().replace(" ", ""), grade = row[5], isprimary = 1)
                session.add(instrument1)
            if row[6] is not '':
                instrument2 = instrument(userid = thisuser.userid, instrumentname = row[6].capitalize().replace(" ", ""), grade = row[7], isprimary = 0)
                session.add(instrument2)
            if row[8] is not '':
                instrument3 = instrument(userid = thisuser.userid, instrumentname = row[8].capitalize().replace(" ", ""), grade = row[9], isprimary = 0)
                session.add(instrument3)
            if row[10] is not '':
                instrument4 = instrument(userid = thisuser.userid, instrumentname = row[10].capitalize().replace(" ", ""), grade = row[11], isprimary = 0)
                session.add(instrument4)
            log('Created user named %s %s' % (thisuser.firstname, thisuser.lastname))
        rownum += 1
    session.commit()
    userscount = session.query(user).count()
    session.close()
    return ('Created users. There are now %s total users in the database.' % userscount)