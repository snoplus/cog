'''The CouchDB interface'''

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
        last_seq = 0
        filter_name = self.database.name + '/task'
 
        while True:
            changes = self.database.changes(feed='continuous', heartbeat=30000,
                                            filter=filter_name, since=last_seq)
 
            try:
                for change in changes:
                    doc_id = change['id']
                    if (doc_id in self.database and
                        'started' not in self.database[doc_id] and
                        'queued' not in self.database[doc_id]):
                        last_seq = change['seq'] + 1
                        yield doc_id
 
            except couchdb.http.ResourceNotFound:
                print 'get_tasks: Caught couchdb.http.ResourceNotFound'

