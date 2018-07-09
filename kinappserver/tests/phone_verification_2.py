import simplejson as json
import unittest
import uuid

import testing.postgresql

import kinappserver
from kinappserver import db, models
from time import sleep


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

    def test_moving_sim_from_once_device_to_another(self):
        """test registration scenarios"""

        resp = self.app.get('/stats/db')
        data = json.loads(resp.data)
        print('db_status: %s' % data)
        self.assertEqual(resp.status_code, 200)


        userid = str(uuid.uuid4())
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

        userid2 = str(uuid.uuid4())
        resp = self.app.post('/user/register',
            data=json.dumps({
                            'user_id': str(userid2),
                            'os': 'android',
                            'device_model': 'samsung8',
                            'device_id': '234234',
                            'time_zone': '05:00',
                            'token': 'fake_token',
                            'app_ver': '1.0'}),
            headers={},
            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        resp = self.app.post('/user/app-launch',
                            data=json.dumps({
                            'app_ver': '1.0'}),
                            headers={USER_ID_HEADER: str(userid)},
                            content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        print('data: %s' % data)
        self.assertEqual(data['config']['phone_verification_enabled'], True)

        # add a bunch of tasks
        task0 = {
            'id': '0',
            'title': 'do you know horses?',
            'desc': 'horses_4_dummies',
            'type': 'questionnaire',
            'price': 1,
            'delay_days': 0,
            'skip_image_test': True,
            'min_to_complete': 2,
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

        resp = self.app.post('/task/add',
                             data=json.dumps({
                                 'task': task0}),
                             headers={},
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        task0['id'] = '1'

        resp = self.app.post('/task/add',
                             data=json.dumps({
                                 'task': task0}),
                             headers={},
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        task0['id'] = '2'

        resp = self.app.post('/task/add',
                             data=json.dumps({
                                 'task': task0}),
                             headers={},
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # user1 updates his phone number to the server after client-side verification
        phone_num = '+9720528802120'
        resp = self.app.post('/user/firebase/update-id-token',
                    data=json.dumps({
                        'token': 'fake-token',
                        'phone_number': phone_num}),
                    headers={USER_ID_HEADER: str(userid)},
                    content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # user 1 fills in the first two tasks

        # get the user's current tasks - expecting task 0
        headers = {USER_ID_HEADER: userid}
        resp = self.app.get('/user/tasks', headers=headers)
        data = json.loads(resp.data)
        print('data: %s' % data)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(data['tasks'][0]['id'], '0')

        # send task results - should succeed
        resp = self.app.post('/user/task/results',
                             data=json.dumps({
                                 'id': '0',
                                 'address': 'GBDUPSZP4APH3PNFIMYMTHIGCQQ2GKTPRBDTPCORALYRYJZJ35O2LOBL',
                                 'results': {'2234': 'werw', '5345': '345345'},
                                 'send_push': False
                             }),
                             headers={USER_ID_HEADER: str(userid)},
                             content_type='application/json')
        print('post task results response: %s' % json.loads(resp.data))
        self.assertEqual(resp.status_code, 200)

        # get the user's current tasks - expecting task 1
        headers = {USER_ID_HEADER: userid}
        resp = self.app.get('/user/tasks', headers=headers)
        data = json.loads(resp.data)
        print('data: %s' % data)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(data['tasks'][0]['id'], '1')

        # send task results - should succeed
        resp = self.app.post('/user/task/results',
                             data=json.dumps({
                                 'id': '1',
                                 'address': 'GBDUPSZP4APH3PNFIMYMTHIGCQQ2GKTPRBDTPCORALYRYJZJ35O2LOBL',
                                 'results': {'2234': 'werw', '5345': '345345'},
                                 'send_push': False
                             }),
                             headers={USER_ID_HEADER: str(userid)},
                             content_type='application/json')
        print('post task results response: %s' % json.loads(resp.data))
        self.assertEqual(resp.status_code, 200)

        # get user 1s current tasks - expecting task_id 2.
        headers = {USER_ID_HEADER: userid}
        resp = self.app.get('/user/tasks', headers=headers)
        data = json.loads(resp.data)
        print('data: %s' % data)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(data['tasks'][0]['id'], '2')
        next_submission_time = data['tasks'][0]['start_date']

        # different user updates his number to the same number, should work - and deactivate the previous user
        print('user 2 updates to the same number as user 1...')
        phone_num = '+9720528802120'
        resp = self.app.post('/user/firebase/update-id-token',
                    data=json.dumps({
                        'token': 'fake-token',
                        'phone_number': phone_num}),
                    headers={USER_ID_HEADER: str(userid2)},
                    content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        print('all users: %s' % models.list_all_users())
        print('all users app data: %s' % models.list_all_users_app_data())
        self.assertEqual(models.list_all_users()[userid]['deactivated'], True)
        self.assertEqual(models.list_all_users()[userid2]['deactivated'], False)

        # get user 1s current tasks - there should be none.
        headers = {USER_ID_HEADER: userid}
        resp = self.app.get('/user/tasks', headers=headers)
        data = json.loads(resp.data)
        print('data: %s' % data)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(data['tasks'], [])
        self.assertEqual(data['reason'], 'user_deactivated')

        # send task results - should fail - user deactivated
        resp = self.app.post('/user/task/results',
                            data=json.dumps({
                            'id': '0',
                            'address': 'GBDUPSZP4APH3PNFIMYMTHIGCQQ2GKTPRBDTPCORALYRYJZJ35O2LOBL',
                            'results': {'2234': 'werw', '5345': '345345'},
                            'send_push': False
                            }),
                            headers={USER_ID_HEADER: str(userid)},
                            content_type='application/json')
        print('post task results response: %s' % json.loads(resp.data))
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(data['reason'], 'user_deactivated')

        # get user 2s current tasks - it should be '2', because the task history was migrated when the user was deactivated
        # and the start time should be the same as was for user 1 pre-migration
        headers = {USER_ID_HEADER: userid2}
        resp = self.app.get('/user/tasks', headers=headers)
        data = json.loads(resp.data)
        print('data: %s' % data)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(data['tasks'][0]['id'], '2')
        self.assertEqual(data['tasks'][0]['start_date'], next_submission_time)

        # send task results - should fail for task id 0
        resp = self.app.post('/user/task/results',
                            data=json.dumps({
                            'id': '0',
                            'address': 'GBDUPSZP4APH3PNFIMYMTHIGCQQ2GKTPRBDTPCORALYRYJZJ35O2LOBL',
                            'results': {'2234': 'werw', '5345': '345345'},
                            'send_push': False
                            }),
                            headers={USER_ID_HEADER: str(userid2)},
                            content_type='application/json')
        print('should fail - task was already submitted')
        print('post task results response: %s' % json.loads(resp.data))
        self.assertEqual(resp.status_code, 400)

        # should fail for task id 1
        resp = self.app.post('/user/task/results',
                            data=json.dumps({
                            'id': '1',
                            'address': 'GBDUPSZP4APH3PNFIMYMTHIGCQQ2GKTPRBDTPCORALYRYJZJ35O2LOBL',
                            'results': {'2234': 'werw', '5345': '345345'},
                            'send_push': False
                            }),
                            headers={USER_ID_HEADER: str(userid2)},
                            content_type='application/json')
        print('should fail - task was already submitted')
        print('post task results response: %s' % json.loads(resp.data))
        self.assertEqual(resp.status_code, 400)

        # should succeed for task id 2
        resp = self.app.post('/user/task/results',
                            data=json.dumps({
                            'id': '2',
                            'address': 'GBDUPSZP4APH3PNFIMYMTHIGCQQ2GKTPRBDTPCORALYRYJZJ35O2LOBL',
                            'results': {'2234': 'werw', '5345': '345345'},
                            'send_push': False
                            }),
                            headers={USER_ID_HEADER: str(userid2)},
                            content_type='application/json')
        print('should succeed...')
        print('post task results response: %s' % json.loads(resp.data))
        self.assertEqual(resp.status_code, 200)

        sleep(5)

        resp = self.app.get('/stats/db')
        data = json.loads(resp.data)
        print('db_status: %s' % data)
        self.assertEqual(resp.status_code, 200)

if __name__ == '__main__':
    unittest.main()
