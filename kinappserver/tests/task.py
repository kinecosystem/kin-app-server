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

    def test_task_storing(self):
        """test storting and getting tasks"""



        cat = {'id': '0',
          'title': 'cat-title',
          'ui_data': {'color': "#something",
                      'image_url': 'https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png',
                      'header_image_url': 'https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png'}}

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
                  'price': 2000,
                  'min_to_complete': 2,
                  'skip_image_test': True,  # TODO revert back to False
                  'start_date': '2013-05-11T21:23:58.970460+00:00',
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


        resp = self.app.post('/task/add',
                            data=json.dumps({
                            'task': task}),
                            headers={},
                            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # add the same task again. this should fail
        resp = self.app.post('/task/add',
                            data=json.dumps({
                            'task': task}),
                            headers={},
                            content_type='application/json')
        self.assertNotEqual(resp.status_code, 200)

        # add the same task again but add the overwrite flag. this should not fail
        task['overwrite'] = True
        resp = self.app.post('/task/add',
                            data=json.dumps({
                            'task': task, }),
                            headers={},
                            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # add the same task again but add the overwrite flag with False. this should fail
        task['overwrite'] = False
        resp = self.app.post('/task/add',
                            data=json.dumps({
                            'task': task, }),
                            headers={},
                            content_type='application/json')
        self.assertNotEqual(resp.status_code, 200)


        # try to insert another task in the same position:
        task['id'] = 'should_fail'
        task['position'] = 0
        resp = self.app.post('/task/add',
                            data=json.dumps({
                            'task': task}),
                            headers={},
                            content_type='application/json')
        self.assertEqual(resp.status_code, 400)

        # try to insert another task in the same position:
        task['id'] = '10'
        task['position'] = 5
        resp = self.app.post('/task/add',
                            data=json.dumps({
                            'task': task}),
                            headers={},
                            content_type='application/json')
        self.assertEqual(resp.status_code, 200)


        quiz_task = { 'id': '1',
                  'title': 'do you know horses?',
                  'desc': 'horses_4_dummies',
                  'type': 'quiz',
                  'position': 1,
                  'cat_id': '0',
                  'price': 2000,
                  'min_to_complete': 2,
                  'skip_image_test': True,  # TODO revert back to False
                  'start_date': '2013-05-11T21:23:58.970460+00:00',
                  'tags': ['music',  'crypto', 'movies', 'kardashians', 'horses'],
                  'provider':
                    {'name': 'om-nom-nom-food', 'image_url': 'https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png'},
                  'items': [
                    {
                     'id': '435',
                     'text': 'what animal is this?',
                     'image_url': 'https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png',
                        'quiz_data': {
                            'answer_id': '235',
                            'explanation': 'Of course it is!',
                            'reward': 5},
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

        resp = self.app.post('/task/add',
                            data=json.dumps({
                            'task': quiz_task}),
                            headers={},
                            content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.status_code, 200)

        print(models.list_all_task_data())

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

        # get the user's current tasks
        headers = {USER_ID_HEADER: userid}
        resp = self.app.get('/user/tasks', headers=headers)
        print(resp.data)
        data = json.loads(resp.data)
        self.assertEqual(resp.status_code, 200)
        self.assertNotEqual(data['tasks']['0'][0]['memo'], None)
        self.assertEqual(models.get_user_task_results(userid), [])

        resp = self.app.post('/user/completed_tasks/add',
                                data=json.dumps({
                                    'user_id': str(userid),
                                    'task_id': '10'}),
                                    headers={USER_ID_HEADER: str(userid)},
                                content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        resp = self.app.post('/user/completed_tasks/remove',
                                data=json.dumps({
                                    'user_id': str(userid),
                                    'task_id': '10'}),
                                    headers={USER_ID_HEADER: str(userid)},
                                content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # try to remove again
        resp = self.app.post('/user/completed_tasks/remove',
                                data=json.dumps({
                                    'user_id': str(userid),
                                    'task_id': '10'}),
                                    headers={USER_ID_HEADER: str(userid)},
                                content_type='application/json')
        self.assertEqual(resp.status_code, 200)

if __name__ == '__main__':
    unittest.main()
