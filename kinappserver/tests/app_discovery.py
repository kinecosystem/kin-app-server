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
        # overwrite the db name, dont interfere with stage db data
        self.postgresql = testing.postgresql.Postgresql()
        kinappserver.app.config['SQLALCHEMY_DATABASE_URI'] = self.postgresql.url()
        kinappserver.app.testing = True
        self.app = kinappserver.app.test_client()
        db.drop_all()
        db.create_all()

    def tearDown(self):
        self.postgresql.stop()

    def test_add_app_discover_api(self):
        """ test adding apps and categories"""
        # create an android user
        android_user = uuid.uuid4()
        resp = self.app.post('/user/register',
                             data=json.dumps({
                                 'user_id': str(android_user),
                                 'os': 'android',
                                 'device_model': 'samsung8',
                                 'device_id': '234234',
                                 'time_zone': '05:00',
                                 'token': 'fake_token',
                                 'app_ver': '1.0'}),
                             headers={},
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        # create an iOS user
        ios_user = uuid.uuid4()
        resp = self.app.post('/user/register',
                             data=json.dumps({
                                 'user_id': str(ios_user),
                                 'os': 'iOS',
                                 'device_model': 'iphone9',
                                 'device_id': '1234',
                                 'time_zone': '05:00',
                                 'token': 'fake_token',
                                 'app_ver': '1.0'}),
                             headers={},
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # create a category
        cat = {
            'category_id': '0',
            'title': 'cat-title'
        }
        # add category to db
        resp = self.app.post('/app_discovery/add_discovery_app_category',
                             data=json.dumps({
                                 'discovery_app_category': cat}),
                             headers={},
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # test if user sees the category
        resp = self.app.get('/app_discovery', headers={USER_ID_HEADER: str(android_user)})
        self.assertEqual(resp.status_code, 200)

        print(json.loads(resp.data))
        data = json.loads(resp.data)

        # test that category data is correct
        self.assertEqual(data[0]['category_id'], 0)
        self.assertEqual(data[0]['title'], 'cat-title')
        self.assertEqual(data[0]['apps'], [])

        # create an android app
        app = {
            'skip_image_test': 'true',
            'app_identifier': '0',
            'title': 'app title',
            'subtitle': 'subtitle',
            'app_category_id': '0',
            'os_type': 'android',
            'meta_data': {
                'app_url': 'url',
                'description': 'long desc',
                'kin_usage': 'how to use description',
                'icon_url': 'url',
                'card_image_url': 'url',
                'image_url': 'url',
            }
        }
        # add the app
        resp = self.app.post('/app_discovery/add_discovery_app',
                             data=json.dumps({
                                 'discovery_app': app,
                                 'set_active': 'True'}),
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # verify android user sees the app
        resp = self.app.get('/app_discovery', headers={USER_ID_HEADER: str(android_user)})
        self.assertEqual(resp.status_code, 200)

        print(json.loads(resp.data))
        data = json.loads(resp.data)

        self.assertEqual(data[0]['category_id'], 0)
        self.assertEqual(data[0]['title'], 'cat-title')
        self.assertEqual(len(data[0]['apps']), 1)

        # verify iOS user does not see the app
        resp = self.app.get('/app_discovery', headers={USER_ID_HEADER: str(ios_user)})
        self.assertEqual(resp.status_code, 200)

        print(json.loads(resp.data))
        data = json.loads(resp.data)

        self.assertEqual(data[0]['category_id'], 0)
        self.assertEqual(data[0]['title'], 'cat-title')
        self.assertEqual(len(data[0]['apps']), 0)

        # create an androdi and ios app
        app = {
            'skip_image_test': 'true',
            'app_identifier': '1',
            'title': 'app title',
            'subtitle': 'subtitle',
            'app_category_id': '0',
            'os_type': 'android, iOS',
            'meta_data': {
                'app_url': 'url',
                'description': 'long desc',
                'kin_usage': 'how to use description',
                'icon_url': 'url',
                'card_image_url': 'url',
                'image_url': 'url',
            }
        }

        # add the app
        resp = self.app.post('/app_discovery/add_discovery_app',
                             data=json.dumps({
                                 'discovery_app': app,
                                 'set_active': 'True'}),
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # verify android user sees 2 apps
        resp = self.app.get('/app_discovery', headers={USER_ID_HEADER: str(android_user)})
        self.assertEqual(resp.status_code, 200)

        print(json.loads(resp.data))
        data = json.loads(resp.data)

        self.assertEqual(data[0]['category_id'], 0)
        self.assertEqual(data[0]['title'], 'cat-title')
        self.assertEqual(len(data[0]['apps']), 2)

        # verify iOS user sees new app
        resp = self.app.get('/app_discovery', headers={USER_ID_HEADER: str(ios_user)})
        self.assertEqual(resp.status_code, 200)

        print(json.loads(resp.data))
        data = json.loads(resp.data)

        self.assertEqual(data[0]['category_id'], 0)
        self.assertEqual(data[0]['title'], 'cat-title')
        self.assertEqual(len(data[0]['apps']), 1)

        # create a category
        cat = {
            'category_id': '1',
            'title': 'cat-title'
        }
        # add category to db
        resp = self.app.post('/app_discovery/add_discovery_app_category',
                             data=json.dumps({
                                 'discovery_app_category': cat}),
                             headers={},
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        resp = self.app.get('/app_discovery', headers={USER_ID_HEADER: str(ios_user)})
        self.assertEqual(resp.status_code, 200)
        print(json.loads(resp.data))
        # verify users sees the new category
        data = json.loads(resp.data)
        self.assertEqual(len(data), 2)


if __name__ == '__main__':
    unittest.main()
