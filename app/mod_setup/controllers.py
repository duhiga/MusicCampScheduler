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
                    instrument1 = instrument(userid = thisuser.userid, instrumentname = row[4].capitalize().replace(" ", ""), level = row[5], isprimary = 1, isactive = 1)
                    session.add(instrument1)
                    log('Created instrument listing: %s at level %s for %s' % (instrument1.instrumentname, instrument1.level, thisuser.firstname))
                if row[6] is not '':
                    instrument2 = instrument(userid = thisuser.userid, instrumentname = row[6].capitalize().replace(" ", ""), level = row[7], isprimary = 0, isactive = 1)
                    session.add(instrument2)
                    log('Created instrument listing: %s at level %s for %s' % (instrument2.instrumentname, instrument2.level, thisuser.firstname))
                if row[8] is not '':
                    instrument3 = instrument(userid = thisuser.userid, instrumentname = row[8].capitalize().replace(" ", ""), level = row[9], isprimary = 0, isactive = 1)
                    session.add(instrument3)
                    log('Created instrument listing: %s at level %s for %s' % (instrument3.instrumentname, instrument3.level, thisuser.firstname))
                if row[10] is not '':
                    instrument4 = instrument(userid = thisuser.userid, instrumentname = row[10].capitalize().replace(" ", ""), level = row[11], isprimary = 0, isactive = 1)
                    session.add(instrument4)
                    log('Created instrument listing: %s at level %s for %s' % (instrument4.instrumentname, instrument4.level, thisuser.firstname))
            rownum += 1
        session.commit()
        userscount = session.query(user).count()
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
                matchingtemplate = session.query(grouptemplate).filter(*[getattr(thismusic,i) == getattr(grouptemplate,i) for i in getinstrumentlist(session)]).first()
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
