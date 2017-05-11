from flask import Blueprint, render_template, request, flash, redirect
from werkzeug import secure_filename
from io import StringIO
from .controllers import *
from app.models import *
from app.config import *

setup = Blueprint('setup', __name__, template_folder='templates')

#Application setup page. This needs to be run at the start, just after the app has been deployed. The user uploads config files and user lists to populate the database.
@setup.route('/user/<logonid>/setup/', methods=["GET", "POST"])
def setuppage(logonid):

    try:
        session = Session()
        thisuser = getuser(session,logonid,True)
        log('SETUP: user firstname:%s lastname:%s method:%s' % (thisuser.firstname, thisuser.lastname, request.method))
    except Exception as ex:
        session.close()
        return str(ex)

    try:
        #check if this user is an admin or the Administrator superuser, if they are not, deny them.
        if thisuser.isadmin != 1 and thisuser.logonid != getconfig('AdminUUID'):
            return errorpage(thisuser,'You are not allowed to view this page.')
        else:
            if request.method == 'GET':
                session.close()
                return render_template('setup.html', \
                                                thisuser=thisuser, \
                                                campname=getconfig('Name'), favicon=getconfig('Favicon_URL'), instrumentlist=getconfig('Instruments').split(","), supportemailaddress=getconfig('SupportEmailAddress'), \
                                                )
            if request.method == 'POST':
                session.close()
                # Get the name of the uploaded file
                file_bytes = request.files['file']
                filename = secure_filename(file_bytes.filename)
                if file_bytes and allowed_file(filename):
                    log('SETUP: File received named %s' % filename)

                    file_string = file_bytes.getvalue()
                    file_text = file_string.decode('UTF-8')
                    csv = StringIO(file_text)

                    if filename == 'config.xml':
                        message = dbbuild(file_text)
                    if filename == 'campers.csv':
                            message = importusers(csv)
                    if filename == 'musiclibrary.csv':
                            message = importmusic(csv)
                    if message == 'Success':
                        flash(message,'success')
                    else:
                        flash(message,'error')
                    return redirect(request.url)
    
    except Exception as ex:
        log('Failed to execute %s for user %s %s with exception: %s.' % (request.method, thisuser.firstname, thisuser.lastname, ex))
        message = ('Failed to execute %s with exception: %s. Try refreshing the page and trying again or contact camp administration.' % (request.method, ex))
        session.rollback()
        session.close()
        if request.method == 'GET':
            return errorpage(thisuser,'Failed to display page. %s' % ex)
        else:
            return jsonify(message = message, url = 'none')

#This page is viewable by the admin only, it lets them edit different objects in the database - grouptemplates, locations, periods, etc.
@setup.route('/user/<logonid>/objecteditor/<input>/', methods=["GET","POST","DELETE"])
def objecteditor(logonid, input, objectid=None):

    try:
        session = Session()
        thisuser = getuser(session,logonid,True)
        log('OBJECTEDITOR: user firstname:%s lastname:%s method:%s' % (thisuser.firstname, thisuser.lastname, request.method))
    except Exception as ex:
        session.close()
        return str(ex)

    try:
        if thisuser.isadmin != 1:
            session.close()
            return render_template('errorpage.html', \
                                    thisuser=thisuser, \
                                    campname=getconfig('Name'), favicon=getconfig('Favicon_URL'), instrumentlist=getconfig('Instruments').split(","), supportemailaddress=getconfig('SupportEmailAddress'), \
                                    errormessage = 'You do not have permission to view this page.'
                                    )

        log('User requested objects with type %s' % input)
        if input == 'grouptemplate':
            table = 'grouptemplate'
            type = 'Group Template'
            objects_query = session.query(grouptemplate)
        elif input == 'location':
            table = 'location'
            type = 'Location'
            objects_query = session.query(location)
        elif input == 'period':
            table = 'period'
            type = 'Period'
            objects_query = session.query(period)
        elif input == 'music':
            table = 'music'
            type = 'Music'
            objects_query = session.query(music)
        elif input == 'group':
            table = 'group'
            type = 'Group'
            objects_query = session.query(group)
        else:
            session.close()
            return render_template('errorpage.html', \
                                thisuser=thisuser, \
                                campname=getconfig('Name'), favicon=getconfig('Favicon_URL'), instrumentlist=getconfig('Instruments').split(","), supportemailaddress=getconfig('SupportEmailAddress'), \
                                errormessage = 'Invalid input.'
                                )
        if request.method == 'GET':
                object_dict = dict((col, getattr(objects_query.first(), col)) for col in objects_query.first().__table__.columns.keys())
                objects = objects_query.all()
                session.close()
                return render_template('objecteditor.html', \
                                    thisuser=thisuser, \
                                    object_dict=object_dict, \
                                    objects=objects, \
                                    type=type, \
                                    table=table, \
                                    objectid=objectid, \
                                    campname=getconfig('Name'), favicon=getconfig('Favicon_URL'), instrumentlist=getconfig('Instruments').split(","), supportemailaddress=getconfig('SupportEmailAddress'), \
                                    )

        if request.method == 'POST':
            try:
                #format the packet received from the server as JSON
                content = request.json
                log('Received packet for modifying %ss with content: %s' % (type, content))
                for o in content['objects']:
                    if o[table + 'id'] != '' and o[table + 'id'] is not None:
                        if o[table + 'id'] == 'new':
                            log('Found a new object to create')
                            if table == 'grouptemplate':
                                object = grouptemplate()
                            elif table == 'location':
                                object = location()
                            elif table == 'period':
                                object = period()
                            elif table == 'music':
                                object = music()
                            elif table == 'group':
                                object = group()
                            session.add(object)
                        else:
                            log('Trying to find a %s object with id %s' % (table, o[table + 'id']))
                            object = objects_query.filter(getattr(globals()[table],(table + 'id')) == o[table + 'id']).first()
                            if object is None:
                                session.rollback()
                                session.close()
                                return jsonify(message = 'Could not find one of your requested objects. This is a malformed request packet.', url = 'none')
                        for key, value in o.items():
                            if key != table + 'id':
                                log('Changing object %s key %s to %s' % (table, key, value))
                                setattr(object,key,value)
                        session.merge(object)
                        url = '/user/' + thisuser.logonid + '/objecteditor/' + table + '/'
                        session.commit()
                        session.close()
                        return jsonify(message = 'none', url = url)
            except Exception as ex:
                session.rollback()
                session.close()
                return jsonify(message = 'Failed to post update with exception: %s' % ex, url = url)

        if request.method == 'DELETE':
            try:
                session.delete(objects_query.filter(getattr(globals()[table],(table + 'id')) == request.json).first())
                url = '/user/' + thisuser.logonid + '/objecteditor/' + table + '/'
                session.commit()
                session.close()
                return jsonify(message = 'none', url = url)
            except Exception as ex:
                session.rollback()
                session.close()
                return jsonify(message = 'Failed to delete object with exception %s' % ex, url = 'none')

    except Exception as ex:
        log('Failed to execute %s for user %s %s with exception: %s.' % (request.method, thisuser.firstname, thisuser.lastname, ex))
        message = ('Failed to execute %s with exception: %s. Try refreshing the page and trying again or contact camp administration.' % (request.method, ex))
        session.rollback()
        session.close()
        if request.method == 'GET':
            return errorpage(thisuser,'Failed to display page. %s' % ex)
        else:
            return jsonify(message = message, url = 'none')
