#VERY UNFINISHED
#his file contains fuctions to initiate empty databases needed for the rest of the app
import sqlalchemy
import untangle
import time
import datetime
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import sessionmaker, relationship
from debug import *
config = untangle.parse('config.xml')
if obj.root.debug['level'] >= 2:
        debug=True
Session = sessionmaker()
engine = create_engine('sqlite:///MusicCampDatabase.db', echo=debug)
Session.configure(bind=engine)
Base = declarative_base()

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
    locationid = Column(Integer, ForeignKey=('locations.locationid'))
    requesttime = Column(DateTime)
    periodid = Column(Integer, ForeignKey=('period.periodid'))
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
    userid = Column(Integer, ForeignKey=('users.userid'))
    groupid = Column(Integer, ForeignKey=('groups.groupid'))
    instrument = Column(String)

    def __repr__(self):
        return "<User(name='%s', fullname='%s', password='%s')>" % (
            self.groupassignmentid,self.userid,self.groupid,self.instrument)

class instrument(Base):
    __tablename__ = 'instruments'

    instrumentid = Column(Integer, primary_key=True)
    instrumentname = Column(String)
    userid = Column(Integer, ForeignKey=('users.userid'))
    isprimary = Column(Integer)

    def __repr__(self):
        return "<User(name='%s', fullname='%s', password='%s')>" % (
            self.instrumentid,self.instrumentname,self.userid,self.isprimary)

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

    def __repr__(self):
        return "<User(name='%s', fullname='%s', password='%s')>" % (
            self.periodid,self.starttime,self.endtime,self.periodname)

#create all tables if needed
Base.metadata.create_all(engine)

#Grab the camp start and end times from the config file
CampStartTime = datetime.datetime.strptime(config.root.CampDetails['StartTime'], '%Y-%m-%d %H:%M')
CampEndTime = datetime.datetime.strptime(config.root.CampDetails['EndTime'], '%Y-%m-%d %H:%M')

#Prepare for the loop, which will go through each day of camp and create an instance of each day's period
ThisDay = datetime.datetime.strptime(datetime.datetime.strftime(CampStartTime, '%Y-%m-%d'), '%Y-%m-%d')
log2('first thisDay is %s' % ThisDay)

#start our session, then go through the loop
session = Session()
loop = 'start'
while loop == 'start': #this loop keeps incrementing the day until it attempts to create periods which happen     
    for x in xrange(0,len(config.root.CampDetails.Periods.Period)):
        ThisStartTime = datetime.datetime.strptime((datetime.datetime.strftime(ThisDay, '%Y-%m-%d') + ' ' + config.root.CampDetails.Periods.Period[x]['StartTime']),'%Y-%m-%d %H:%M')
        ThisEndTime = datetime.datetime.strptime((datetime.datetime.strftime(ThisDay, '%Y-%m-%d') + ' ' + config.root.CampDetails.Periods.Period[x]['EndTime']),'%Y-%m-%d %H:%M')
        ThisPeriodName = config.root.CampDetails.Periods.Period[x]['Name']
        find_period = session.query(period).filter(period.periodname == ThisPeriodName,period.starttime == ThisStartTime,period.endtime == ThisEndTime).first()
        if find_period is None and ThisStartTime < CampEndTime:
            log2('Period not found. Creating period instance with details ' + datetime.datetime.strftime(ThisStartTime, '%Y-%m-%d %H:%M') + datetime.datetime.strftime(ThisStartTime, '%Y-%m-%d %H:%M') + ThisPeriodName)
            session.add(period(periodname = ThisPeriodName,starttime = ThisStartTime,endtime = ThisEndTime))
        #THIS LINE IS NOT FINISHED! you need to finish asking if the absent group is there, and if not, create it.
        find_absent_group = session.query(group).filter(group.groupname == 'absent',period.starttime == ThisStartTime,period.endtime == ThisEndTime).first()
        if ThisStartTime > CampEndTime:
            loop = 'stop'
    ThisDay = ThisDay + datetime.timedelta(days=1)
    log2('now looping for %s' % ThisDay)
session.commit()
log2('finished!')