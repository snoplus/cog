'''Main server functions and event loop.'''

from cog import db

def serve_forever(database, cluster):
    '''Run the server.

    Watch the changes feed of `database` for new tasks, and start them running
    on the cluster.

    :param database: couchdb.client.Database object to watch
    :param cluster: Cluster object defining the cluster to run jobs on
    '''
    tasks = database.get_tasks()  # infinite generator

    for doc_id in tasks:
        print doc_id
        cluster.submit_task(database, database.database[doc_id])

