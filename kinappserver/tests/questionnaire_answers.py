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


class Tester(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        pass

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

    def test_questionnaire_answers(self):
        """test storting questionnaire answers"""
        userid = uuid.uuid4()

        # register an android with a token
        resp = self.app.post('/user/register',
                            data=json.dumps({
                            'user_id': str(userid),
                            'os': 'android',
                            'device_model': 'samsung8',
                            'device_id': '234234',
                            'time_zone': '+05:00',
                            'token':'fake_token'}),
                            headers={},
                            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # update the token
        resp = self.app.post('/user/quest/answers',
                            data=json.dumps({
                            'user_id': str(userid),
                            'id':'1',
                            'address':'my_address',
                            'answers':{'2234':'werw','5345':'345345'}
                            }),
                            headers={},
                            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        print(model.list_all_users_answers_data())

if __name__ == '__main__':
    unittest.main()
