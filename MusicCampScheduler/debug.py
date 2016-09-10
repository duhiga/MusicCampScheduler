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