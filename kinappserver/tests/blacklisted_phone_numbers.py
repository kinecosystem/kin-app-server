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

    def test_auth_token(self):
        """blacklisting phone number scenarios"""

        phone_number = '+9720526602765'
        # blacklist a number
        resp = self.app.post('/user/phone-number/blacklist',
            data=json.dumps({
                            'phone-number': phone_number,
                            'os': 'android',
                            'device_model': 'samsung8',
                            'device_id': '234234',
                            'time_zone': '05:00',
                            'token': 'fake_token',
                            'app_ver': '1.0'}),
            headers={},
            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # ensure its blacklisted

        self.assertEqual(True, models.is_phone_number_blacklisted(phone_number))


if __name__ == '__main__':
    unittest.main()
