from flask import Flask, render_template, request, redirect, jsonify, make_response, json, request, url_for, send_from_directory, flash
from collections import namedtuple

import sys
import types
import time
import datetime
import re
import json
import untangle
import uuid
import sqlalchemy
import os
import io
from datetime import date, timedelta
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, exists, Enum, types, UniqueConstraint, ForeignKeyConstraint, Text
from .config import *

log('Application Startup Initiated')

#Make the WSGI interface available at the top level so wfastcgi can get it.
app = Flask(__name__)

wsgi_app = app.wsgi_app
app.secret_key = getconfig('SecretKey')
engine = create_engine(getconfig('DATABASE_URL'))

log('Model Import Started')
from .models import *
log('Model Import Completed')

log('Database Build Started')
try:
    Base.metadata.create_all(engine, checkfirst=True)
    log('Database Build Completed')
except Exception as ex:
    log('Failed to create database tables with exception: ' % ex)

Session = sessionmaker(bind=engine)

log('Importing Setup Module')
from .mod_setup import setup
app.register_blueprint(setup)

log('Importing Home Module')
from .mod_home import home
app.register_blueprint(home)

log('Importing Lists Module')
from .mod_lists import lists
app.register_blueprint(lists)

log('Importing Requests Module')
from .mod_requests import requests
app.register_blueprint(requests)

log('Importing Admin Module')
from .mod_admin import admin
app.register_blueprint(admin)

@app.route('/js/<path:path>')
def send_js(path):
    return send_from_directory('js', path)

@app.route('/css/<path:path>')
def send_css(path):
    return send_from_directory('css', path)

@app.route('/img/<path:path>')
def send_png(path):
    return send_from_directory('img', path)

#this section manages the admin user. This will be the user that the admin will use to set up the database from the webapp
session = Session()
#try to find a user named 'Administrator' whos ID matches the app's configured AdminUUID
admin = session.query(user).filter(user.logonid == getconfig('AdminUUID'), user.firstname == 'Administrator').first()
#if we don't find one, it means that this is the first boot, or the AdminUUID has been changed
try:
    if admin is None:
        #try to find a user called Administrator
        findadmin = session.query(user).filter(user.firstname == 'Administrator').first()
        #if we find one, it means that someone has changed the AdminUUID parameter. Update this user to match it.
        if findadmin is not None:
            log('Found Administrator user did not match AdminUUID parameter. Updating the user details to match.')
            findadmin.logonid = getconfig('AdminUUID')
            session.merge(findadmin)
        #if we don't find one, this is the first boot of the app. Create the administrator user.
        else:
            log('Welcome to the music camp scheduler! This is the first boot of the app. Look in your applicaiton parameters for the AdminUUID parameter, then log in to the setup page with websitename/user/AdminUUID(replace this with your admin UUID)/setup/')
            admin = user(logonid = getconfig('AdminUUID'), userid = str(uuid.uuid4()), firstname = 'Administrator', lastname = 'A', isactive = 0, isadmin = 1, \
                arrival = datetime.datetime.strptime(getconfig('StartTime'), '%Y-%m-%d %H:%M'), departure = datetime.datetime.strptime(getconfig('EndTime'), '%Y-%m-%d %H:%M'))
            session.add(admin)
        session.commit()
except Exception as ex:
    log('Failed to validate administrator with exception: ' % ex)
session.close()
session.flush()

log("Application Startup Complete")