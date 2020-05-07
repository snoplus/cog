'''The CouchDB interface'''

import time
import couchdb

class CouchDB(object):
    '''Interface to a CouchDB database.

    Perhaps this should be a subclass of couchdb.client.Database.

    :param host: The server hostname
    :param dbname: Name of the database to access
    :param username: CouchDB username
    :param password: CouchDB password
    '''
    def __init__(self, host, dbname, username=None, password=None):
        self.host = host
        self.dbname = dbname
        self.username = username
        self.password = password

        self.database = CouchDB.connect(self.host, self.dbname,
                                        self.username, self.password)

    @staticmethod
    def connect(host, dbname, username, password):
        '''Connect to a database on a CouchDB server.
 
        :param host: The server hostname
        :param dbname: Name of the database to access
        :param credentials: A (username, password) tuple
        :returns: A couchdb.client.Database object
        '''
        couch = couchdb.Server(host)
 
        if username is not None and password is not None:
            couch.resource.credentials = (username, password)
 
        return couch[dbname]

    def get_tasks(self):
        '''Watch the changes feed for new tasks.
 
        :returns: Generator of changed document IDs
        '''
 
        while True:
            rows = self.database.view('pytunia/pending_tasks')
            try:
                for row in rows:
                    yield row.id
 
            except couchdb.http.ResourceNotFound:
                print 'get_tasks: Caught couchdb.http.ResourceNotFound'

	    except ValueError as e:
                print 'get_tasks: Caught ValueError:', e

            time.sleep(60)

