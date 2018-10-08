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

    def test_user_migration(self):
        """test storting task reults"""

        cat = {'id': '0',
          'title': 'cat-title',
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

        cat2 = {'id': '1',
          'title': 'cat-title2',
               "skip_image_test": True,
          'ui_data': {'color': "#123",
                      'image_url': 'https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png',
                      'header_image_url': 'https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png'}}

        resp = self.app.post('/category/add',
                            data=json.dumps({
                            'category': cat2}),
                            headers={},
                            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        cat3 = {'id': '2',
          'title': 'cat-title3',
               "skip_image_test": True,
          'ui_data': {'color': "#123",
                      'image_url': 'https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png',
                      'header_image_url': 'https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png'}}

        resp = self.app.post('/category/add',
                            data=json.dumps({
                            'category': cat3}),
                            headers={},
                            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        print('all cat_ids: %s' % models.get_all_cat_ids())

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

        # set tasks1.0-style tasks into the db
        db.engine.execute('update public.user_app_data set completed_tasks=\'"[]"\' where user_id=\'%s\';' % (str(userid)))
        models.add_task_to_completed_tasks1(str(userid), '0')

        # migrate the user to task2.0
        models.migrate_user_to_tasks2(str(userid))

        # get the user's current tasks
        headers = {USER_ID_HEADER: userid}
        resp = self.app.get('/user/tasks', headers=headers)
        data = json.loads(resp.data)
        print('data: %s' % data)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(data['tasks']['0'], [])
        self.assertEqual(data['tasks']['1'], [])
        self.assertEqual(data['tasks']['2'], [])

        # lets add a task that that user already solved.

        task = {
            'id': '0',
            "cat_id": '0',
            "position": 0,
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

        resp = self.app.post('/task/add',
                            data=json.dumps({
                            'task': task}),
                            headers={},
                            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        task['id'] = 1
        task['position'] = 1
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

        # set tasks1.0-style tasks into the db
        db.engine.execute('update public.user_app_data set completed_tasks=\'"[]"\' where user_id=\'%s\';' % (str(userid)))
        models.add_task_to_completed_tasks1(str(userid), '0')

        # migrate the user to task2.0
        models.migrate_user_to_tasks2(str(userid))

        # get the user's current tasks - should not receive task id 0
        headers = {USER_ID_HEADER: userid}
        resp = self.app.get('/user/tasks', headers=headers)
        data = json.loads(resp.data)
        print('data: %s' % data)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(data['tasks']['0']), 1)  # returns one task
        self.assertEqual(data['tasks']['0'][0]['id'], '1')  # task no. 1 because zero was already returned
        self.assertEqual(data['tasks']['1'], [])
        self.assertEqual(data['tasks']['2'], [])



if __name__ == '__main__':
    unittest.main()
