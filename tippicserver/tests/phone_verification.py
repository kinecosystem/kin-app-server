import simplejson as json
import unittest
import uuid

import testing.postgresql

import tippicserver
from tippicserver import db, models

import logging as log
log.getLogger().setLevel(log.INFO)


USER_ID_HEADER = "X-USERID"

class Tester(unittest.TestCase):

    def setUp(self):
        #overwrite the db name, dont interfere with stage db data
        self.postgresql = testing.postgresql.Postgresql()
        tippicserver.app.config['SQLALCHEMY_DATABASE_URI'] = self.postgresql.url()
        tippicserver.app.testing = True

        self.app = tippicserver.app.test_client()
        db.drop_all()
        db.create_all()

    def tearDown(self):
        self.postgresql.stop()

    def test_register_with_verification2(self):
        """test registration scenarios"""

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

        userid2 = str(uuid.uuid4())
        resp = self.app.post('/user/register',
            data=json.dumps({
                            'user_id': str(userid2),
                            'os': 'android',
                            'device_model': 'samsung8',
                            'device_id': '234234',
                            'time_zone': '05:00',
                            'token': 'fake_token',
                            'app_ver': '1.0'}),
            headers={},
            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        resp = self.app.post('/user/app-launch',
                            data=json.dumps({
                            'app_ver': '1.0'}),
                            headers={USER_ID_HEADER: str(userid)},
                            content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        print('data: %s' % data)
        self.assertEqual(data['config']['phone_verification_enabled'], True)

        # user updates his phone number to the server after client-side verification
        phone_num = '+9720528802120'
        resp = self.app.post('/user/firebase/update-id-token',
                    data=json.dumps({
                        'token': 'fake-token',
                        'phone_number': phone_num}),
                    headers={USER_ID_HEADER: str(userid)},
                    content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # user re-updates his number to the same number, should work.
        phone_num = '+9720528802120'
        resp = self.app.post('/user/firebase/update-id-token',
                    data=json.dumps({
                        'token': 'fake-token',
                        'phone_number': phone_num}),
                    headers={USER_ID_HEADER: str(userid)},
                    content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        print('all users: %s' %models.list_all_users())

        # different user updates his number to the same number, should work - and deactivate the previous user
        print('user 2 updates to the same number as user 1...')
        phone_num = '+9720528802120'
        resp = self.app.post('/user/firebase/update-id-token',
                    data=json.dumps({
                        'token': 'fake-token',
                        'phone_number': phone_num}),
                    headers={USER_ID_HEADER: str(userid2)},
                    content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        print('all users: %s' %models.list_all_users())

        # user2 re-updates his phone number to a different number. should fail
        phone_num = '+9720528802121'
        resp = self.app.post('/user/firebase/update-id-token',
                    data=json.dumps({
                        'token': 'fake-token',
                        'phone_number': phone_num}),
                    headers={USER_ID_HEADER: str(userid2)},
                    content_type='application/json')
        self.assertNotEqual(resp.status_code, 200)

        ## TODO - BERRY there were tests here checking task submission - different test we need to add for Tippic?

if __name__ == '__main__':
    unittest.main()
