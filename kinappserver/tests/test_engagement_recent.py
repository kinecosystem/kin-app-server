import simplejson as json
from uuid import uuid4
from time import sleep
import testing.postgresql
from datetime import datetime
from datetime import timedelta

import unittest
import kinappserver
from kinappserver import db, models


USER_ID_HEADER = "X-USERID"

class Tester(unittest.TestCase):
    """tests the selection logic for engagement-recent"""

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


    def test_engagement_recent(self):
        """test selecting the right users for this engagement notificaton"""

        def count_tokens(tokens):
            return len(tokens['iOS']) + len(tokens['android'])

        def set_users_last_active(new_timestamp):
            db.engine.execute("update public.user_app_data set update_at='%s'" % new_timestamp)

        def add_user():
            userid1 = uuid4()
            resp = self.app.post('/user/register',
                data=json.dumps({
                                'user_id': str(userid1),
                                'os': 'android',
                                'device_model': 'samsung8',
                                'device_id': '234234',
                                'time_zone': '+02:00',
                                'token': 'AAAAA',
                                'app_ver': '1.0'}),
                headers={},
                content_type='application/json')
            self.assertEqual(resp.status_code, 200)

            db.engine.execute("""update public.push_auth_token set auth_token='%s' where user_id='%s';""" % (str(userid1), str(userid1)))

            resp = self.app.post('/user/auth/ack',
                                 data=json.dumps({
                                     'token': str(userid1)}),
                                 headers={USER_ID_HEADER: str(userid1)},
                                 content_type='application/json')
            self.assertEqual(resp.status_code, 200)

            return userid1


        # add 2 tasks
        task0 = {
          'id': '0', 
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

        # add 10 users
        user_ids = []
        for i in range(0,10):
            user_ids.append(add_user())

        tokens = models.get_users_for_engagement_push('engage-recent')
        self.assertEqual(count_tokens(tokens), 0)

        # set last active to 4 days ago
        time_active = str(datetime.utcnow() + timedelta(days=-4))
        set_users_last_active(time_active)
        tokens = models.get_users_for_engagement_push('engage-recent')
        self.assertEqual(count_tokens(tokens), 10)

        # set last active to 3 days ago
        time_active = str(datetime.utcnow() + timedelta(days=-3))
        set_users_last_active(time_active)
        tokens = models.get_users_for_engagement_push('engage-recent')
        self.assertEqual(count_tokens(tokens), 10)

        # set last active to 5 days ago
        time_active = str(datetime.utcnow() + timedelta(days=-5))
        set_users_last_active(time_active)
        tokens = models.get_users_for_engagement_push('engage-recent')
        self.assertEqual(count_tokens(tokens), 0)

        # set last active to 3 days ago
        time_active = str(datetime.utcnow() + timedelta(days=-2))
        set_users_last_active(time_active)
        tokens = models.get_users_for_engagement_push('engage-recent')
        self.assertEqual(count_tokens(tokens), 10)

        # submit results by user 0 and thus put the user into cooldown
        models.store_task_results(user_ids[0], '0', '[\"0\",\"1\"]')

        # get tokens. user 0's token should be gone
        tokens = models.get_users_for_engagement_push('engage-recent')
        self.assertEqual(count_tokens(tokens), 9)


if __name__ == '__main__':
    unittest.main()
