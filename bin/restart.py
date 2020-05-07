#!/usr/bin/env python2

import json
import cog.db
import argparse


parser = argparse.ArgumentParser('Rerun cog tasks')
parser.add_argument('config',help='Config file for database')
parser.add_argument('status',help='The state of the jobs to reset')
parser.add_argument('-n','--newer-than',default=0,type=float,help='ignore jobs created before this unix time')

args = parser.parse_args()

with open(args.config, 'r') as f:
    configuration = json.load(f)

db_config = configuration['couchdb']
host = db_config['host']
dbname = db_config['dbname']
username = db_config.get('username', None)
password = db_config.get('password', None)

couchdb = cog.db.CouchDB(host, dbname, username, password)
db = couchdb.database

pending = db.view('pytunia/'+args.status+'_tasks',start_key=args.newer_than,ascending=True)

clear_fields = ['queued','started','completed']
batch = []
for result in pending:
    print result.id
    doc = db[result.id] 
    for field in clear_fields:
        if field in doc:
            del doc[field]
    batch.append(doc)
    if len(batch) > 100:
        db.update(batch)
        batch = []
if len(batch) > 0:
    db.update(batch)

