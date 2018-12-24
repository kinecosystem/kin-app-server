import simplejson as json
import unittest
import uuid

import testing.postgresql

import kinappserver
from kinappserver import db, models

import logging as log
log.getLogger().setLevel(log.INFO)

USER_ID_HEADER = "X-USERID"

class Tester(unittest.TestCase):

    def register_user(self,user_id, phone_num):
        resp = self.app.post('/user/register',
            data=json.dumps({
                            'user_id': str(user_id),
                            'os': 'android',
                            'device_model': 'samsung8',
                            'device_id': '123456',
                            'time_zone': '00:00',
                            'token': 'fake_token',
                            'app_ver': '1.4.1'}),
            headers={},
            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        db.engine.execute("""update public.push_auth_token set auth_token='%s' where user_id='%s';""" % (str(user_id), str(user_id)))


        resp = self.app.post('/user/auth/ack',
                            data=json.dumps({
                                'token': str(user_id)}),
                            headers={USER_ID_HEADER: str(user_id)},
                            content_type='application/json')
        self.assertEqual(resp.status_code, 200)


        # user updates his phone number to the server after client-side verification
        resp = self.app.post('/user/firebase/update-id-token',
                    data=json.dumps({
                        'token': 'fake-token',
                        'phone_number': phone_num}),
                    headers={USER_ID_HEADER: str(user_id)},
                    content_type='application/json')
        self.assertEqual(resp.status_code, 200)

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

    def test_users_blacklisting(self):
        """ test user list blacklisting"""
        user_ids = [
            "1d7bc242-81fb-4be1-8eea-f87f2ee61680",
            "04bcc50e-ba34-4568-a73c-0c0c20e5bde0",
            "a87241ff-9900-4770-9c3e-8554c76e8a24",
            "5bec064c-4fe5-4699-a9ef-f2cacdd8aa10"
        ]
        
        self.register_user(user_ids[0], "+97212345678")        
        self.register_user(user_ids[1], "+97222345678")      
        self.register_user(user_ids[2], "+97132345678")     
        self.register_user(user_ids[3], "+97132345678")

        # blacklist a number
        resp = self.app.post('/user/user-id/blacklist',
                             data=json.dumps({
                                 'user_ids': user_ids}),
                             headers={},
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        print('data: %s' % data)


        phone_number = '+9720526602765'
        # blacklist a number
        resp = self.app.post('/user/phone-number/blacklist',
                             data=json.dumps({
                                 'phone-number': phone_number}),
                             headers={},
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # ensure its blacklisted

        self.assertEqual(True, models.is_phone_number_blacklisted(phone_number))

if __name__ == '__main__':
    unittest.main()
