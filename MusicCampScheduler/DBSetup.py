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
    engine = create_engine("sqlite:///" + config.root.Application['DBPath'], echo=True)
else:
    engine = create_engine("sqlite:///" + config.root.Application['DBPath'])
log2('sqlalchemy version: %s' % sqlalchemy.__version__)
Session = sessionmaker()
Session.configure(bind=engine)
Base = declarative_base()

def dump_datetime(value):
    """Deserialize datetime object into string form for JSON processing."""
    if value is None:
        return None
    return [value.strftime("%Y-%m-%d"), value.strftime("%H:%M:%S")]

class user(Base):
    __tablename__ = 'users'

    userid = Column(Integer, primary_key=True)
    firstname = Column(String)
    lastname = Column(String)
    age = Column(Integer)
    isannouncer = Column(Integer)
    isconductor = Column(Integer)
    isadmin = Column(Integer)

    def __repr__(self):
        return "<user(userid='%s', firstname='%s', lastname='%s', age='%s', isannouncer='%s', isconductor='%s', isadmin='%s')>" % (
            self.userid, self.firstname, self.lastname, self.age, self.announcer, self.conductor, self.admin)

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
    Conductor = Column(Integer)
    Flute = Column(Integer)
    Oboe = Column(Integer)
    Clarinet = Column(Integer)
    Bassoon = Column(Integer)
    Horn = Column(Integer)
    Trumpet = Column(Integer)
    Trombone = Column(Integer)
    Tuba = Column(Integer)
    Percussion = Column(Integer)
    Piano = Column(Integer)
    Violin = Column(Integer)
    Viola = Column(Integer)
    Cello = Column(Integer)
    DoubleBass = Column(Integer)

    def __repr__(self):
        return """<group(groupid='%s', groupname='%s', locationid='%s', requesttime='%s', requesteduserid='%s', periodid='%s',
                        music='%s', ismusical='%s', iseveryone='%s', Conductor='%s', Flute='%s', Oboe='%s',
                        Clarinet='%s', Bassoon='%s', Horn='%s', Trumpet='%s', Trombone='%s', Tuba='%s',
                        Percussion='%s', Piano='%s', Violin='%s', Viola='%s', Cello='%s', DoubleBass='%s')>""" % (
            self.groupid,self.groupname,self.locationid,self.requesttime,self.periodid,self.music,self.ismusical,
            self.iseveryone,self.Conductor,self.Flute,self.Oboe,self.Clarinet,self.Bassoon,self.Horn,self.Trumpet,
            self.Trombone,self.Tuba,self.Percussion,self.Piano,self.Violin,self.Viola,self.Cello,self.DoubleBass)

class grouptemplate(Base):
    __tablename__ = 'grouptemplates'

    grouptemplateid = Column(Integer, primary_key=True)
    grouptemplatename = Column(String)
    size = Column(String)
    Conductor = Column(Integer)
    Flute = Column(Integer)
    Oboe = Column(Integer)
    Clarinet = Column(Integer)
    Bassoon = Column(Integer)
    Horn = Column(Integer)
    Trumpet = Column(Integer)
    Trombone = Column(Integer)
    Tuba = Column(Integer)
    Percussion = Column(Integer)
    Piano = Column(Integer)
    Violin = Column(Integer)
    Viola = Column(Integer)
    Cello = Column(Integer)
    DoubleBass = Column(Integer)

    """
    DONT THINK I NEED THIS...
    
    def dump(self):
        return {"IpPortList": {'grouptemplateid': self.grouptemplateid,
                               'grouptemplatename': self.grouptemplatename,
                               'size': self.size,
                               'Conductor': self.Conductor,
                               'Flute': self.Flute,
                               'Oboe': self.Oboe,
                               'Clarinet': self.Clarinet,
                               'Bassoon': self.Bassoon,
                               'Horn': self.Horn,
                               'Trumpet': self.Trumpet,
                               'Tuba': self.Tuba,
                               'Percussion': self.Percussion,
                               'Piano': self.Piano,
                               'Violin': self.Violin,
                               'Viola': self.Viola,
                               'Cello': self.Cello,
                               'DoubleBass': self.DoubleBass}}
    """

    def __repr__(self):
        return """<grouptemplate(grouptemplateid='%s', grouptemplatename='%s', size='%s', Conductor='%s', Flute='%s', Oboe='%s',
                        Clarinet='%s', Bassoon='%s', Horn='%s', Trumpet='%s', Trombone='%s', Tuba='%s',
                        Percussion='%s', Piano='%s', Violin='%s', Viola='%s', Cello='%s', DoubleBass='%s')>""" % (
            self.grouptemplateid,self.grouptemplatename,self.size,self.Conductor,self.Flute,self.Oboe,self.Clarinet,self.Bassoon,
            self.Horn,self.Trumpet,self.Trombone,self.Tuba,self.Percussion,self.Piano,self.Violin,self.Viola,self.Cello,self.DoubleBass)


