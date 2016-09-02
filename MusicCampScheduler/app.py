"""

This app runs the music camp scheduler site the target audience for this site is around 100 people for a camp around 1 week
long. The intended model for the music camp is that people are allocated into groups like orchestras, bands, quartets, etc
over several periods in a day. People can mark themselves as "absent" at least one day in advance and will not be allocated 
to groups in the session. Once running, the website must be maintained by an adminstrator, and conductors to confirm groups.

Before use, you need to open up config.xml and point it to a SQL database, and configure any other needed information. Debug
levels are 0=none, 1=debug, 2=verbose.

"""


from flask import Flask, render_template, redirect, jsonify, make_response, json
import scss
import sys
import types
import time
import datetime
import re
import json
import untangle
#import DBSetup
from SQL import *
from debug import *
#from DBSetup import *
from json import JSONEncoder, JSONDecoder

# Make the WSGI interface available at the top level so wfastcgi can get it.
app = Flask(__name__)
obj = untangle.parse('config.xml')
app.secret_key = obj.root.CampDetails['SecretKey']
wsgi_app = app.wsgi_app


#the below two classes extend JSON to decode datetimes properly.  Use:
#event = {'Timestamp': datetime.datetime.now(), 'Value': 10}
#json_event = json.dumps(event, cls=WebAPIEncoder)
#decoded_json_event = json.loads(json_event, cls=WebAPIDecoder)
class WebAPIEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()
        return super(WebAPIEncoder, self).default(obj)
 
 
class WebAPIDecoder(JSONDecoder):
    def decode(self, obj):
        decoded = super(WebAPIDecoder, self).decode(obj)
        if isinstance(decoded, list):
            pairs = enumerate(decoded)
        elif isinstance(decoded, dict):
            pairs = decoded.items()
        result = []
        for k, v in pairs:
            if k == "Timestamp":
                v = datetime.datetime.strptime(v, '%Y-%m-%dT%H:%M:%S.%f')
            result.append((k, v))
        if isinstance(decoded, list):
            return [r[1] for r in result]
        elif isinstance(decoded, dict):
            return dict(result)
        return decoded

#the user object defines an individual user.  The user is an individual
#attending the music camp
class user:
    def __init__(self, userid, firstname, lastname, age, email):
        self.userid = userid
        self.firstname = firstname
        self.lastname = lastname
        self.age = age
        self.email = email

#the group object defines an instance of a group of player()s playing music,
#having a meal, or being absent.  These objects are either generated
#by users through a web GUI, or by the scheduler.  A group object with an empty
#periodid indicates that it has not been scheduled yet.
class group:
    def __init__(self, groupid, groupname, locationid, requesttime, periodid, music, ismusical, iseveryone, conductor, flute, oboe, \
                 clarinet, bassoon, horn, trumpet, trombone, tuba, percussion, violin, viola, cello, doublebass):
        self.groupid = groupid
        self.groupname = groupname
        self.locationid = locationid
        self.requesttime = requesttime
        self.periodid = periodid
        self.music = music
        self.ismusical = ismusical
        self.iseveryone = iseveryone
        self.conductor = conductor
        self.flute = flute
        self.oboe = oboe
        self.clarinet = clarinet
        self.bassoon = bassoon
        self.horn = horn
        self.trumpet = trumpet
        self.trombone = trombone
        self.tuba = tuba
        self.percussion = percussion
        self.violin = violin
        self.viola = viola
        self.cello = cello
        self.doublebass = doublebass

#the player object defines a player sitting in a group
class player:
    def __init__(self, firstname, lastname, instrument, groupname, location, groupid):
        self.firstname = firstname
        self.lastname = lastname
        self.instrument = instrument
        self.groupname = groupname
        self.location = location
        self.groupid = groupid

#the period object describes a single period, be it breakfast, lunch, dinner,
#an evening session or a daytime session.
class perioddisplay:
    def __init__(self, starttime, endtime, groupname, instrument, locationname, groupid, ismusical, iseveryone, periodid, periodname):
        self.starttime = starttime
        self.endtime = endtime
        self.groupname = groupname
        self.instrument = instrument
        self.location = locationname
        self.groupid = groupid
        self.ismusical = ismusical
        self.iseveryone = iseveryone
        self.periodid = periodid
        self.periodname = periodname

class period:
    def __init__(self, periodid, starttime, endtime, periodname):
        self.periodid = periodid
        self.starttime = starttime
        self.endtime = endtime
        self.periodname = periodname

