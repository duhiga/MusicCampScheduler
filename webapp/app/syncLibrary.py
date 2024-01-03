import gspread
from .DBSetup import *
from .config import *
from pathlib import Path

def get_column_names(model):
    # Retrieve column names from an SQLAlchemy model
    return [column.name for column in model.__table__.columns]

def updateRecord(record, data_dict):
    for key, value in data_dict.items():
        if (value != ''):
            setattr(record, key, value)

def pushLibrary(google_sheet_url, google_account_key_name, session):

    log('Connecting to MusicLibrary google sheet')
    # Query all rows from the "musics" table
    musics_data = session.query(music).all()

    # Authenticate with Google Sheets
    google_account_key_path = Path(__file__).with_name(google_account_key_name)
    gc = gspread.service_account(filename=google_account_key_path)

    # Open the Google Sheet by URL
    sh = gc.open_by_url(google_sheet_url)

    # Select the first (and only) worksheet
    worksheet = sh.get_worksheet(0)

    log('Connected to MusicLibrary google sheet')

    log('Exporting database to google sheet')
    # Clear existing data in the sheet
    worksheet.clear()

    # Write headers to the sheet
    headers = get_column_names(music)
    worksheet.append_row(headers)

    rows_data = [[getattr(music_row, column) for column in headers] for music_row in musics_data]
    worksheet.append_rows(rows_data)

def pullLibrary(google_sheet_url, google_account_key_name, session):

    log('Connecting to MusicLibrary google sheet')
    # Authenticate with Google Sheets using the service account key
    google_account_key_path = Path(__file__).with_name(google_account_key_name)
    gc = gspread.service_account(filename=google_account_key_path)

    # Open the Google Sheet by URL
    sh = gc.open_by_url(google_sheet_url)

    # Select the first (and only) worksheet
    worksheet = sh.get_worksheet(0)

    log('Connected to MusicLibrary google sheet')

    # Retrieve data from the Google Sheet
    google_sheet_data = worksheet.get_all_records()

    # Retrieve column names from the SQLAlchemy model
    model_column_names = get_column_names(music)

    log('Importing records from google sheets to database')
    # Update SQLAlchemy table based on Google Sheet data
    for google_sheet_row in google_sheet_data:
        # Create a dictionary with column name as key and Google Sheet value
        data_dict = {col: google_sheet_row.get(col, None) for col in model_column_names}
        
        # Check if an existing record with the same primary key exists
        if isinstance(data_dict['musicid'], int):
            existing_record = session.query(music).filter_by(musicid=data_dict['musicid']).first()
            if existing_record:
                updateRecord(existing_record, data_dict)
            else:
                new_record = music()
                updateRecord(new_record, data_dict)
                session.add(new_record)
        else:
            new_record = music()
            updateRecord(new_record, data_dict)
            session.add(new_record)