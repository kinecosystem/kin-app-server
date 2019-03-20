import json
import unittest
import uuid

import testing.postgresql

import kinappserver
from kinappserver import db

import logging as log
log.getLogger().setLevel(log.INFO)


USER_ID_HEADER = "X-USERID"


class Tester(unittest.TestCase):

    #@mock.patch('redis.StrictRedis', mockredis.mock_redis_client)
    def setUp(self):
        #overwrite the db name, dont interfere with stage db data
        self.postgresql = testing.postgresql.Postgresql()
        kinappserver.app.config['SQLALCHEMY_DATABASE_URI'] = self.postgresql.url()
        kinappserver.app.testing = True
        #kinappserver.app.redis = redis.StrictRedis(host='0.0.0.0', port=6379, db=0) # doesnt play well with redis-lock
        self.app = kinappserver.app.test_client()
        db.drop_all()
        db.create_all()
        


    def tearDown(self):
        self.postgresql.stop()

    
    def test_onboard(self):
        """test onboarding scenarios"""

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

        # try to onboard user, should succeed
        from kin import Keypair
        kp = Keypair()
        address = kp.address_from_seed(kp.generate_seed())
        resp = self.app.post('/user/onboard',
            data=json.dumps({
                            'public_address': address}),
            headers={USER_ID_HEADER: str(userid)},
            content_type='application/json')
        print(json.loads(resp.data))
        self.assertEqual(resp.status_code, 200)


        # try onboarding again with the same user - should fail
        resp = self.app.post('/user/onboard',
            data=json.dumps({
                            'public_address': address}),
            headers={USER_ID_HEADER: str(userid)},
            content_type='application/json')
        print(json.loads(resp.data))
        self.assertEqual(resp.status_code, 400)

        # try sending kin to that public address
        resp = self.app.post('/send-kin',
            data=json.dumps({
                            'public_address': address,
                            'amount': 1}),
            headers={USER_ID_HEADER: str(userid)},
            content_type='application/json')
        print(json.loads(resp.data))
        self.assertEqual(resp.status_code, 200)

        resp = self.app.post('/send-kin-payment-service',
            data=json.dumps({
                            'public_address': address,
                            'amount': 1}),
            headers={USER_ID_HEADER: str(userid)},
            content_type='application/json')
        print(json.loads(resp.data))
        self.assertEqual(resp.status_code, 200)


if __name__ == '__main__':
    unittest.main()
