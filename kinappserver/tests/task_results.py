from time import sleep
import unittest
import uuid

import simplejson as json
import testing.postgresql

import kinappserver
from kinappserver import db, models

import logging as log
log.getLogger().setLevel(log.INFO)


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
        """test storting task results"""

        for cat_id in range(2):
            cat = {'id': str(cat_id),
              'title': 'cat-title',
                   'supported_os': 'all',
                   "skip_image_test": True,
              'ui_data': {'color': "#123",
                          'image_url': 'https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png',
                          'header_image_url': 'https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png'}}

            resp = self.app.post('/category/add',
                                data=json.dumps({
                                'category': cat}),
                                headers={},
                                content_type='application/json')
            self.assertEqual(resp.status_code, 200)

        # add a task
        task0 = {
          'id': '0',
            "cat_id": '0',
            "position": 0,
          'title': 'do you know horses?',
          'desc': 'horses_4_dummies',
          'type': 'questionnaire',
          'price': 1,
          'skip_image_test': True,
          'min_to_complete': 2,
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
            "cat_id": '0',
            "position": 1,
          'title': 'do you know horses?',
          'desc': 'horses_4_dummies',
          'type': 'questionnaire',
          'price': 1,
          'skip_image_test': True,
          'min_to_complete': 2,
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
            "cat_id": '0',
            "position": 2,
          'title': 'do you know horses?',
          'desc': 'horses_4_dummies',
          'type': 'questionnaire',
          'price': 1,
          'skip_image_test': True,
          'min_to_complete': 2,
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

        task2['position'] = 0
        task2['id'] = '3'
        task2['cat_id'] = '1'
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

        userid = uuid.uuid4()

        # register an android with a token
        resp = self.app.post('/user/register',
                            data=json.dumps({
                            'user_id': str(userid),
                            'os': 'android',
                            'device_model': 'samsung8',
                            'device_id': '234234',
                            'time_zone': '05:00',
                            'token': 'fake_token',
                            'app_ver': '2.0'}),
                            headers={},
                            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        db.engine.execute("""update public.push_auth_token set auth_token='%s' where user_id='%s';""" % (str(userid), str(userid)))

        resp = self.app.post('/user/auth/ack',
                             data=json.dumps({
                                 'token': str(userid)}),
                             headers={USER_ID_HEADER: str(userid)},
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        sleep(1)

        self.assertEqual(0, models.count_completed_tasks(str(userid)))

        print('count_immediate_tasks before first submission: %s' % models.count_immediate_tasks(str(userid)))

        # get the user's current tasks
        headers = {USER_ID_HEADER: userid}
        resp = self.app.get('/user/tasks', headers=headers)
        data = json.loads(resp.data)
        print('data: %s' % data)
        self.assertEqual(resp.status_code, 200)
        print('next task id: %s' % data['tasks']['0'][0]['id'])
        print('next task start date: %s' % data['tasks']['0'][0]['start_date'])
        self.assertEqual(data['tasks']['0'][0]['id'], '0')
        task_memo = data['tasks']['0'][0]['memo']
        print('next task memo: %s' % task_memo)

        # get the user's current tasks for category 0
        headers = {USER_ID_HEADER: userid}
        resp = self.app.get('/user/category/0/tasks', headers=headers)
        data = json.loads(resp.data)
        print('data: %s' % data)
        self.assertEqual(resp.status_code, 200)
        print('next task id: %s' % data['tasks'][0]['id'])
        print('next task start date: %s' % data['tasks'][0]['start_date'])
        self.assertEqual(data['tasks'][0]['id'], '0')

        # get the user's current tasks for category 1
        headers = {USER_ID_HEADER: userid}
        resp = self.app.get('/user/category/1/tasks', headers=headers)
        data = json.loads(resp.data)
        print('data: %s' % data)
        self.assertEqual(resp.status_code, 200)
        print('next task id: %s' % data['tasks'][0]['id'])
        print('next task start date: %s' % data['tasks'][0]['start_date'])
        self.assertEqual(data['tasks'][0]['id'], '3')


        # send task results
        resp = self.app.post('/user/task/results',
                            data=json.dumps({
                            'id': '0',
                            'address': 'GCYUCLHLMARYYT5EXJIK2KZJCMRGIKKUCCJKJOAPUBALTBWVXAT4F4OZ',
                            'results': {'2234': 'werw', '5345': '345345'},
                            'send_push': False
                            }),
                            headers={USER_ID_HEADER: str(userid)},
                            content_type='application/json')
        data = json.loads(resp.data)
        print('post task results response: %s' % data)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(data['memo'], task_memo)

        sleep(8)  # give the thread enough time to complete before the db connection is shutdown


        print('count_immediate_tasks after first submission: %s' % models.count_immediate_tasks(str(userid)))

        # get user tx history - should have 1 items
        resp = self.app.get('/user/transactions', headers={USER_ID_HEADER: str(userid)})
        self.assertEqual(resp.status_code, 200)
        print('txs: %s' % json.loads(resp.data))
        self.assertNotEqual(json.loads(resp.data)['txs'], [])

        # get the user's current tasks
        headers = {USER_ID_HEADER: userid}
        resp = self.app.get('/user/tasks', headers=headers)
        data = json.loads(resp.data)
        print('data: %s' % data)
        self.assertEqual(resp.status_code, 200)
        print('next task id: %s' % data['tasks']['0'][0]['id'])
        print('next task start date: %s' % data['tasks']['0'][0]['start_date'])
        
        self.assertEqual(data['tasks']['0'][0]['id'], '1')

        # set the delay_days on all the tasks to two
        resp = self.app.post('/task/delay_days',
                            data=json.dumps({
                            'days': 2}),
                            headers={},
                            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # send task results - should be accepted as there's no delay)
        resp = self.app.post('/user/task/results',
                            data=json.dumps({
                            'id': '1',
                            'address': 'GCYUCLHLMARYYT5EXJIK2KZJCMRGIKKUCCJKJOAPUBALTBWVXAT4F4OZ',
                            'results': {'2234': 'werw', '5345': '345345'},
                            'captcha_token': '23234',
                            'send_push': False
                            }),
                            headers={USER_ID_HEADER: str(userid)},
                            content_type='application/json')

        print('data: %s' % data)
        self.assertEqual(resp.status_code, 200)

        sleep(10)

        # get the user's current tasks
        headers = {USER_ID_HEADER: userid}
        resp = self.app.get('/user/tasks', headers=headers)
        data = json.loads(resp.data)
        self.assertEqual(resp.status_code, 200)
        print('next task id in cat_id 0: %s' % data['tasks']['0'][0]['id'])
        print('next task start date: %s' % data['tasks']['0'][0]['start_date'])

        self.assertEqual(data['tasks']['0'][0]['id'], '2')
        self.assertEqual(data['tasks']['1'][0]['id'], '3')

        resp = self.app.post('/user/task/results',
                            data=json.dumps({
                            'id': '3',
                            'address': 'GCYUCLHLMARYYT5EXJIK2KZJCMRGIKKUCCJKJOAPUBALTBWVXAT4F4OZ',
                            'results': {'2234': 'werw', '5345': '345345'},
                            'send_push': False
                            }),
                            headers={USER_ID_HEADER: str(userid)},
                            content_type='application/json')

        # the next start date should be at least 24 hours into the future:
        import arrow

        future = arrow.get(data['tasks']['0'][0]['start_date'])
        now = arrow.utcnow()
        self.assertEqual((future-now).total_seconds() / 3600 > 24, True)

        # send task results before the next task is due (due to cooldown)
        resp = self.app.post('/user/task/results',
                            data=json.dumps({
                            'id': '2',
                            'address': 'GCYUCLHLMARYYT5EXJIK2KZJCMRGIKKUCCJKJOAPUBALTBWVXAT4F4OZ',
                            'results': {'2234': 'werw', '5345': '345345'},
                            'send_push': False
                            }),
                            headers={USER_ID_HEADER: str(userid)},
                            content_type='application/json')
        print('post task results response: %s' % json.loads(resp.data))
        self.assertEqual(resp.status_code, 403)


        print('total completed tasks for user_id: %s ' % models.count_completed_tasks(str(userid)))
        self.assertEqual(3, models.count_completed_tasks(str(userid)))

        print('count_immediate_tasks: %s' % models.count_immediate_tasks(str(userid)))
        print('get_next_tasks_for_user: %s' % models.get_next_tasks_for_user(str(userid)))
        models.count_missing_txs()

        sleep(8)  # give the thread enough time to complete before the db connection is shutdown



if __name__ == '__main__':
    unittest.main()
