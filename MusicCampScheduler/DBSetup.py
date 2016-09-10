#VERY UNFINISHED
#his file contains fuctions to initiate empty databases needed for the rest of the app
import sqlalchemy
import untangle
import time
import datetime
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, exists, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, aliased
from debug import *
config = untangle.parse('config.xml')

#sets up debugging
debug = config.root.Application['Debug']
def log1(string):
    if debug >= 1:
        print(string)
def log2(string):
    if debug >= 2:
        print(string)
print('Debug level set to %s' % debug)

if config.root.Application['Debug'] >= 3:
    sqldebug=True
else:
    sqldebug=False
log2('sqlalchemy version: %s' % sqlalchemy.__version__)
Session = sessionmaker()
engine = create_engine("sqlite:///" + config.root.Application['DBPath'])#, echo=sqldebug)
Session.configure(bind=engine)
Base = declarative_base()
"""
class instrumentlist(Enum):
    Conductor = "Conductor"
    Flute = "Flute"
    Oboe = "Oboe"
    Clarinet = "Clarinet"
    Bassoon = "Bassoon"
    Horn = "Horn"
    Trumpet = "Trumpet"
    Trombone = "Trombone"
    Tuba = "Tuba"
    Percussion = "Percussion"
    Violin = "Violin"
    Viola = "Viola"
    Cello = "Cello"
    DoubleBass = "DoubleBass"
"""
class user(Base):
    __tablename__ = 'users'

    userid = Column(Integer, primary_key=True)
    firstname = Column(String)
    lastname = Column(String)
    age = Column(Integer)
    email = Column(String)
    isannouncer = Column(Integer)
    isconductor = Column(Integer)
    isadmin = Column(Integer)

    def __repr__(self):
        return "<User(name='%s', fullname='%s', password='%s')>" % (
            self.userid, self.firstname, self.lastname, self.age, self.email, self.announcer, self.conductor, self.admin)

class group(Base):
    __tablename__ = 'groups'

    groupid = Column(Integer, primary_key=True)
    groupname = Column(String)
    locationid = Column(Integer, ForeignKey('locations.locationid'))
    requesttime = Column(DateTime)
    requesteduserid = Column(Integer, ForeignKey('users.userid'))
    periodid = Column(Integer, ForeignKey('periods.periodid'))
    music = Column(String)
    ismusical = Column(Integer)
    iseveryone = Column(Integer)
    conductor = Column(Integer)
    flute = Column(Integer)
    oboe = Column(Integer)
    clarinet = Column(Integer)
    bassoon = Column(Integer)
    horn = Column(Integer)
    trumpet = Column(Integer)
    trombone = Column(Integer)
    tuba = Column(Integer)
    percussion = Column(Integer)
    violin = Column(Integer)
    viola = Column(Integer)
    cello = Column(Integer)
    doublebass = Column(Integer)

    def __repr__(self):
        return "<User(name='%s', fullname='%s', password='%s')>" % (
            self.groupid,self.groupname,self.locationid,self.requesttime,self.periodid,self.music,self.ismusical,
            self.iseveryone,self.conductor,self.flute,self.oboe,self.clarinet,self.bassoon,self.horn,self.trumpet,
            self.trombone,self.tuba,self.percussion,self.violin,self.viola,self.cello,self.doublebass)

class grouptemplate(Base):
    __tablename__ = 'grouptemplates'

    grouptemplateid = Column(Integer, primary_key=True)
    grouptemplatename = Column(String)
    conductor = Column(Integer)
    flute = Column(Integer)
    oboe = Column(Integer)
    clarinet = Column(Integer)
    bassoon = Column(Integer)
    horn = Column(Integer)
    trumpet = Column(Integer)
    trombone = Column(Integer)
    tuba = Column(Integer)
    percussion = Column(Integer)
    violin = Column(Integer)
    viola = Column(Integer)
    cello = Column(Integer)
    doublebass = Column(Integer)

    def __repr__(self):
        return "<User(name='%s', fullname='%s', password='%s')>" % (
            self.grouptemplateid,self.grouptemplatename,self.conductor,self.flute,self.oboe,self.clarinet,self.bassoon,
            self.horn,self.trumpet,self.trombone,self.tuba,self.percussion,self.violin,self.viola,self.cello,self.doublebass)


class groupassignment(Base):
    __tablename__ = 'groupassignments'

    groupassignmentid = Column(Integer, primary_key=True)
    userid = Column(Integer, ForeignKey('users.userid'))
    groupid = Column(Integer, ForeignKey('groups.groupid'))
    instrument = Column(Enum('conductor','flute','oboe','clarinet','bassoon','horn','trumpet','trombone','tuba','percussion','violin','viola','cello','doublebass','absent'), ForeignKey('instruments.instrumentname'))

    def __repr__(self):
        return "<User(name='%s', fullname='%s', password='%s')>" % (
            self.groupassignmentid,self.userid,self.groupid,self.instrument)

