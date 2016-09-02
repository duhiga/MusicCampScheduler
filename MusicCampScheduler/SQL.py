"""

This application is intended to use MySQL as a backend. Feel free to replace the code below with a method of
connecting to any other database. All you really need is code that executes a given SQL query on the database
and returns a 2 dimensional list back.

"""
from debug import *
import MySQLdb
import untangle

obj = untangle.parse('config.xml')

def sql(query):
    try:
        log2('executing query: %s' % query)
        log2('DB Host: %s' % obj.root.sql['host'])
        db = MySQLdb.connect(host=obj.root.sql['host'], user=obj.root.sql['user'], passwd=obj.root.sql['password'], db=obj.root.sql['database']) #connect to database
        cur = db.cursor() #initiate a query cursor
        cur.execute(query) #execute the query
        data = cur.fetchall() #fetch all that match the query and store in data array
        log2('Printing output of query:')
        log2(data)
        db.close() #close the connection
        return data #return the results of the query
    except Exception as ex:
        log1('Failed to execute query with exception: %s:' % ex)
        log1(query)
        db.close()
        return 'error'