#the location object describes a location that people can play in, eat or have fun
class location:
    def __init__(self, locationid, locationname, capacity):
        self.locationid = locationid
        self.locationname = locationname
        self.capacity = capacity

class date:
    def __init__(self, date):
        self.date = date

log2('   Python version: %s' % sys.version)

#checks a user entry for bad characters.  Users are only allowed to submit inputs in their URLs with letters and numbers and dashes.
def check(string):
    log1('checking input %s' % string)
    if re.match("^[a-zA-Z0-9-]*$",string):
        log1('%s passes the check' % string)
        tf = True
    else:
        log1('%s fails the check' % string)
        tf = False
    return tf
    
#turns data extracted from a SQL query into a specified object
def datatoclass(classtype,data,row):
    try:
        generatedclass = getattr(sys.modules[__name__], classtype) #convert the classtype string into a class
    except AttributeError:
        raise NameError("datatoclass failed because %s doesn't exist." % objecttype)
    if isinstance(generatedclass, (types.ClassType, types.TypeType)):
        c = (generatedclass(*[data[row][column] for column in range(0,len(data[row]))])) #insert data from SQL statement into the chosen class
        return c
    raise TypeError("datatoclass failed because %s is not a class." % classtype)

#turns data extracted from a SQL query into a list of specified objects
def datatoclasslist(classtype,data):
    try:
        log2('Forming %s %s objects that match the query' % (len(data),classtype))
        classlist = []
        for row in range(0,len(data)):
            classlist.append(datatoclass(classtype,data,row))
        log2('created %s list with length %s' % (classtype,len(classlist)))
        return classlist
    except Exception as ex:
        log1('datatoclasslist failed while trying to convert to a %s class with exception: %s' % (classtype,ex))
        log1('The data it was trying to convert was:')
        log1(data)
        return 'error'

#looks up a list of players that aren't playing in any groups that share a period with the input group, and play one of the instruments in
#the group.  Returns a list of player objects.
def playersubstitutesforgroup(groupid):
    try:
        log2('looking up the session ID for group with groupid %s' % groupid)
        g = datatoclass('group',sql("SELECT * FROM groups WHERE groupid=\"" + groupid + "\""),0)
        log2('this group sessionid is %s' % g.periodid)
        log2('looking up all free players in session with sessionid %s' % g.periodid)
        #the following query finds substitutes for this group.
        #i.e.  people who aren't currently playing, but play the same
        #instruments as those in the group
        data = sql("""SELECT u.firstname,u.lastname,ga.instrument,null,null,null FROM groupassignments ga INNER JOIN (
                          SELECT si.userid,si.instrument FROM instruments si WHERE NOT EXISTS (
                              SELECT nu.userid FROM users nu
                              INNER JOIN groupassignments nga ON nga.userid = nu.userid
                              INNER JOIN groups ng ON nga.groupid = ng.groupid
                              WHERE nu.userid = si.userid AND ng.periodid = """ + g.periodid + """)) n
                        ON ga.instrument = n.instrument
                        INNER JOIN users u ON n.userid = u.userid
                        WHERE ga.groupid = """ + g.groupid)
        substitutelist = datatoclasslist('player',data)
        return substitutelist
    except Exception as ex:
        log1('playersubstitutesforgroup failed on groupID %s with exception: %s' % (groupid,ex))
        return 'error'

#Looks up the amount of times a user has participated in an "ismusical" group during the camp
def useridtonumberofplayings(userid):
    try:
        log2('finding number of group plays for user %s' % userid)
        data = sql("""
            SELECT COUNT(g.ismusical) FROM groups g
            INNER JOIN groupassignments ga ON g.groupid = ga.groupid
            INNER JOIN periods p on g.periodid = p.periodid
            WHERE g.ismusical = 1 AND p.endtime < NOW() AND ga.userid = \'""" + userid + "\'")
        groupcount = data[0][0]
        log2('found %s playings for user %s' % (groupcount,userid))
        return groupcount
    except Exception as ex:
        log1('useridtonumberofplayings failed on userid %s with exception: %s' % (userid,ex))
        return 'error'

