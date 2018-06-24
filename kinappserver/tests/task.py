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
        task = {  'id': 0,
                  'title': 'do you know horses?',
                  'desc': 'horses_4_dummies',
                  'type': 'questionnaire',
                  'price': 2000,
                  'min_to_complete': 2,
                  'skip_image_test': False,
                  'start_date': '2013-05-11T21:23:58.970460+00:00',
                  'tags': ['music',  'crypto', 'movies', 'kardashians', 'horses'],
                  'provider': 
                    {'name': 'om-nom-nom-food', 'image_url': 'https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png'},
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

        # get the user's current tasks
        headers = {USER_ID_HEADER: userid}
        resp = self.app.get('/user/tasks', headers=headers)
        data = json.loads(resp.data)
        print(data)
        self.assertEqual(resp.status_code, 200)
        self.assertNotEqual(data['tasks'][0]['memo'], None)
        self.assertEqual(models.get_user_task_results(userid), [])



if __name__ == '__main__':
    unittest.main()
