import logging as log
import unittest
import uuid
import simplejson as json
import testing.postgresql

import kinappserver
from kinappserver import db

log.getLogger().setLevel(log.INFO)


USER_ID_HEADER = "X-USERID"


class Tester(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        pass

    def setUp(self):
        # overwrite the db name, dont interfere with stage db data
        self.postgresql = testing.postgresql.Postgresql()
        kinappserver.app.config['SQLALCHEMY_DATABASE_URI'] = self.postgresql.url(
        )
        kinappserver.app.testing = True
        self.app = kinappserver.app.test_client()
        db.drop_all()
        db.create_all()

    def tearDown(self):
        self.postgresql.stop()

    def test_topics_task_logic(self):
        """test topics/task logic"""

        topic_sports = {
            "name": "Sports",
            "skip_image_test": True,
            "icon_url": "https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png"
        }

        topic_games = {
            "name": "Games",
            "skip_image_test": True,
            "icon_url": "https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png"
        }

        cat_1 = {'id': '1',
                 'title': 'cat-title',
                 'supported_os': 'all',
                 "skip_image_test": True,
                 'ui_data': {'color': "#123",
                             'image_url': 'https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png',
                             'header_image_url': 'https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png'}}

        cat_2 = {'id': '2',
                 'title': 'cat-title',
                 'supported_os': 'all',
                 "skip_image_test": True,
                 'ui_data': {'color': "#123",
                             'image_url': 'https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png',
                             'header_image_url': 'https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png'}}

        task_1 = {
            'id': '1',
            "cat_id": '1',
            "position": 0,
            'title': 'do you know horses?',
            'desc': 'horses_4_dummies',
            'type': 'questionnaire',
            'price': 1,
            'skip_image_test': True,
            'min_to_complete': 2,
            'tags': [1],
            'provider':
                {'name': 'om-nom-nom-food',
                    'image_url': 'http://inter.webs/horsie.jpg'},
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

        task_2 = {
            'id': '2',
            "cat_id": '1',
            "position": 1,
            'title': 'do you know horses?',
            'desc': 'horses_4_dummies',
            'type': 'questionnaire',
            'price': 1,
            'skip_image_test': True,
            'min_to_complete': 2,
            'tags': [2],
            'provider':
                {'name': 'om-nom-nom-food',
                    'image_url': 'http://inter.webs/horsie.jpg'},
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

        task_3 = {
            'id': '3',
            "cat_id": '2',
            "position": 0,
            'title': 'do you know horses?',
            'desc': 'horses_4_dummies',
            'type': 'questionnaire',
            'price': 1,
            'skip_image_test': True,
            'min_to_complete': 2,
            'tags': [1],
            'provider':
                {'name': 'om-nom-nom-food',
                    'image_url': 'http://inter.webs/horsie.jpg'},
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

        task_4 = {
            'id': '4',
            "cat_id": '2',
            "position": 1,
            'title': 'do you know horses?',
            'desc': 'horses_4_dummies',
            'type': 'questionnaire',
            'price': 1,
            'skip_image_test': True,
            'min_to_complete': 2,
            'tags': [2],
            'provider':
                {'name': 'om-nom-nom-food',
                    'image_url': 'http://inter.webs/horsie.jpg'},
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

        db.engine.execute("""update public.push_auth_token set auth_token='%s' where user_id='%s';""" % (
            str(userid), str(userid)))

        resp = self.app.post('/user/auth/ack',
                             data=json.dumps({
                                 'token': str(userid)}),
                             headers={USER_ID_HEADER: str(userid)},
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        resp = self.app.post('/category/add',
                             data=json.dumps({
                                 'category': cat_1}),
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        resp = self.app.post('/category/add',
                             data=json.dumps({
                                 'category': cat_2}),
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        resp = self.app.post('/topic/add',
                             data=json.dumps({
                                 'topic': topic_sports}),
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        resp = self.app.post('/topic/add',
                             data=json.dumps({
                                 'topic': topic_games}),
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        resp = self.app.post('/task/add',
                             data=json.dumps({
                                 'task': task_1}),
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        resp = self.app.post('/task/add',
                             data=json.dumps({
                                 'task': task_2}),
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        resp = self.app.post('/task/add',
                             data=json.dumps({
                                 'task': task_3}),
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        resp = self.app.post('/task/add',
                             data=json.dumps({
                                 'task': task_4}),
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        ######################################################

        resp = self.app.get('/topic/list_all')
        print('resp: %s' % resp.data)
        topics = json.loads(resp.data)['topics']
        self.assertEqual(resp.status_code, 200)
        self.assertSetEqual(set(topics.keys()), {'1', '2'})

        # get the user's current tasks
        headers = {USER_ID_HEADER: userid}
        resp = self.app.get('/user/tasks', headers=headers)
        print('resp: %s' % resp.data)
        data = json.loads(resp.data)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(data['tasks']['1'].id, '1')
        self.assertEqual(data['tasks']['2'].id, '3')

        # user selects topics
        resp = self.app.post(
            '/user/topics', data=json.dumps({'ids': ["2"]}), headers=headers, content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # get user topics
        resp = self.app.get('/user/topics', headers=headers)
        print('resp: %s' % resp.data)
        topics = json.loads(resp.data)['topics']
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(set(topics), {'2'})

        # get the user's current tasks
        headers = {USER_ID_HEADER: userid}
        resp = self.app.get('/user/tasks', headers=headers)
        print('resp: %s' % resp.data)
        data = json.loads(resp.data)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(data['tasks']['1'].id, '2')
        self.assertEqual(data['tasks']['2'].id, '4')


if __name__ == '__main__':
    unittest.main()
