#not needed, keeping in case I need to use the code in an example later    
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


#old SQL
def periodidtoplayerlist(session, periodid):
    
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


#NOT USED. Just keeping this for reference.
#@app.route('/user/<userid>/absentreq/')
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
                            )
    else:
        return 'You have submitted illegal characters in your URL. Any inputs must only contain letters, numbers and dashes.'

#NOT USED - just keeping for reference
#Returns data from a query from the page from the function above.
#@app.route("/return/periodlist/<date>/", methods=["GET"])
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

#NOT FINISHED - SEE BELOW
#Used in the grouprequest page to fill the instruments
#@app.route("/return/instrumentplayers/<instrument>/", methods=["GET"])
def instrumentplayers_get(instrument,periodid='none'):
    if check(instrument) and check(periodid):
        if periodid == 'none':
            players = (datatoclasslist('player',sql("""
                SELECT u.userid,u.firstname,u.lastname,i.instrument,null,null,null 
                FROM instruments i INNER JOIN users u ON u.userid=i.userid""")))
        else:
            #NOT FINISHED to do: write the below SQL to find all available players for a particular instrument during a period
            players = (datatoclasslist('player',sql("""
                SELECT u.userid,u.firstname,u.lastname,i.instrument,null,null,null FROM users u 
                INNER JOIN instruments i ON u.userid = i.userid
                INNER JOIN groupassignments ga ON ga.userid = u.userid
                INNER JOIN groups g ON ga.groupid = g.groupid
                INNER JOIN periods p ON g.periodid = p.periodid
                WHERE p.periodid != """ + str(periodid) + " AND i.instrument = '" + str(instrument) + "'"))) #not finished
        response = make_response(json.dumps([ob.__dict__ for ob in players]))
        response.content_type = 'application/json'
        log2(response)
        return response
    else:
        return 'You have submitted illegal characters in your URL. Any inputs must only contain letters, numbers and dashes.'

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
        data = sql("""SELECT u.userid,u.firstname,u.lastname,ga.instrument,null,null,null FROM groupassignments ga INNER JOIN (
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