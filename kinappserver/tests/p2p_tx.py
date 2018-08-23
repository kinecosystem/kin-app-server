import simplejson as json
from uuid import uuid4
from time import sleep
import testing.postgresql

import unittest
import kinappserver
from kinappserver import db, stellar, models


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


    def test_p2p_tx(self):
        """test creating a p2p tx"""
        from stellar_base.keypair import Keypair
        offerid = '0'
        offer = {'id': offerid,
                 'type': 'gift-card',
                 'type_image_url': "https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png",
                 'domain': 'music',
                 'title': 'offer_title',
                 'desc': 'offer_desc',
                 'image_url': 'image_url',
                 'skip_image_test': True,
                 'price': 2,
                 'address': 'GCYUCLHLMARYYT5EXJIK2KZJCMRGIKKUCCJKJOAPUBALTBWVXAT4F4OZ',
                 'provider':
                    {'name': 'om-nom-nom-food', 'image_url': 'http://inter.webs/horsie.jpg'},
                }

        # add an offer
        resp = self.app.post('/offer/add',
                            data=json.dumps({
                            'offer': offer}),
                            headers={},
                            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # enable the offer
        resp = self.app.post('/offer/set_active',
                            data=json.dumps({
                            'id': offerid,
                            'is_active': True}),
                            headers={},
                            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # create a good instance for the offer (1)
        resp = self.app.post('/good/add',
            data=json.dumps({
            'offer_id': offerid,
            'good_type': 'code',
            'value': 'abcd'}),
            headers={},
            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # register a couple of users
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

        userid2 = uuid4()
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

        userid3 = uuid4()
        resp = self.app.post('/user/register',
                             data=json.dumps({
                                 'user_id': str(userid3),
                                 'os': 'android',
                                 'device_model': 'samsung8',
                                 'device_id': '234234',
                                 'time_zone': '05:00',
                                 'token': 'fake_token',
                                 'app_ver': '1.0'}),
                             headers={},
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # onboard user 2 to set address in server
        kp = Keypair.random()
        address2 = kp.address().decode()
        resp = self.app.post('/user/onboard',
            data=json.dumps({
                            'public_address': address2}),
            headers={USER_ID_HEADER: str(userid2)},
            content_type='application/json')
        print(json.loads(resp.data))
        self.assertEqual(resp.status_code, 200)

        # onboard user 3 to set address in server
        kp = Keypair.random()
        address3 = kp.address().decode()
        resp = self.app.post('/user/onboard',
            data=json.dumps({
                            'public_address': address3}),
            headers={USER_ID_HEADER: str(userid3)},
            content_type='application/json')
        print(json.loads(resp.data))
        self.assertEqual(resp.status_code, 200)

        # onboard user 1 to set address in server
        kp = Keypair.random()
        address1 = kp.address().decode()
        resp = self.app.post('/user/onboard',
            data=json.dumps({
                            'public_address': address1}),
            headers={USER_ID_HEADER: str(userid1)},
            content_type='application/json')
        print(json.loads(resp.data))
        self.assertEqual(resp.status_code, 200)

        # get user1 p2p tx history - should have 0 item
        resp = self.app.get('/user/transactions', headers={USER_ID_HEADER: str(userid1)})
        self.assertEqual(resp.status_code, 200)
        #print('txs: %s' % json.loads(resp.data).encode('utf-8'))
        self.assertEqual(len(json.loads(resp.data)['txs']), 0)

        # user 1 updates his phone number to the server after client-side verification
        phone_num = '+972527702890'
        resp = self.app.post('/user/firebase/update-id-token',
                    data=json.dumps({
                        'token': phone_num,
                        'phone_number': phone_num}),
                    headers={USER_ID_HEADER: str(userid1)},
                    content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # user 2 updates his phone number to the server after client-side verification
        phone_num = '+972528802120'
        resp = self.app.post('/user/firebase/update-id-token',
                    data=json.dumps({
                        'token': phone_num,
                        'phone_number': phone_num}),
                    headers={USER_ID_HEADER: str(userid2)},
                    content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # user 3 updates his phone number to the server after client-side verification
        phone_num2 = '+9720528802121'
        resp = self.app.post('/user/firebase/update-id-token',
                    data=json.dumps({
                        'token': phone_num,
                        'phone_number': phone_num2}),
                    headers={USER_ID_HEADER: str(userid3)},
                    content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # user1 tries to get user2's address by contact info (exact match)
        print('trying to perform exact match of phone number....')
        resp = self.app.post('/user/contact',
                    data=json.dumps({
                        'phone_number': phone_num}),
                    headers={USER_ID_HEADER: str(userid1)},
                    content_type='application/json')
        data = json.loads(resp.data)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(data['status'], 'ok')
        self.assertEqual(data['address'], address2)

        # user1 tries to get user2's address by contact info (local number)
        print('trying to perform local match of phone number....')
        resp = self.app.post('/user/contact',
                             data=json.dumps({
                                 'phone_number': '0528802120'}),
                             headers={USER_ID_HEADER: str(userid1)},
                             content_type='application/json')
        data = json.loads(resp.data)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(data['status'], 'ok')
        self.assertEqual(data['address'], address2)

        # user1 tries to get user3's address by contact info (local number with leading zero after 972)
        print('trying to perform local match of phone number....')
        resp = self.app.post('/user/contact',
                             data=json.dumps({
                                 'phone_number': '0528802121'}),
                             headers={USER_ID_HEADER: str(userid1)},
                             content_type='application/json')
        data = json.loads(resp.data)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(data['status'], 'ok')
        self.assertEqual(data['address'], address3)

        # user1 sends money to user2

        # user1 reports tx to the server
        resp = self.app.post('user/transaction/p2p',
                    data=json.dumps({
                        'tx_hash': '3425f5a096ba5aaec49e9ee8912d84a8e11010f785fae6964c9ab85872193cb4',
                        'destination_address': address2,
                        'amount': 1}),
                    headers={USER_ID_HEADER: str(userid1)},
                    content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertEqual(data['status'], 'ok')

        # get user1 p2p tx history - should have 1 item
        resp = self.app.get('/user/transactions', headers={USER_ID_HEADER: str(userid1)})
        self.assertEqual(resp.status_code, 200)
        #print('txs: %s' % json.loads(resp.data).encode('utf-8'))
        self.assertEqual(len(json.loads(resp.data)['txs']), 1)

        # get user2 p2p tx history - should have 1 item
        resp = self.app.get('/user/transactions', headers={USER_ID_HEADER: str(userid2)})
        self.assertEqual(resp.status_code, 200)
        #print('txs: %s' % json.loads(resp.data).encode('utf-8'))
        self.assertEqual(len(json.loads(resp.data)['txs']), 1)


if __name__ == '__main__':
    unittest.main()
