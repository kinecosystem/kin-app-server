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
        """a single phone number can only be used so many times before we stop accepting it"""

        # android
        device_model = 'model'
        userid = str(uuid.uuid4())
        resp = self.app.post('/user/register',
            data=json.dumps({
                            'user_id': str(userid),
                            'os': 'android',
                            'device_model': device_model,
                            'device_id': '234234',
                            'time_zone': '05:00',
                            'token': 'fake_token',
                            'app_ver': '1.0'}),
            headers={},
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

        # android
        device_model = 'model'
        userid = str(uuid.uuid4())
        resp = self.app.post('/user/register',
                             data=json.dumps({
                                 'user_id': str(userid),
                                 'os': 'android',
                                 'device_model': device_model,
                                 'device_id': '234234',
                                 'time_zone': '05:00',
                                 'token': 'fake_token',
                                 'app_ver': '1.0'}),
                             headers={},
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # user verifies his number - first time
        phone_num = '+9720528802120'
        resp = self.app.post('/user/firebase/update-id-token',
                             data=json.dumps({
                                 'token': 'fake-token',
                                 'phone_number': phone_num}),
                             headers={USER_ID_HEADER: str(userid)},
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # android
        device_model = 'model'
        userid = str(uuid.uuid4())
        resp = self.app.post('/user/register',
                             data=json.dumps({
                                 'user_id': str(userid),
                                 'os': 'android',
                                 'device_model': device_model,
                                 'device_id': '234234',
                                 'time_zone': '05:00',
                                 'token': 'fake_token',
                                 'app_ver': '1.0'}),
                             headers={},
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # user verifies his number - third time should fail
        phone_num = '+9720528802120'
        resp = self.app.post('/user/firebase/update-id-token',
                             data=json.dumps({
                                 'token': 'fake-token',
                                 'phone_number': phone_num}),
                             headers={USER_ID_HEADER: str(userid)},
                             content_type='application/json')
        self.assertNotEqual(resp.status_code, 200)





        models.print_auth_tokens()

if __name__ == '__main__':
    unittest.main()
