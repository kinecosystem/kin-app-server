import simplejson as json
from uuid import uuid4
import testing.postgresql

import unittest
import kinappserver
from kinappserver import db
import logging as log
log.getLogger().setLevel(log.INFO)


USER_ID_HEADER = "X-USERID"


class Tester(unittest.TestCase):
    """tests the entire spend-scenario: creating an order and then redeeming it"""

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

    def test_whitelist(self):
        """test whitelisting """

        # register a user
        userid1 = uuid4()
        resp = self.app.post('/user/register',
            data=json.dumps({
                            'user_id': str(userid1),
                            'os': 'android',
                            'device_model': 'samsung8',
                            'device_id': '234234',
                            'time_zone': '05:00',
                            'token': 'fake_token',
                            'app_ver': '1.0'}),
            headers={},
            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # add transactions to the user
        db.engine.execute("""update public.push_auth_token set auth_token='%s' where user_id='%s';""" % (str(userid1), str(userid1)))

        resp = self.app.post('/user/auth/ack',
                            data=json.dumps({
                            'token': str(userid1)}),
                            headers={USER_ID_HEADER: str(userid1)},
                            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # user updates his phone number to the server after client-side verification
        phone_num1 = '+972551234444'
        resp = self.app.post('/user/firebase/update-id-token',
                    data=json.dumps({
                        'token': 'fake-token',
                        'phone_number': phone_num1}),
                    headers={USER_ID_HEADER: str(userid1)},
                    content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # request to
        resp = self.app.post('/user/whitelist',
                    data=json.dumps({
                    'id': '1-kit-s411ebc83d07e4c55b9d13',
                    'sender_address': 'GD6UWGMWGW5VLM4ZLIC3OXPV772W55IVFAH5RZK36CUYQDK7FSMJLDMJ',
                    'recipient_address':'GCSD5FPNKSTAOPDZ2OWMFPJEBRD3HWPTDICTS4PTOKESOJHNLQUDVSGA',
                    'amount':3,
                    'transaction':'AAAAAP1LGZY1u1WzmVoFt131//Vu9RUoD9jlW/CpiA1fLJiVAAAAAAAXjnUAAAABAAAAAAAAAAEAAAAGMS1raXQtAAAAAAABAAAAAAAAAAEAAAAApD6V7VSmBzx506zCvSQMR7PZ8xoFOXHzcoknJO1cKDoAAAAAAAAAAAAEk+AAAAAAAAAAAV8smJUAAABAhfjmQkqeeKRZGmmtiivXynmregpE0yNKHP3yVIrbT0pSQg6jjlDNnTUQrWbptHhYGyx76SdbocYYCxX//qE1Ag=='
                    }),
                    headers={USER_ID_HEADER: str(userid1)},
                    content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertEqual(data['status'], 'ok')

if __name__ == '__main__':
    unittest.main()
