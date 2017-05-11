import sqlalchemy
import untangle
import time
import datetime
import csv
from sqlalchemy.dialects.mysql.base import MSBinary
import uuid
from app.config import *
from app.models import *

from app import Session

#For a given file, return whether it's an allowed type or not
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1] in ['txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'xml', 'csv']

#Database Build section. The below configures periods and groups depending on how the config.xml is configured.
def dbbuild(configfile):
    log('Initiating initial database build from config file')
    conf = untangle.parse(configfile)
    #Grab the camp start and end times from the config file
    CampStartTime = datetime.datetime.strptime(getconfig('StartTime'), '%Y-%m-%d %H:%M')
    CampEndTime = datetime.datetime.strptime(getconfig('EndTime'), '%Y-%m-%d %H:%M')
    #Prepare for the loop, which will go through each day of camp and create an instance of each day's period
    ThisDay = datetime.datetime.strptime(datetime.datetime.strftime(CampStartTime, '%Y-%m-%d'), '%Y-%m-%d')
    #start our session, then go through the loop
    session = Session()

    #Create the instrument objects from the file
    for x in range(0,len(conf.root.CampDetails.Instrument)):
        find_instrument = session.query(instrument).filter(instrument.instrumentname == conf.root.CampDetails.Instrument[x]['Name']).first()
        if find_instrument is None:
            newinstrument = instrument(
                instrumentname = conf.root.CampDetails.Instrument[x]['Name'],
                order = conf.root.CampDetails.Instrument[x]['Order'],
                )
            if conf.root.CampDetails.Instrument[x]['Abbreviations'] is not None:
                newinstrument.abbreviations = conf.root.CampDetails.Instrument[x]['Abbreviations'].split(",")
            session.add(newinstrument)
            log('Created instrument %s' % newinstrument.instrumentname)
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
                locationname = conf.root.CampDetails.Location[x]['Name'],
                capacity = conf.root.CampDetails.Location[x]['Capacity']
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
            thisuser.firstname = row[0].replace(" ","")
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
                session.add(thismusic)
                session.flush()
                for idx, item in enumerate(row):
                    try:
                        thisinstrument = getinstrumentbyname(session,headers[idx])
                    except:
                        thisinstrument = None
                    if thisinstrument is not None and item != '' and item != '0':
                        for x in range(0,int(item)):
                            session.add(musicinstrument(instrumentid = thisinstrument.instrumentid, musicid = thismusic.musicid))
                            log('IMPORTMUSIC: Added instrument %s to music with id %s' % (thisinstrument.instrumentname,thismusic.musicid))
                    elif item != '':
                        setattr(thismusic,headers[idx],item)
                session.flush()
                log('IMPORTMUSIC: Successfully created music. musicid:%s musicname:%s composer:%s' % (thismusic.musicid, thismusic.musicname, thismusic.composer))
        session.commit()
        session.close()
        return ('Success')
    except Exception as ex:
        session.rollback()
        session.close()
        log('IMPORTMUSIC: Failed to import with exception: %s.' % ex)
        return ('Failed to import with exception: %s.' % ex)