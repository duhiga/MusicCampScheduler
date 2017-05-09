from flask import *
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