#gets a list of periods corresponding to the requested userid and date
def useridanddatetoperiods(userid,date):
    data = sql("""
        SELECT TIME_FORMAT(p.starttime,'%H:%i'),TIME_FORMAT(p.endtime,'%H:%i'),b.groupname,b.instrument,b.locationname,b.groupid,b.ismusical,b.iseveryone,p.periodid,p.periodname
        FROM periods p
        LEFT JOIN(
        SELECT g.periodid,g.groupname,ga.instrument,l.locationname,g.groupid,g.ismusical,g.iseveryone
        FROM groupassignments ga
        RIGHT JOIN groups g ON g.groupid = ga.groupid
        INNER JOIN locations l ON g.locationid = l.locationid
        WHERE ga.userid = '""" + userid + """' OR g.iseveryone = 1
        ORDER BY g.iseveryone
        ) b ON b.periodid = p.periodid
        WHERE CAST(p.starttime AS DATE) = '""" + date + """'
        GROUP BY p.starttime""")
    p = datatoclasslist('perioddisplay',data)
    return p

#looks up the whole list of players in a given periodID
def periodidtoplayerlist(periodid):
    try:
        log2('Looking up all players playing in periodID %s' % periodid)
        data = sql("""
            SELECT u.firstname,u.lastname,ga.instrument,g.groupname,l.locationname,g.groupid
            FROM groups g
            LEFT JOIN groupassignments ga ON g.groupid = ga.groupid
            LEFT JOIN locations l ON g.locationid = l.locationid
            LEFT JOIN users u ON ga.userid = u.userid
            WHERE g.periodid = """ + periodid + """
            ORDER BY CASE WHEN g.groupname='absent' THEN 1 ELSE 0 END,g.groupname, FIELD(instrument,'flute','oboe','clarinet','bassoon','horn',
            'trumpet','trombone','tuba','percussion','violin','cello','doublebass')""")
        playerlist = datatoclasslist('player',data)
        return playerlist
    except Exception as ex:
        log1('periodidtoplayerlist failed on groupID %s with exception: %s' % (groupid,ex))
        return 'error'

#the root page isn't meant to be navigable.  It shows the user an error and
#tells them how to get to their user dashboard.
@app.route('/')
def rootpage():
    return render_template('index.html')

#upon the URL request in the form domain/user/<userid> the user receives their dashboard.  This updates every day with the groups they 
#are playing in.
@app.route('/user/<userid>/')
def dashboard(userid,date='none'):
    if check(userid) and check(date):
        log1('dashboard fetch requested for user %s' % userid)
        log1('date modifier is currently set to %s' % date)
        user = datatoclass('user',sql("SELECT userid,firstname,lastname,age,email FROM users WHERE userid=\"" + userid + "\""),0)
        #find the number of times a user has played in groups in the past
        count = useridtonumberofplayings(userid)
        #find all periods today, and what this user is doing in each
        today = "2016-12-29" #time.strftime("%Y-%m-%d")
        if date == 'none':
            date = today
        weekday = datetime.datetime.strftime((datetime.datetime.strptime(date, '%Y-%m-%d')), '%A')
        periods = useridanddatetoperiods(userid,date)
        previousday = datetime.datetime.strftime((datetime.datetime.strptime(date, '%Y-%m-%d') + datetime.timedelta(days=-1)), '%Y-%m-%d')
        nextday = datetime.datetime.strftime((datetime.datetime.strptime(date, '%Y-%m-%d') + datetime.timedelta(days=1)), '%Y-%m-%d')
        return render_template('dashboard.html', \
                            user=user, \
                            count=count, \
                            date=date,\
                            periods=periods, \
                            previousday=previousday, \
                            nextday=nextday, \
                            today=today, \
                            weekday=weekday \
                            )
    else:
        return 'You have submitted illegal characters in your URL. Any inputs must only contain letters, numbers and dashes.'

@app.route('/user/<userid>/date/<date>/')
def dashboardDateModifier(userid,date):
    return dashboard(userid,date)