class instrument(Base):
    __tablename__ = 'instruments'

    instrumentid = Column(Integer, primary_key=True)
    userid = Column(Integer, ForeignKey('users.userid'))
    instrumentname = Column(Enum('conductor','flute','oboe','clarinet','bassoon','horn','trumpet','trombone','tuba','percussion','violin','viola','cello','doublebass','absent'))
    grade = Column(Integer)
    isprimary = Column(Integer)

    def __repr__(self):
        return "<User(name='%s', fullname='%s', password='%s')>" % (
            self.instrumentid,self.userid,self.instrumentname,self.grade,self.isprimary)

class location(Base):
    __tablename__ = 'locations'

    locationid = Column(Integer, primary_key=True)
    locationname = Column(String)
    capacity = Column(Integer)

    def __repr__(self):
        return "<User(name='%s', fullname='%s', password='%s')>" % (
            self.locationid,self.locationname,self.capacity)

class period(Base):
    __tablename__ = 'periods'

    periodid = Column(Integer, primary_key=True)
    starttime = Column(DateTime)
    endtime = Column(DateTime)
    periodname = Column(String)
    meal = Column(Integer)

    def __repr__(self):
        return "<User(name='%s', fullname='%s', password='%s')>" % (
            self.periodid,self.starttime,self.endtime,self.periodname)

#create all tables if needed
Base.metadata.create_all(engine)

if config.root.Application['DBBuildRequired'] == 'Yes':
    #Grab the camp start and end times from the config file
    CampStartTime = datetime.datetime.strptime(config.root.CampDetails['StartTime'], '%Y-%m-%d %H:%M')
    CampEndTime = datetime.datetime.strptime(config.root.CampDetails['EndTime'], '%Y-%m-%d %H:%M')
    #Prepare for the loop, which will go through each day of camp and create an instance of each day's period
    ThisDay = datetime.datetime.strptime(datetime.datetime.strftime(CampStartTime, '%Y-%m-%d'), '%Y-%m-%d')
    log2('first thisDay is %s' % ThisDay)
    #start our session, then go through the loop
    session = Session()
    loop = 'start'
    for x in xrange(0,len(config.root.CampDetails.Locations.Location)):
        find_location = session.query(location).filter(location.locationname == config.root.CampDetails.Locations.Location[x]['Name']).first()
        if find_location is None:
            find_location = location(locationname = config.root.CampDetails.Locations.Location[x]['Name'],capacity = config.root.CampDetails.Locations.Location[x]['Capacity'])
            session.add(find_location)
    meallocation = session.query(location).filter(location.locationname == config.root.CampDetails.Locations['MealLocation']).first()
    #For each day covered by the camp start and end time
    while loop == 'start':
        log2('now looping for %s' % ThisDay)
        #For each period covered by the camp's configured period list
        for x in xrange(0,len(config.root.CampDetails.Periods.Period)):
            ThisStartTime = datetime.datetime.strptime((datetime.datetime.strftime(ThisDay, '%Y-%m-%d') + ' ' + config.root.CampDetails.Periods.Period[x]['StartTime']),'%Y-%m-%d %H:%M')
            ThisEndTime = datetime.datetime.strptime((datetime.datetime.strftime(ThisDay, '%Y-%m-%d') + ' ' + config.root.CampDetails.Periods.Period[x]['EndTime']),'%Y-%m-%d %H:%M')
            ThisPeriodName = config.root.CampDetails.Periods.Period[x]['Name']
            ThisPeriodMeal = config.root.CampDetails.Periods.Period[x]['Meal']
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
                    find_mealgroup = group(groupname = find_period.periodname,periodid = find_period.periodid,iseveryone = 1,ismusical = 0,locationid = meallocation.locationid)
                    session.add(find_mealgroup)
                find_absent_group = session.query(group).filter(group.groupname == 'absent',group.periodid == find_period.periodid).first()
                #if no absentgroup exists in the database, create it
                if find_absent_group is None:
                    find_absent_group = group(groupname = 'absent',periodid = find_period.periodid,ismusical=0)
                    session.add(find_absent_group)
            #if we hit the camp's configured end time, then stop looping
            if ThisStartTime > CampEndTime:
                loop = 'stop'
        ThisDay = ThisDay + datetime.timedelta(days=1)    
    session.commit()
    session.close()
    log2('Finished Database Build!')