class groupassignment(Base):
    __tablename__ = 'groupassignments'

    groupassignmentid = Column(Integer, primary_key=True)
    userid = Column(Integer, ForeignKey('users.userid'))
    groupid = Column(Integer, ForeignKey('groups.groupid'))
    instrument = Column(Enum('Conductor','Flute','Oboe','Clarinet','Bassoon','Horn','Trumpet','Trombone','Tuba','Percussion','Piano','Violin','Viola','Cello','DoubleBass','absent'), ForeignKey('instruments.instrumentname'))

    def __repr__(self):
        return "<groupassignment(groupassignmentid='%s', userid='%s', groupid='%s', instrument='%s')>" % (
            self.groupassignmentid,self.userid,self.groupid,self.instrument)

class instrument(Base):
    __tablename__ = 'instruments'

    instrumentid = Column(Integer, primary_key=True)
    userid = Column(Integer, ForeignKey('users.userid'))
    instrumentname = Column(Enum('Conductor','Flute','Oboe','Clarinet','Bassoon','Horn','Trumpet','Trombone','Tuba','Percussion','Piano','Violin','Viola','Cello','DoubleBass','absent'))
    grade = Column(Integer)
    isprimary = Column(Integer)

    def __repr__(self):
        return "<instrument(instrumentid='%s', userid='%s', instrumentname='%s', grade='%s', isprimary='%s')>" % (
            self.instrumentid,self.userid,self.instrumentname,self.grade,self.isprimary)

class location(Base):
    __tablename__ = 'locations'

    locationid = Column(Integer, primary_key=True)
    locationname = Column(String)
    capacity = Column(Integer)

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

    def __repr__(self):
        return "<period(periodid='%s', starttime='%s', endtime='%s', periodname='%s', meal='%s')>" % (
            self.periodid,self.starttime,self.endtime,self.periodname,self.meal)

#create all tables if needed
Base.metadata.create_all(engine)

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
    #create group templates
    for x in xrange(0,len(config.root.CampDetails.GroupTemplates.GroupTemplate)):
        log2(config.root.CampDetails.GroupTemplates.GroupTemplate[x])
        find_template = session.query(grouptemplate).filter(grouptemplate.grouptemplatename == config.root.CampDetails.GroupTemplates.GroupTemplate[x]['grouptemplatename']).first()
        if find_template is None:
            template = grouptemplate(\
                            grouptemplatename=config.root.CampDetails.GroupTemplates.GroupTemplate[x]['Name'],\
                            size=config.root.CampDetails.GroupTemplates.GroupTemplate[x]['Size'],\
                            Conductor=config.root.CampDetails.GroupTemplates.GroupTemplate[x]['Conductor'],\
                            Flute=config.root.CampDetails.GroupTemplates.GroupTemplate[x]['Flute'],\
                            Oboe=config.root.CampDetails.GroupTemplates.GroupTemplate[x]['Oboe'],\
                            Clarinet=config.root.CampDetails.GroupTemplates.GroupTemplate[x]['Clarinet'],\
                            Bassoon=config.root.CampDetails.GroupTemplates.GroupTemplate[x]['Bassoon'],\
                            Horn=config.root.CampDetails.GroupTemplates.GroupTemplate[x]['Horn'],\
                            Trombone=config.root.CampDetails.GroupTemplates.GroupTemplate[x]['Trombone'],\
                            Tuba=config.root.CampDetails.GroupTemplates.GroupTemplate[x]['Tuba'],\
                            Percussion=config.root.CampDetails.GroupTemplates.GroupTemplate[x]['Percussion'],\
                            Piano=config.root.CampDetails.GroupTemplates.GroupTemplate[x]['Piano'],\
                            Violin=config.root.CampDetails.GroupTemplates.GroupTemplate[x]['Violin'],\
                            Viola=config.root.CampDetails.GroupTemplates.GroupTemplate[x]['Viola'],\
                            Cello=config.root.CampDetails.GroupTemplates.GroupTemplate[x]['Cello'],\
                            DoubleBass=config.root.CampDetails.GroupTemplates.GroupTemplate[x]['DoubleBass'])
            session.add(template)
    session.commit()
    session.close()
    log2('Finished Database Build!')