import unittest
import uuid

import simplejson as json
import testing.postgresql


import kinappserver
from kinappserver import db, models
import arrow

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

    def test_ad_hoc_task_logic(self):
        """test storing and getting ad-hoc tasks"""

        def assert_user_tasks(user_id, expected_tasks):
            # get the user's current tasks
            headers = {USER_ID_HEADER: userid}
            resp = self.app.get('/user/tasks', headers=headers)
            data = json.loads(resp.data)
            self.assertEqual(resp.status_code, 200)
            print('data: %s' % data)
            for cat_id in expected_tasks.keys():
                if expected_tasks[cat_id] is None:
                    self.assertEqual(data['tasks'][cat_id], [])
                else:
                    self.assertEqual(expected_tasks[cat_id], data['tasks'][cat_id][0]['id'])

        cat = {'id': '0',
          'title': 'cat-title',
          'supported_os': 'all',
          'ui_data': {'color': "#something",
                      'image_url': 'https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png',
                      'header_image_url': 'https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png'}}

        resp = self.app.post('/category/add',
                            data=json.dumps({
                            'category': cat}),
                            headers={},
                            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        cat['id'] = '1'
        resp = self.app.post('/category/add',
                            data=json.dumps({
                            'category': cat}),
                            headers={},
                            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        task = {  'id': '0',
                  'title': 'do you know horses?',
                  'desc': 'horses_4_dummies',
                  'type': 'questionnaire',
                  'position': 0,
                  'cat_id': '0',
                  'price': 2,
                  'delay_days': 0,
                  'min_to_complete': 2,
                  'skip_image_test': True, # test link-checking code
                  'tags': ['music',  'crypto', 'movies', 'kardashians', 'horses'],
                  'provider': 
                    {'name': 'om-nom-nom-food', 'image_url': 'https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png'},
                  'post_task_actions':[{'type': 'external-url',
                                        'text': 'please vote mofos',
                                        'text_ok': 'yes! register!',
                                        'text_cancel': 'no thanks mofos',
                                        'url': 'https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png',
                                        'icon_url': 'https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png',
                                        'campaign_name': 'buy-moar-underwear'}],
                  'items': [
                    {
                     'id': '435', 
                     'text': 'what animal is this?',
                     'image_url': 'https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png',
                     'type': 'textimage',
                         'results': [
                                {'id': '235',
                                 'text': 'a horse!', 
                                 'image_url': 'https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png'},
                                    {'id': '2465436',
                                 'text': 'a cat!', 
                                 'image_url': 'https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png'},
                                 ],
                    }]
            }

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

        db.engine.execute("""update public.push_auth_token set auth_token='%s' where user_id='%s';""" % (str(userid), str(userid)))

        resp = self.app.post('/user/auth/ack',
                            data=json.dumps({
                            'token': str(userid)}),
                            headers={USER_ID_HEADER: str(userid)},
                            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # add the first task
        task['cat_id'] = '0'
        task['id'] = '0'
        task['position'] = 0
        resp = self.app.post('/task/add',
                             data=json.dumps({
                                 'task': task}),
                             headers={},
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        assert_user_tasks(userid, {'0': '0', '1': None})

        # expecting ad hoc task with id 1 in cat '1'
        task['cat_id'] = '1'
        task['id'] = '1'
        task['position'] = -1
        task['task_start_date'] = str(arrow.utcnow().shift(hours=-1))
        task['task_expiration_date'] = str(arrow.utcnow().shift(hours=+1))
        resp = self.app.post('/task/add',
                             data=json.dumps({
                                 'task': task}),
                             headers={},
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        assert_user_tasks(userid, {'0': '0', '1': '1'})

        # expecting ad hoc task with id 2 in cat '1' - it starts before task_id '1'
        task['cat_id'] = '1'
        task['id'] = '2'
        task['position'] = -1
        task['task_start_date'] = str(arrow.utcnow().shift(hours=-2))
        task['task_expiration_date'] = str(arrow.utcnow().shift(hours=+1))
        resp = self.app.post('/task/add',
                             data=json.dumps({
                                 'task': task}),
                             headers={},
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        assert_user_tasks(userid, {'0': '0', '1': '2'})

        # expecting ad hoc task with id 3 in cat '0' - it takes precedence over task_id '0'
        task['cat_id'] = '0'
        task['id'] = '3'
        task['position'] = -1
        task['task_start_date'] = str(arrow.utcnow().shift(hours=-2))
        task['task_expiration_date'] = str(arrow.utcnow().shift(hours=+1))
        resp = self.app.post('/task/add',
                             data=json.dumps({
                                 'task': task}),
                             headers={},
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        assert_user_tasks(userid, {'0': '3', '1': '2'})

        # should not change - task_id '4' comes after task_id 3
        task['cat_id'] = '0'
        task['id'] = '4'
        task['position'] = -1
        task['task_start_date'] = str(arrow.utcnow().shift(hours=-1))
        task['task_expiration_date'] = str(arrow.utcnow().shift(hours=+1))
        resp = self.app.post('/task/add',
                             data=json.dumps({
                                 'task': task}),
                             headers={},
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        assert_user_tasks(userid, {'0': '3', '1': '2'})

        # should not change - task_id '5' is inactive - starts later
        task['cat_id'] = '0'
        task['id'] = '5'
        task['position'] = -1
        task['task_start_date'] = str(arrow.utcnow().shift(hours=+1))
        task['task_expiration_date'] = str(arrow.utcnow().shift(hours=+2))
        resp = self.app.post('/task/add',
                             data=json.dumps({
                                 'task': task}),
                             headers={},
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        assert_user_tasks(userid, {'0': '3', '1': '2'})

        # should not change - task_id '6' is inactive - already over
        task['cat_id'] = '0'
        task['id'] = '6'
        task['position'] = -1
        task['task_start_date'] = str(arrow.utcnow().shift(hours=-20))
        task['task_expiration_date'] = str(arrow.utcnow().shift(hours=-4))
        resp = self.app.post('/task/add',
                             data=json.dumps({
                                 'task': task}),
                             headers={},
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        assert_user_tasks(userid, {'0': '3', '1': '2'})

        # send task results for task_id 3
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
        self.assertEqual(resp.status_code, 200)

        # having solved task 3, task 4 should now be active
        assert_user_tasks(userid, {'0': '4', '1': '2'})

        # send task results for task_id 4
        resp = self.app.post('/user/task/results',
                            data=json.dumps({
                            'id': '4',
                            'address': 'GCYUCLHLMARYYT5EXJIK2KZJCMRGIKKUCCJKJOAPUBALTBWVXAT4F4OZ',
                            'results': {'2234': 'werw', '5345': '345345'},
                            'send_push': False
                            }),
                            headers={USER_ID_HEADER: str(userid)},
                            content_type='application/json')
        print('post task results response: %s' % json.loads(resp.data))
        self.assertEqual(resp.status_code, 200)

        # having solved task 3, task 4 should now be active
        assert_user_tasks(userid, {'0': '0', '1': '2'})

        # send task results for task_id 2
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
        self.assertEqual(resp.status_code, 200)

        # having solved task 3, task 4 should now be active
        assert_user_tasks(userid, {'0': '0', '1': '1'})


        # send task results for task_id 1
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
        self.assertEqual(resp.status_code, 200)

        # having solved task 3, task 4 should now be active
        assert_user_tasks(userid, {'0': '0', '1': None})

if __name__ == '__main__':
    unittest.main()
