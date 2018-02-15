import base64
import simplejson as json
from json import dumps as json_stringify
from time import mktime, sleep
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

    def test_task_results(self):
        """test storting task reults"""

        # add a task
        task = {
          'task_id': 1, 
          'title': 'do you know horses?',
          'desc': 'horses_4_dummies',
          'type': 'questionnaire',
          'kin_reward': 1,
          'min_to_complete': 2,
          'start_date': '2013-05-11T21:23:58.970460+00:00',
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
                            'task': task}),
                            headers={},
                            content_type='application/json')
        self.assertEqual(resp.status_code, 200)    


        userid = uuid.uuid4()

        # register an android with a token
        resp = self.app.post('/user/register',
                            data=json.dumps({
                            'user_id': str(userid),
                            'os': 'android',
                            'device_model': 'samsung8',
                            'device_id': '234234',
                            'time_zone': '+05:00',
                            'token':'fake_token',
                            'app_ver': '1.0'}),
                            headers={},
                            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        #model.send_push_tx_completed(str(userid), "fake_tx_hash", 0, 1)

        # send task results
        resp = self.app.post('/user/task/results',
                            data=json.dumps({
                            'id':'1',
                            'address':'GBDUPSZP4APH3PNFIMYMTHIGCQQ2GKTPRBDTPCORALYRYJZJ35O2LOBL',
                            'results':{'2234':'werw','5345':'345345'},
                            'send_push': False
                            }),
                            headers={USER_ID_HEADER: str(userid)},
                            content_type='application/json')
        print('task_results: %s' % json.loads(resp.data))
        self.assertEqual(resp.status_code, 200)
        sleep(5) # give the thread enough time to complete before the db connection is shutdown

        print(model.list_all_users_results_data())

if __name__ == '__main__':
    unittest.main()
