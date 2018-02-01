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

    def test_task_storing(self):
        """test storting and getting tasks"""
        task = { 'title': 'do you know horses?',
                  'desc': 'horses_4_dummies',
                  'type': 'questionnaire',
                  'kin_reward': 2000,
                  'min_to_complete': 2,
                  'tags': ['music',  'crypto', 'movies', 'kardashians', 'horses'],
                  'author': 
                    {'name': 'om-nom-nom-food', 'image_url': 'http://inter.webs/horsie.jpg'},
                  'items': [
                    {
                     'id':'435', 
                     'text':'what animal is this?',
                     'type': 'textimage',
                         'results':[
                                {'id':'235',
                                 'text': 'a horse!', 
                                 'image_url': 'cdn.helllo.com/horse.jpg'},
                                    {'id':'2465436',
                                 'text': 'a cat!', 
                                 'image_url': 'cdn.helllo.com/kitty.jpg'},
                                 ],
                    }]
            }


        resp = self.app.post('/task/add',
                            data=json.dumps({
                            'id': 0,
                            'task': task}),
                            headers={},
                            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        print(model.list_all_task_data())

        # register a user
        userid = uuid.uuid4()
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

        # get the user's current tasks
        resp = self.app.get('/user/tasks?user_id=%s' % userid)
        data = json.loads(resp.data)
        print(data)
        self.assertEqual(resp.status_code, 200)



if __name__ == '__main__':
    unittest.main()
