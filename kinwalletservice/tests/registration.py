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

import kinwalletservice
from kinwalletservice import db, config




class Tester(unittest.TestCase):

    def setUp(self):
        #overwrite the db name, dont interfere with stage db data
        self.postgresql = testing.postgresql.Postgresql()
        kinwalletservice.app.config['SQLALCHEMY_DATABASE_URI'] = self.postgresql.url()
        kinwalletservice.app.testing = True
        self.app = kinwalletservice.app.test_client()
        db.drop_all()
        db.create_all()


    def tearDown(self):
        self.postgresql.stop()

    def test_register(self):
        """test registration scenarios"""

        # android
        userid = uuid.uuid4()
        resp = self.app.post('/user/register',
            data=json.dumps({'os': 'android',
                            'device_model': 'samsung8',
                            'device_id': '234234',
                            'time_zone': '+05:00',
                            'token':'fake_token'}),
            headers={'x-userid': userid},
            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # ios
        userid = uuid.uuid4()
        resp = self.app.post('/user/register',
            data=json.dumps({'os': 'ios',
                            'device_model': 'samsung8',
                            'device_id': '234234',
                            'time_zone': '+05:00',
                            'token':'fake_token'}),
            headers={'x-userid': userid},
            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # no push token. should succeed.
        userid = uuid.uuid4()
        resp = self.app.post('/user/register',
            data=json.dumps({'os': 'ios',
                            'device_model': 'samsung8',
                            'device_id': '234234',
                            'time_zone': '+05:00'}),
            headers={'x-userid': userid},
            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # windows phone. should fail.
        userid = uuid.uuid4()
        resp = self.app.post('/user/register',
            data=json.dumps({'os': 'win',
                            'device_model': 'samsung8',
                            'device_id': '234234',
                            'time_zone': '+05:00'}),
            headers={'x-userid': userid},
            content_type='application/json')
        self.assertEqual(resp.status_code, 400)

if __name__ == '__main__':
    unittest.main()
