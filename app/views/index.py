from flask import Blueprint, render_template

index = Blueprint('index', __name__)

@index.route('/')
def rootpage():
    return render_template('index.html')
