import base64
import simplejson as json
from json import dumps as json_stringify
from time import mktime
from datetime import datetime
import unittest
from unittest import mock
import uuid


import mockredis
import redis
import testing.postgresql
from flask import Flask

import kinappserver
from kinappserver import db, config




class Tester(unittest.TestCase):

    def setUp(self):
        #overwrite the db name, dont interfere with stage db data
        self.postgresql = testing.postgresql.Postgresql()
        kinappserver.app.config['SQLALCHEMY_DATABASE_URI'] = self.postgresql.url()
        kinappserver.app.testing = True
        self.app = kinappserver.app.test_client()
        db.drop_all()
        db.create_all()


    def tearDown(self):
        self.postgresql.stop()

    def test_health(self):
        """a simple test for the health endpoint"""
        resp = self.app.get('health')
        data = json.loads(resp.data)
        assert data['status']=='ok'

    @mock.patch('redis.StrictRedis', mockredis.mock_redis_client)
    def test_flow(self):
        '''
        '''
        print('starting the test flow...')
        print(config)
        if not config.DEBUG:
            print('refusing to run this code on PROD.')
            return False
        db.drop_all()
        db.create_all()
        r = redis.StrictRedis(host='0.0.0.0', port=6379, db=0)
        r.set('foo', 'bar')

if __name__ == '__main__':
    unittest.main()
