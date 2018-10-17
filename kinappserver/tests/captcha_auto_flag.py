from time import sleep
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

    def test_captcha_auto_flag(self):
        """test storting task reults"""

        cat = {'id': '0',
          'title': 'cat-title',
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
        task = {
          'id': '0',
            'position': 0,
            'cat_id': '0',
          'title': 'do you know horses?',
          'desc': 'horses_4_dummies',
          'type': 'questionnaire',
          'price': 1,
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


        for i in range(0,20):
            task['id'] = i
            task['position'] = i
            resp = self.app.post('/task/add',
                                data=json.dumps({
                                'task': task}),
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

        db.engine.execute("""update public.push_auth_token set auth_token='%s' where user_id='%s';""" % (str(userid), str(userid)))

        resp = self.app.post('/user/auth/ack',
                             data=json.dumps({
                                 'token': str(userid)}),
                             headers={USER_ID_HEADER: str(userid)},
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)


        # send task results for task 0 - will raise the captcha flag to 1 for the next task
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
        self.assertEqual(resp.status_code, 200)  # no captcha provided
        data = json.loads(resp.data)
        self.assertEqual(data['show_captcha'], True)


        # send task results for task 1 - dont provide captcha, should not work
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
        self.assertNotEqual(resp.status_code, 200)
        data = json.loads(resp.data)


        # send task results for task 1 - this time provide captcha, should work
        resp = self.app.post('/user/task/results',
                            data=json.dumps({
                            'id': '1',
                            'address': 'GCYUCLHLMARYYT5EXJIK2KZJCMRGIKKUCCJKJOAPUBALTBWVXAT4F4OZ',
                            'results': {'2234': 'werw', '5345': '345345'},
                            'send_push': False,
                            'captcha_token': '123123',
                            }),
                            headers={USER_ID_HEADER: str(userid)},
                            content_type='application/json')
        print('post task results response: %s' % json.loads(resp.data))
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertEqual(data['show_captcha'], False)


        # send task results for task 2, should require captcha so lets not send it and fail:
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
        data = json.loads(resp.data)
        self.assertEqual(resp.status_code, 200)  # no captcha needed

        # send task results for task 3:
        resp = self.app.post('/user/task/results',
                            data=json.dumps({
                            'id': '3',
                            'address': 'GCYUCLHLMARYYT5EXJIK2KZJCMRGIKKUCCJKJOAPUBALTBWVXAT4F4OZ',
                            'results': {'2234': 'werw', '5345': '345345'},
                            'send_push': False,
                            'captcha_token': '24234'
                            }),
                            headers={USER_ID_HEADER: str(userid)},
                            content_type='application/json')
        print('post task results response: %s' % json.loads(resp.data))
        data = json.loads(resp.data)
        self.assertEqual(resp.status_code, 200)  # no captcha needed
        self.assertEqual(data['show_captcha'], False)


        # send task results for task 4:
        resp = self.app.post('/user/task/results',
                            data=json.dumps({
                            'id': '4',
                            'address': 'GCYUCLHLMARYYT5EXJIK2KZJCMRGIKKUCCJKJOAPUBALTBWVXAT4F4OZ',
                            'results': {'2234': 'werw', '5345': '345345'},
                            'send_push': False,
                            'captcha_token': '24234'
                            }),
                            headers={USER_ID_HEADER: str(userid)},
                            content_type='application/json')
        print('post task results response: %s' % json.loads(resp.data))
        data = json.loads(resp.data)
        self.assertEqual(resp.status_code, 200)  # no captcha needed
        self.assertEqual(data['show_captcha'], False)

       # send task results for task 5:
        resp = self.app.post('/user/task/results',
                            data=json.dumps({
                            'id': '5',
                            'address': 'GCYUCLHLMARYYT5EXJIK2KZJCMRGIKKUCCJKJOAPUBALTBWVXAT4F4OZ',
                            'results': {'2234': 'werw', '5345': '345345'},
                            'send_push': False,
                            'captcha_token': '24234'
                            }),
                            headers={USER_ID_HEADER: str(userid)},
                            content_type='application/json')
        print('post task results response: %s' % json.loads(resp.data))
        data = json.loads(resp.data)
        self.assertEqual(resp.status_code, 200)  # no captcha needed
        self.assertEqual(data['show_captcha'], False)

        # send task results for task 6:
        resp = self.app.post('/user/task/results',
                             data=json.dumps({
                                 'id': '6',
                                 'address': 'GCYUCLHLMARYYT5EXJIK2KZJCMRGIKKUCCJKJOAPUBALTBWVXAT4F4OZ',
                                 'results': {'2234': 'werw', '5345': '345345'},
                                 'send_push': False,
                                 'captcha_token': '24234'
                             }),
                             headers={USER_ID_HEADER: str(userid)},
                             content_type='application/json')
        print('post task results response: %s' % json.loads(resp.data))
        data = json.loads(resp.data)
        self.assertEqual(resp.status_code, 200)  # no captcha needed
        self.assertEqual(data['show_captcha'], False)



if __name__ == '__main__':
    unittest.main()
