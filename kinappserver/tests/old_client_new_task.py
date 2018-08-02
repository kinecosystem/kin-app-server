from time import sleep
import unittest
import uuid

import simplejson as json
import testing.postgresql

import kinappserver
from kinappserver import db


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

    def test_old_client(self):
        """test storting task reults"""

        # add a task
        task0 = {
          'id': '0', 
          'title': 'do you know horses?',
          'desc': 'horses_4_dummies',
          'type': 'questionnaire',
          'price': 1,
          'min_to_complete': 2,
          'skip_image_test': True,
          'start_date': '2013-05-11T21:23:58.970460+00:00',
          'tags': ['music', 'crypto', 'movies', 'kardashians', 'horses'],
          'provider': 
            {'name': 'om-nom-nom-food', 'image_url': 'http://inter.webs/horsie.jpg'},
          'items': [
            {
             'id': '435',
             'text': 'what animal is this?',
             'type': 'textimage',
                 'results': [
                        {'id': '235',
                         'text': 'a horse!',
                         'image_url': 'cdn.helllo.com/horse.jpg'},
                            {'id': '2465436',
                         'text': 'a cat!',
                         'image_url': 'cdn.helllo.com/kitty.jpg'},
                         ],
            }]
        }

        task1 = {
          'id': '1',
          'min_client_version_android': '1.0.0',
          'min_client_version_ios': '1.0.0',
          'title': 'do you know horses?',
          'desc': 'horses_4_dummies',
          'type': 'questionnaire',
          'price': 1,
          'skip_image_test': True,
          'min_to_complete': 2,
          'start_date': '2013-05-11T21:23:58.970460+00:00',
          'tags': ['music',  'crypto', 'movies', 'kardashians', 'horses'],
          'provider': 
            {'name': 'om-nom-nom-food', 'image_url': 'http://inter.webs/horsie.jpg'},
          'items': [
            {
             'id': '435',
             'text': 'what animal is this?',
             'type': 'textimage',
                 'results': [
                        {'id': '235',
                         'text': 'a horse!',
                         'image_url': 'cdn.helllo.com/horse.jpg'},
                            {'id': '2465436',
                         'text': 'a cat!',
                         'image_url': 'cdn.helllo.com/kitty.jpg'},
                         ],
            }]
        }

        task2 = {
          'id': '2',
          'min_client_version_android': '1.0.0',
          'min_client_version_ios': '1.0.0',
          'title': 'do you know horses?',
          'desc': 'horses_4_dummies',
          'type': 'questionnaire',
          'price': 1,
          'skip_image_test': True,
          'min_to_complete': 2,
          'start_date': '2013-05-11T21:23:58.970460+00:00',
          'tags': ['music',  'crypto', 'movies', 'kardashians', 'horses'],
          'provider':
            {'name': 'om-nom-nom-food', 'image_url': 'http://inter.webs/horsie.jpg'},
          'items': [
            {
             'id': '435',
             'text': 'what animal is this?',
             'type': 'textimage',
                 'results': [
                        {'id': '235',
                         'text': 'a horse!',
                         'image_url': 'cdn.helllo.com/horse.jpg'},
                            {'id': '2465436',
                         'text': 'a cat!',
                         'image_url': 'cdn.helllo.com/kitty.jpg'},
                         ],
            }]
        }


        resp = self.app.post('/task/add',
                            data=json.dumps({
                            'task': task0}),
                            headers={},
                            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        resp = self.app.post('/task/add',
                            data=json.dumps({
                            'task': task1}),
                            headers={},
                            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        resp = self.app.post('/task/add',
                            data=json.dumps({
                            'task': task2}),
                            headers={},
                            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # set the delay_days on all the tasks to zero
        resp = self.app.post('/task/delay_days',
                            data=json.dumps({
                            'days': 0}),
                            headers={},
                            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        userid_ios = uuid.uuid4()
        userid_android = uuid.uuid4()

        # register an android with a token
        resp = self.app.post('/user/register',
                            data=json.dumps({
                            'user_id': str(userid_android),
                            'os': 'android',
                            'device_model': 'samsung8',
                            'device_id': '234234',
                            'time_zone': '05:00',
                            'token': 'fake_token',
                            'app_ver': '0.5'}),
                            headers={},
                            content_type='application/json')
        self.assertEqual(resp.status_code, 200)


        # register an ios with a token
        resp = self.app.post('/user/register',
                            data=json.dumps({
                            'user_id': str(userid_ios),
                            'os': 'iOS',
                            'device_model': 'samsung8',
                            'device_id': '234234',
                            'time_zone': '05:00',
                            #'token': 'fake_token', # no push in tests
                            'app_ver': '0.5'}),
                            headers={},
                            content_type='application/json')
        data = json.loads(resp.data)
        print('data: %s' % data)
        self.assertEqual(resp.status_code, 200)

        sleep(1)

        # get the user's current tasks
        headers = {USER_ID_HEADER: userid_ios}
        resp = self.app.get('/user/tasks', headers=headers)
        data = json.loads(resp.data)
        print('data: %s' % data)
        self.assertEqual(resp.status_code, 200)
        print('next task id: %s' % data['tasks'][0]['id'])
        print('next task start date: %s' % data['tasks'][0]['start_date'])
        self.assertEqual(data['tasks'][0]['id'], '0')


        # send task results for first task - ios
        resp = self.app.post('/user/task/results',
                            data=json.dumps({
                            'id': '0',
                            'address': 'GCYUCLHLMARYYT5EXJIK2KZJCMRGIKKUCCJKJOAPUBALTBWVXAT4F4OZ',
                            'results': {'2234': 'werw', '5345': '345345'},
                            'send_push': False
                            }),
                            headers={USER_ID_HEADER: str(userid_ios)},
                            content_type='application/json')
        print('post task results response: %s' % json.loads(resp.data))
        self.assertEqual(resp.status_code, 200)
        sleep(8) # give the thread enough time to complete before the db connection is shutdown


        # get user tx history - should have 1 items
        resp = self.app.get('/user/transactions', headers={USER_ID_HEADER: str(userid_ios)})
        self.assertEqual(resp.status_code, 200)
        print('txs: %s' % json.loads(resp.data))
        self.assertNotEqual(json.loads(resp.data)['txs'], [])

        # get the user's current tasks - should be empty - ios
        headers = {USER_ID_HEADER: userid_ios}
        resp = self.app.get('/user/tasks', headers=headers)
        data = json.loads(resp.data)
        print('data: %s' % data)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(data['tasks'], [])


        # get the user's current tasks
        headers = {USER_ID_HEADER: userid_android}
        resp = self.app.get('/user/tasks', headers=headers)
        data = json.loads(resp.data)
        print('data: %s' % data)
        self.assertEqual(resp.status_code, 200)
        print('next task id: %s' % data['tasks'][0]['id'])
        print('next task start date: %s' % data['tasks'][0]['start_date'])
        self.assertEqual(data['tasks'][0]['id'], '0')


        # send task results for first task - android
        resp = self.app.post('/user/task/results',
                            data=json.dumps({
                            'id': '0',
                            'address': 'GCYUCLHLMARYYT5EXJIK2KZJCMRGIKKUCCJKJOAPUBALTBWVXAT4F4OZ',
                            'results': {'2234': 'werw', '5345': '345345'},
                            'send_push': False
                            }),
                            headers={USER_ID_HEADER: str(userid_android)},
                            content_type='application/json')
        print('post task results response: %s' % json.loads(resp.data))
        self.assertEqual(resp.status_code, 200)
        sleep(8) # give the thread enough time to complete before the db connection is shutdown


        # get user tx history - should have 1 items
        resp = self.app.get('/user/transactions', headers={USER_ID_HEADER: str(userid_android)})
        self.assertEqual(resp.status_code, 200)
        print('txs: %s' % json.loads(resp.data))
        self.assertNotEqual(json.loads(resp.data)['txs'], [])

        # get the user's current tasks - should be empty - android
        headers = {USER_ID_HEADER: userid_android}
        resp = self.app.get('/user/tasks', headers=headers)
        data = json.loads(resp.data)
        print('data: %s' % data)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(data['tasks'], [])


        sleep(8)  # give the thread enough time to complete before the db connection is shutdown


if __name__ == '__main__':
    unittest.main()
