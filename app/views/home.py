from flask import Blueprint, render_template, request
from app import Session
from app.models import *
from sqlalchemy import *
import datetime
from datetime import date, timedelta
from app.controllers import getschedule

home = Blueprint('home', __name__)

#upon the URL request in the form domain/user/<logonid> the user receives their home. The home contains the groups they 
#are playing in. Optionally, this page presents their home in the future or the past, and gives them further options.
@home.route('/user/<logonid>/')
def homePage(logonid,inputdate='n'):

    try:
        session = Session()
        thisuser = getuser(session,logonid,True)
        log('HOME: user firstname:%s lastname:%s method:%s' % (thisuser.firstname, thisuser.lastname, request.method))
    except Exception as ex:
        session.close()
        return str(ex)

    try:
        log('HOME: date modifier is currently set to %s' % inputdate)
        #get the current announcement
        currentannouncement = session.query(announcement).order_by(desc(announcement.creationtime)).first()
        if currentannouncement is not None:
            announcementcontent = currentannouncement.content.replace("\n","<br />")
        else:
            announcementcontent = ''
        #get impontant datetimes
        today = datetime.datetime.combine(datetime.date.today(), datetime.time.min) #get today's date
        log('HOME: Today is %s' % today.strftime('%Y-%m-%d %H:%M'))
        campstarttime = datetime.datetime.strptime(getconfig('StartTime'), '%Y-%m-%d %H:%M')
        campendtime = datetime.datetime.strptime(getconfig('EndTime'), '%Y-%m-%d %H:%M')
        #if the suer has submitted a date, convert it to a datetime and use it as the display date
        if inputdate != 'n': 
            displaydate = datetime.datetime.strptime(inputdate, '%Y-%m-%d')
        #if the user has not submitted a date and today is before the start of camp, use the first day of camp as the display date
        elif today < datetime.datetime.strptime(getconfig('StartTime'), '%Y-%m-%d %H:%M'): 
            displaydate = datetime.datetime.strptime(getconfig('StartTime').split()[0], '%Y-%m-%d')
        #if today is after the start of camp, use today as the display date
        else:
            displaydate = today
        
        previousday = displaydate + datetime.timedelta(days=-1)
        midday = displaydate + datetime.timedelta(hours=12)
        nextday = displaydate + datetime.timedelta(days=1)

        #get an array containing the dates that the camp is running
        dates = []
        for d in range((campendtime-campstarttime).days + 2):
            dates.append(campstarttime + timedelta(days=d))

        #get the user's schedule, an array of objects depending on the user's state during each period
        schedule = getschedule(session,thisuser,displaydate)

        unscheduled = False
        for p in schedule:
            if session.query(group).filter(group.periodid == p.periodid, group.status == "Confirmed", or_(group.ismusical == 1, group.iseveryone == 1)).first() is None:
                unscheduled = True
                break

        session.close()

        return render_template('home.html', \
                            thisuser=thisuser, \
                            date=displaydate,\
                            schedule=schedule, \
                            dates=dates, \
                            previousday=previousday, \
                            nextday=nextday, \
                            today=today, \
                            campname=getconfig('Name'), favicon=getconfig('Favicon_URL'), instrumentlist=getconfig('Instruments').split(","), supportemailaddress=getconfig('SupportEmailAddress'), \
                            currentannouncement=announcementcontent, \
                            now = datetime.datetime.now(), \
                            midday=midday, \
                            unscheduled=unscheduled, \
                            )

    except Exception as ex:
        log('Failed to execute %s for user %s %s with exception: %s.' % (request.method, thisuser.firstname, thisuser.lastname, ex))
        message = ('Failed to execute %s with exception: %s. Try refreshing the page and trying again or contact camp administration.' % (request.method, ex))
        session.rollback()
        session.close()
        if request.method == 'GET':
            return render_template('errorpage.html', \
                                        thisuser=thisuser, \
                                        campname=getconfig('Name'), favicon=getconfig('Favicon_URL'), instrumentlist=getconfig('Instruments').split(","), supportemailaddress=getconfig('SupportEmailAddress'), \
                                        errormessage = 'Failed to display page. %s' % ex
                                        )
        else:
            return jsonify(message = message, url = 'none')

#NOT CURRENTLY USED Currently broken. Doesn't like the fact that the getschedule function returns an array of inconsistant objects. Either make them consistant,
#or put logic into the 'for s in ...' part of the below function. Or maybe improve the query in the getschedule function.
"""@app.route('/user/<logonid>/requestschedule/', methods=["POST"])
def requestschedule(logonid):
    log('Schedule request for date %s' % request.json['date'])
    #convert the inputdate to a datetime object
    date = datetime.datetime.strptime(request.json['date'], '%Y-%m-%d')
    session = Session()
    #gets the data associated with this user
    thisuser = session.query(user).filter(user.logonid == logonid).first()
    if thisuser is None:
        session.close()
        return jsonify(message = 'Your user does not exist. Something went wrong.', url = 'none', status_code = 400)

    schedule_serialized = []
    for s in getschedule(session,thisuser,date):
        schedule_serialized.append({'groupname': s.groupname, 'starttime': s.starttime, 'endtime': s.endtime,\
            'locationname': s.locationname, 'groupid': s.groupid, 'ismusical': s.ismusical, 'iseveryone': s.iseveryone,\
            'preiodid': s.periodid, 'periodname': s.periodname, 'instrumentname': s.instrumentname})

    return jsonify(schedule_serialized)"""

#When the user selects the "next day" and "previous day" links on their home, it goes to this URL. this route redirects them back
#to the user home with a date modifier.
@home.route('/user/<logonid>/date/<date>/')
def homeDateModifier(logonid,date):
    return homePage(logonid,date)

#Makes a post query that marks a player adsent for a given period. This is triggered off the above (two) home functions.
@home.route("/user/<logonid>/period/<periodid>/absent/<command>/", methods=["POST"])
def mark_absent(logonid,periodid,command):

    try:
        session = Session()
        thisuser = getuser(session,logonid,True)
        log('ABSENTREQUEST: user firstname:%s lastname:%s method:%s' % (thisuser.firstname, thisuser.lastname, request.method))
    except Exception as ex:
        session.close()
        return str(ex)

    try:
        thisperiod = getperiod(session,periodid)
        if command == 'confirm':
            thisuser.markabsent(session,thisperiod)
        if command == 'cancel':            
            thisuser.markpresent(session,thisperiod)

    except Exception as ex:
        log('Failed to execute %s for user %s %s with exception: %s.' % (request.method, thisuser.firstname, thisuser.lastname, ex))
        message = ('Failed to execute %s with exception: %s. Try refreshing the page and trying again or contact camp administration.' % (request.method, ex))
        session.rollback()
        session.close()
        if request.method == 'GET':
            return render_template('errorpage.html', \
                                        thisuser=thisuser, \
                                        campname=getconfig('Name'), favicon=getconfig('Favicon_URL'), instrumentlist=getconfig('Instruments').split(","), supportemailaddress=getconfig('SupportEmailAddress'), \
                                        errormessage = 'Failed to display page. %s' % ex
                                        )
    else:
        return jsonify(message = message, url = 'none')