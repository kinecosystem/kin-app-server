import unittest
import uuid

import simplejson as json
import testing.postgresql
from stellar_base.keypair import Keypair
from stellar_base.address import Address


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
        #overwrite the db name, dont interfere with stage db data
        self.postgresql = testing.postgresql.Postgresql()
        kinappserver.app.config['SQLALCHEMY_DATABASE_URI'] = self.postgresql.url()
        kinappserver.app.testing = True
        self.app = kinappserver.app.test_client()
        db.drop_all()
        db.create_all()
        kinappserver.app.redis.flushdb()


    def tearDown(self):
        self.postgresql.stop()

    def test_truex_callback(self):

        # register a user
        userid = 'c1ee58d9-c068-44fc-8c62-400f0537e8d2'
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

        kp = Keypair.random()
        resp = self.app.post('/user/onboard',
            data=json.dumps({
                            'public_address': kp.address().decode()}),
            headers={USER_ID_HEADER: str(userid)},
            content_type='application/json')
        print(json.loads(resp.data))
        self.assertEqual(resp.status_code, 200)

        # TODO establish trust for this address

        task0 = {'id': '0',
                 'title': 'do you know horses?',
                 'desc': 'horses_4_dummies',
                 'type': 'truex',
                 'price': 2,
                 'skip_image_test': True,
                 'min_to_complete': 2,
                 'tags': ['music', 'crypto', 'movies', 'kardashians', 'horses'],
                 'provider':
                     {'name': 'om-nom-nom-food', 'image_url': 'https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png'},
                 'items': [{'type': 'text'}]
                 }

        resp = self.app.post('/task/add',
                            data=json.dumps({
                            'task': task0}),
                            headers={},
                            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # set the delay_days on all the tasks to two
        resp = self.app.post('/task/delay_days',
                            data=json.dumps({
                            'days': 0}),
                            headers={},
                            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # get the user's current tasks
        headers = {USER_ID_HEADER: userid}
        resp = self.app.get('/user/tasks', headers=headers)
        data = json.loads(resp.data)
        print(data)
        self.assertEqual(resp.status_code, 200)

        url = '/truex/callback?application_key=e8e7dbe7d7b1d16f0ab2&network_user_id=c1ee58d9-c068-44fc-8c62-400f0537e8d2&currency_amount=1&currency_label=&revenue=0.0072&placement_hash=21be84de4fa0cc0315a5563d02e293b99b67cd16&campaign_name=Kik+-+Kin+-+KF+Panda+Mobile+SVNRE&campaign_id=13255&creative_name=KF+Panda+Mobile+SVNRE&creative_id=8974&engagement_id=883635952&client_request_id=1529492319&sig=eXeHQVjiJEx%2BaCnctbZq1g08q0Y%3D'
        print('processing truex callback - should work')
        # get the truex activity - should fail
        resp = self.app.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(b'1', resp.data)

if __name__ == '__main__':
    unittest.main()