#this route is linked to from the user's dashboard.  When they click on a group name, they are taken to a page showing all the people
#in that group, along with possible substitutes
@app.route('/user/<userid>/group/<groupid>/')
def groupdetails(userid,groupid):
    if check(userid) and check(groupid):
        log1('Group page requested by %s for groupID %s' % (userid,groupid))
        #gets the data associated with this user
        user = datatoclass('user',sql("SELECT * FROM users WHERE userid=\"" + userid + "\""),0)
        #gets the data associated with this group ID
        group = datatoclass('group',sql("SELECT * FROM groups WHERE groupid=\"" + groupid + "\""),0)
        #gets the period that this group takes place
        period = datatoclass('period',sql("SELECT * FROM periods WHERE periodid = " + group.periodid),0)
        #gets the location that this group takes place
        location = datatoclass('location',sql("SELECT * FROM locations WHERE locationid = " + group.locationid),0)
        #gets the list of players playing in the given group
        data = sql("""
            SELECT u.firstname,u.lastname,ga.instrument,g.groupname,l.locationname,g.groupid
            FROM groupassignments ga
            INNER JOIN users u ON ga.userid = u.userid
            INNER JOIN groups g ON ga.groupid = g.groupid
            INNER JOIN locations l ON g.locationid = l.locationid
            WHERE ga.groupid=""" + groupid)
        players = datatoclasslist('player',data)
        substitutes = playersubstitutesforgroup(groupid)
        return render_template('group.html', \
                            period=period, \
                            group=group, \
                            location=location, \
                            players=players, \
                            substitutes=substitutes, \
                            user=user \
                            )
    else:
        return 'You have submitted illegal characters in your URL. Any inputs must only contain letters, numbers and dashes.'

@app.route('/user/<userid>/grouprequest/')
def grouprequestpage(userid):
    if check(userid):
        #gets the data associated with this user
        user = datatoclass('user',sql("SELECT * FROM users WHERE userid=\"" + userid + "\""),0)
        return render_template('grouprequest.html', \
                            user=user, \
                            )
    else:
        return 'You have submitted illegal characters in your URL. Any inputs must only contain letters, numbers and dashes.'

@app.route('/user/<userid>/absentrequest/')
def absentrequestpage(userid):
    if check(userid):
        #gets the data associated with this user
        user = datatoclass('user',sql("SELECT * FROM users WHERE userid=\"" + userid + "\""),0)
        today = time.strftime("%Y-%m-%d")
        weekday = time.strftime("%A")
        nextday = datetime.datetime.strftime((datetime.datetime.strptime(today, '%Y-%m-%d') + datetime.timedelta(days=1)), '%Y-%m-%d')
        #look up all dates in the future containing periods
        perioddates = datatoclasslist('date',sql("""
                SELECT DISTINCT DATE_FORMAT(starttime,'%Y-%m-%d') FROM periods WHERE starttime >= '""" + today + "'"))
        #look up all sessions on the user's requested day
        periods = datatoclasslist('period',sql("""
                SELECT periodid,TIME_FORMAT(starttime,'%H:%i'),TIME_FORMAT(endtime,'%H:%i'),periodname
                FROM periods
                WHERE starttime >= '""" + nextday + "'"))
        return render_template('absentrequest.html', \
                            user=user, \
                            today=today, \
                            weekday=weekday, \
                            periods=periods, \
                            perioddates=perioddates, \
                            campname=obj.root.CampDetails['Name'] \
                            )
    else:
        return 'You have submitted illegal characters in your URL. Any inputs must only contain letters, numbers and dashes.'

#Returns data from a query from the page from the function above.
@app.route("/return/periodlist/<date>/", methods=["GET"])
def get_request(date):
    if check(date):
        periods = (datatoclasslist('period',sql("""
                SELECT periodid,TIME_FORMAT(starttime,'%H:%i'),TIME_FORMAT(endtime,'%H:%i'),periodname
                FROM periods
                WHERE DATE_FORMAT(starttime,'%Y-%m-%d') = '""" + date + "'")))
        response = make_response(json.dumps([ob.__dict__ for ob in periods]))
        response.content_type = 'application/json'
        log2(response)
        return response
    else:
        return 'You have submitted illegal characters in your URL. Any inputs must only contain letters, numbers and dashes.'

#this page is the full report for any given period
@app.route('/user/<userid>/period/<periodid>/')
def periodpage(userid,periodid):
    if check(userid) and check(periodid):
        players = periodidtoplayerlist(periodid)
        user = datatoclass('user',sql("SELECT * FROM users WHERE userid=\"" + userid + "\""),0)
        period = datatoclass('period',sql("SELECT * FROM periods WHERE periodid = " + periodid),0)
        return render_template('period.html', \
                            players=players, \
                            user=user, \
                            period=period \
                            )
    else:
        return 'You have submitted illegal characters in your URL. Any inputs must only contain letters, numbers and dashes.'

if __name__ == '__main__':
    app.run(debug=True, \
            host='0.0.0.0')
