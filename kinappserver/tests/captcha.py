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

    def test_captcha(self):
        """test storting task reults"""

        cat = {'id': '0',
          'title': 'cat-title',
            'supported_os': 'all',
          'skip_image_test': True,
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

        task3 = {
          'id': '3',
            "cat_id": '0',
            "position": 3,
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

        resp = self.app.post('/task/add',
                            data=json.dumps({
                            'task': task3}),
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
                            'app_ver': '1.2.6'}), # supports captcha
                            headers={},
                            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        userid_old_android = uuid.uuid4()

        # register an android with a token
        resp = self.app.post('/user/register',
                             data=json.dumps({
                                 'user_id': str(userid_old_android),
                                 'os': 'android',
                                 'device_model': 'samsung8',
                                 'device_id': '234234',
                                 'time_zone': '05:00',
                                 'token': 'fake_token',
                                 'app_ver': '1.2.5'}),  # does not support captcha
                             headers={},
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        userid_ios = uuid.uuid4()

        # register an android with a token
        resp = self.app.post('/user/register',
                             data=json.dumps({
                                 'user_id': str(userid_ios),
                                 'os': 'iOS',
                                 'device_model': 'samsung8',
                                 'device_id': '234234',
                                 'time_zone': '05:00',
                                 'token': 'fake_token',
                                 'app_ver': '1.2.6'}),  # does not support captcha
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

        # get the user's current tasks
        headers = {USER_ID_HEADER: userid}
        resp = self.app.get('/user/tasks', headers=headers)
        data = json.loads(resp.data)
        print('data: %s' % data)
        self.assertEqual(resp.status_code, 200)
        print('next task id: %s' % data['tasks']['0'][0]['id'])
        print('next task start date: %s' % data['tasks']['0'][0]['start_date'])
        self.assertEqual(data['tasks']['0'][0]['id'], '0')

        # raise the captcha flag to 0 - should not require captcha on the current task
        models.set_should_solve_captcha(str(userid), 0)

        # send task results - no captcha needed
        resp = self.app.post('/user/task/results',
                            data=json.dumps({
                            'id': '0',
                            'address': 'GCYUCLHLMARYYT5EXJIK2KZJCMRGIKKUCCJKJOAPUBALTBWVXAT4F4OZ',
                            'results': {'2234': 'werw', '5345': '345345'},
                            'send_push': False
                            }),
                            headers={USER_ID_HEADER: str(userid)},
                            content_type='application/json')
        print('post task results response: %s' % json.loads(resp.data))
        self.assertEqual(resp.status_code, 200)  # no captcha needed

        # send task results - captcha needed but not provided - should fail
        resp = self.app.post('/user/task/results',
                            data=json.dumps({
                            'id': '1',
                            'address': 'GCYUCLHLMARYYT5EXJIK2KZJCMRGIKKUCCJKJOAPUBALTBWVXAT4F4OZ',
                            'results': {'2234': 'werw', '5345': '345345'},
                            'send_push': False
                            }),
                            headers={USER_ID_HEADER: str(userid)},
                            content_type='application/json')
        print('post task results response: %s' % json.loads(resp.data))
        self.assertNotEqual(resp.status_code, 200)  #  captcha needed but not provided

        # send task results - captcha needed and provided
        resp = self.app.post('/user/task/results',
                            data=json.dumps({
                            'id': '1',
                            'address': 'GCYUCLHLMARYYT5EXJIK2KZJCMRGIKKUCCJKJOAPUBALTBWVXAT4F4OZ',
                            'results': {'2234': 'werw', '5345': '345345'},
                            'captcha_token': 'asdadasdasdasd',
                            'send_push': False
                            }),
                            headers={USER_ID_HEADER: str(userid)},
                            content_type='application/json')
        print('post task results response: %s' % json.loads(resp.data))
        self.assertEqual(resp.status_code, 200)  # captcha provided


        # raise the captcha flag to 1 - should require captcha on the current task
        models.set_should_solve_captcha(str(userid), 1)

        # send task results - captcha needed but not provided - should fail
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
        self.assertNotEqual(resp.status_code, 200)  # captcha needed but not provided

        # send task results - captcha needed and provided
        resp = self.app.post('/user/task/results',
                             data=json.dumps({
                                 'id': '2',
                                 'address': 'GCYUCLHLMARYYT5EXJIK2KZJCMRGIKKUCCJKJOAPUBALTBWVXAT4F4OZ',
                                 'results': {'2234': 'werw', '5345': '345345'},
                                 'captcha_token': 'asdadasdasdasd',
                                 'send_push': False
                             }),
                             headers={USER_ID_HEADER: str(userid)},
                             content_type='application/json')
        print('post task results response: %s' % json.loads(resp.data))
        self.assertEqual(resp.status_code, 200)  # captcha provided

        res = db.engine.execute("""select captcha_history from user_app_data where user_id='%s'""" % userid)
        history = res.fetchall()[0][0]
        print('captcha history: %s' % history)
        self.assertEqual(len(history), 2)  # 2 captchas in the history

        # lower the captcha flag to -1 - should not require captcha
        models.set_should_solve_captcha(str(userid), -1)

        # send task results - captcha not needed and not provided - should succeed
        resp = self.app.post('/user/task/results',
                             data=json.dumps({
                                 'id': '3',
                                 'address': 'GCYUCLHLMARYYT5EXJIK2KZJCMRGIKKUCCJKJOAPUBALTBWVXAT4F4OZ',
                                 'results': {'2234': 'werw', '5345': '345345'},
                                 'send_push': False
                             }),
                             headers={USER_ID_HEADER: str(userid)},
                             content_type='application/json')
        print('post task results response: %s' % json.loads(resp.data))
        self.assertEqual(resp.status_code, 200)  # captcha needed but not provided


if __name__ == '__main__':
    unittest.main()
