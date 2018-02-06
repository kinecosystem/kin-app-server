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
from kinappserver import db, config, model

USER_ID_HEADER = "X-USERID"

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

    def test_register(self):
        """test registration scenarios"""

        # android
        resp = self.app.post('/user/register',
            data=json.dumps({
                            'os': 'android',
                            'device_model': 'samsung8',
                            'device_id': '234234',
                            'time_zone': '+05:00',
                            'token':'fake_token'}),
            headers={USER_ID_HEADER: str(uuid.uuid4())},
            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # ios
        resp = self.app.post('/user/register',
            data=json.dumps({
                            'os': 'iOS',
                            'device_model': 'samsung8',
                            'device_id': '234234',
                            'time_zone': '+05:00',
                            'token':'fake_token'}),
            headers={USER_ID_HEADER: str(uuid.uuid4())},
            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # no push token. should succeed.
        userid = uuid.uuid4()
        resp = self.app.post('/user/register',
            data=json.dumps({
                            'os': 'iOS',
                            'device_model': 'samsung8',
                            'device_id': '234234',
                            'time_zone': '+05:00'}),
            headers={USER_ID_HEADER: str(userid)},
            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # re-use userid - should fail
        resp = self.app.post('/user/register',
            data=json.dumps({
                            'os': 'iOS',
                            'device_model': 'samsung8',
                            'device_id': '234234',
                            'time_zone': '+05:00'}),
            headers={USER_ID_HEADER: str(userid)},
            content_type='application/json')
        self.assertEqual(resp.status_code, 400)
        print(json.loads(resp.data))

        print(model.list_all_users())
        assert(model.user_exists(userid))
        assert(not model.user_exists(uuid.uuid4()))

        # windows phone. should fail.
        userid = uuid.uuid4()
        resp = self.app.post('/user/register',
            data=json.dumps({
                            'os': 'win',
                            'device_model': 'samsung8',
                            'device_id': '234234',
                            'time_zone': '+05:00'}),
            headers={USER_ID_HEADER: str(userid)},
            content_type='application/json')
        self.assertEqual(resp.status_code, 400)
        assert(not model.user_exists(userid))

        # invalid uuid. should fail
        resp = self.app.post('/user/register',
            data=json.dumps({
                            'os': 'iOS',
                            'device_model': 'samsung8',
                            'device_id': '234234',
                            'time_zone': '+05:00'}),
            headers={USER_ID_HEADER: str('invaliduuid')},
            content_type='application/json')
        self.assertEqual(resp.status_code, 400)
        print(json.loads(resp.data))

if __name__ == '__main__':
    unittest.main()
