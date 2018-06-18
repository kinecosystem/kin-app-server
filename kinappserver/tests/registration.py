import simplejson as json
import unittest
import uuid

import testing.postgresql

import kinappserver
from kinappserver import db, models


USER_ID_HEADER = "X-USERID"

class Tester(unittest.TestCase):

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

    def test_register(self):
        """test registration scenarios"""

        # android
        userid = str(uuid.uuid4())
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

        users = models.list_all_users()
        assert(users[userid]['onboarded'] == False)
        assert(users[userid]['os'] == 'android')
        assert(users[userid]['device_model'] == 'samsung8')
        assert(users[userid]['device_id'] == '234234')
        assert(users[userid]['time_zone'] == int('5'))
        assert(users[userid]['push_token'] == 'fake_token')
        assert(users[userid]['sid'] == 1)
        assert(users[userid]['auth_token'] is not '' and not None)


        # reuse device-id but not userid, should succeed
        resp = self.app.post('/user/register',
            data=json.dumps({
                            'user_id': str(uuid.uuid4()),
                            'os': 'android',
                            'device_model': 'samsung8',
                            'device_id': '234234',
                            'time_zone': '05:00',
                            'token': 'fake_token',
                            'app_ver': '1.0'}),
            headers={},
            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # ios
        resp = self.app.post('/user/register',
            data=json.dumps({
                            'user_id': str(uuid.uuid4()),
                            'os': 'iOS',
                            'device_model': 'samsung8',
                            'device_id': '234234',
                            'time_zone': '05:00',
                            'token': 'fake_token',
                            'app_ver': '1.0'}),
            headers={},
            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # no push token. should succeed.
        userid = uuid.uuid4()
        resp = self.app.post('/user/register',
            data=json.dumps({
                            'user_id': str(userid),
                            'os': 'iOS',
                            'device_model': 'samsung8',
                            'device_id': '234234',
                            'time_zone': '05:00',
                            'app_ver': '1.0'}),
            headers={},
            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # re-use userid - should succeed
        resp = self.app.post('/user/register',
            data=json.dumps({
                            'user_id': str(userid),
                            'os': 'iOS',
                            'device_model': 'samsung8',
                            'device_id': '234234',
                            'time_zone': '05:00',
                            'app_ver': '1.0'}),
            headers={},
            content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        print(json.loads(resp.data))

        print(models.list_all_users())
        assert(models.user_exists(userid))
        assert(not models.user_exists(uuid.uuid4()))

        # windows phone. should fail.
        userid = uuid.uuid4()
        resp = self.app.post('/user/register',
            data=json.dumps({
                            'user_id': str(userid),
                            'os': 'win',
                            'device_model': 'samsung8',
                            'device_id': '234234',
                            'time_zone': '05:00',
                            'app_ver': '1.0'}),
            headers={},
            content_type='application/json')
        self.assertEqual(resp.status_code, 400)
        assert(not models.user_exists(userid))

        # invalid uuid. should fail
        resp = self.app.post('/user/register',
            data=json.dumps({
                            'user_id': 'invaliduuid',
                            'os': 'iOS',
                            'device_model': 'samsung8',
                            'device_id': '234234',
                            'time_zone': '05:00',
                            'app_ver': '1.0'}),
            headers={},
            content_type='application/json')
        self.assertEqual(resp.status_code, 400)
        print(json.loads(resp.data))

        models.print_auth_tokens()

if __name__ == '__main__':
    unittest.main()
