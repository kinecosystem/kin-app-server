import unittest
import uuid

import simplejson as json
import testing.postgresql


import kinappserver
from kinappserver import db, models


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

    def test_truex_task(self):
        """test storting and getting tasks"""
        task0 = {  'id': 0,
                  'title': 'do you know horses?',
                  'desc': 'horses_4_dummies',
                  'type': 'nottruex',
                  'price': 2000,
                  'skip_image_test': True,
                  'min_to_complete': 2,
                  'start_date': '2013-05-11T21:23:58.970460+00:00',
                  'tags': ['music',  'crypto', 'movies', 'kardashians', 'horses'],
                  'provider': 
                    {'name': 'om-nom-nom-food', 'image_url': 'https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png'},
                  'items': []
            }

        task1 = {  'id': 1,
                  'title': 'do you know horses?',
                  'desc': 'horses_4_dummies',
                  'type': 'truex',
                  'price': 2000,
                  'skip_image_test': True,
                  'min_to_complete': 2,
                  'start_date': '2013-05-11T21:23:58.970460+00:00',
                  'tags': ['music',  'crypto', 'movies', 'kardashians', 'horses'],
                  'provider':
                    {'name': 'om-nom-nom-food', 'image_url': 'https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png'},
                  'items': []
            }


        task2 = {  'id': 2,
                  'title': 'do you know horses?',
                  'desc': 'horses_4_dummies',
                  'type': 'truex',
                  'price': 2000,
                  'skip_image_test': True,
                  'min_to_complete': 2,
                  'start_date': '2013-05-11T21:23:58.970460+00:00',
                  'tags': ['music',  'crypto', 'movies', 'kardashians', 'horses'],
                  'provider':
                    {'name': 'om-nom-nom-food', 'image_url': 'https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png'},
                  'items': []
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

        print(models.list_all_task_data())

        # set the delay_days on all the tasks to two
        resp = self.app.post('/task/delay_days',
                            data=json.dumps({
                            'days': 0}),
                            headers={},
                            content_type='application/json')
        self.assertEqual(resp.status_code, 200)


        # register a user
        userid = uuid.uuid4()
        resp = self.app.post('/user/register',
            data=json.dumps({
                            'user_id': str(userid),
                            'os': 'android',
                            'device_model': 'samsung8',
                            'device_id': '234234',
                            'time_zone': '05:00',
                            'token': 'fake_token',
                            'app_ver': '1.0'}),
            headers={},
            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # get the user's current tasks
        headers = {USER_ID_HEADER: userid}
        resp = self.app.get('/user/tasks', headers=headers)
        data = json.loads(resp.data)
        print(data)
        self.assertEqual(resp.status_code, 200)

        # post some fictitious answers

        # set the delay_days on all the tasks to two
        resp = self.app.post('/task/delay_days',
                            data=json.dumps({
                            'days': 0}),
                            headers={},
                            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        print('getting the truex activity for a non truex task - should fail')
        # get the truex activity - should fail
        resp = self.app.get('/truex/activity',
                            headers={USER_ID_HEADER: str(userid)})
        self.assertNotEqual(resp.status_code, 200)

        print('submitting the first task...')
        # send task results - should be accepted as there's no delay for the first task)
        resp = self.app.post('/user/task/results',
                            data=json.dumps({
                            'id': '0',
                            'address': 'GBDUPSZP4APH3PNFIMYMTHIGCQQ2GKTPRBDTPCORALYRYJZJ35O2LOBL',
                            'results': {'2234': 'werw', '5345': '345345'},
                            'send_push': False
                            }),
                            headers={USER_ID_HEADER: str(userid)},
                            content_type='application/json')

        print('2nd task: get the activity - should work')
        # get the truex activity - should succeed
        resp = self.app.get('/truex/activity',
                            headers={USER_ID_HEADER: str(userid)})
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        print(data)

        # set the delay_days on all the tasks to two
        resp = self.app.post('/task/delay_days',
                            data=json.dumps({
                            'days': 2}),
                            headers={},
                            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        resp = self.app.post('/user/task/results',
                            data=json.dumps({
                            'id': '1',
                            'address': 'GBDUPSZP4APH3PNFIMYMTHIGCQQ2GKTPRBDTPCORALYRYJZJ35O2LOBL',
                            'results': {'2234': 'werw', '5345': '345345'},
                            'send_push': False
                            }),
                            headers={USER_ID_HEADER: str(userid)},
                            content_type='application/json')

        # get the user's current tasks
        headers = {USER_ID_HEADER: userid}
        resp = self.app.get('/user/tasks', headers=headers)
        data = json.loads(resp.data)
        print(data)
        self.assertEqual(resp.status_code, 200)

        print('getting the truex activity prematurely - should fail')
        # get the truex activity - should fail
        resp = self.app.get('/truex/activity',
                            headers={USER_ID_HEADER: str(userid)})
        self.assertNotEqual(resp.status_code, 200)


if __name__ == '__main__':
    unittest.main()
