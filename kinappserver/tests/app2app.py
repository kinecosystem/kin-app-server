import simplejson as json
from uuid import uuid4
from time import sleep
import testing.postgresql

import unittest
import kinappserver
from kinappserver import db, stellar, models

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


    def test_app2app_report(self):
        """test reporting a app2app tx
        USER_ID_HEADER = "X-USERID"
        {
            'tx_hash': 'hash',
            'destination_app_sid': '1234-abcd...',
            'destination_address': 'accountaddress',
            'amount': 100
        }
        """
        from stellar_base.keypair import Keypair

        # register a user
        userid = uuid4()
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


        db.engine.execute("""update public.push_auth_token set auth_token='%s' where user_id='%s';""" % (str(userid), str(userid)))

        resp = self.app.post('/user/auth/ack',
                             data=json.dumps({
                                 'token': str(userid)}),
                             headers={USER_ID_HEADER: str(userid)},
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # onboard user to set address in server
        kp = Keypair.random()
        address = kp.address().decode()
        resp = self.app.post('/user/onboard',
            data=json.dumps({
                            'public_address': address}),
            headers={USER_ID_HEADER: str(userid)},
            content_type='application/json')
        print(json.loads(resp.data))
        self.assertEqual(resp.status_code, 200)

        # get user1 p2p tx history - should have 0 item
        resp = self.app.get('/user/transactions', headers={USER_ID_HEADER: str(userid)})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(json.loads(resp.data)['txs']), 0)

        # user 1 updates his phone number to the server after client-side verification
        phone_num = '+972527702890'
        resp = self.app.post('/user/firebase/update-id-token',
                    data=json.dumps({
                        'token': phone_num,
                        'phone_number': phone_num}),
                    headers={USER_ID_HEADER: str(userid)},
                    content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # create a category
        cat = {
            'category_id': '0',
            'category_name': 'Travel & Local'
        }
        # add category to db
        resp = self.app.post('/app_discovery/add_category',
                             data=json.dumps({
                                 'discovery_app_category': cat}),
                             headers={},
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # create an android app
        app = {
            'skip_image_test': 'true',
            "identifier": "com.addme.android",
            "is_active": "true",
            "category_id": 0,
            "os_type": "android",
            "name": "Addme Android",
            "meta_data": {
                "app_url": "https://play.google.com/store/apps/details?id=org.kinecosystem.kinit&hl=en",
                "card_image_url": "https://cdn.kinitapp.com/brand_img/airbnb.png",
                "short_description": "Ask questions to the community.",
                "description": "Beseech is a place for local communities to gather,  exchange advice, create connections, trade, and compete.",
                "icon_url": "https://cdn.kinitapp.com/brand_img/soyummy.jpg",
                "image_url_0": "https://cdn.kinitapp.com/brand_img/amazon.png",
                "image_url_1": "https://cdn.kinitapp.com/brand_img/soyummy.jpg",
                "image_url_2": "https://cdn.kinitapp.com/brand_img/airbnb.png",
                "kin_usage": "How to earn Kin: - Answer questions posted by other others - the most helpful answer will receive the Kin posted as a reward for the question How to spend Kin: - Ask questions to the community. The Kin spent to post the question will be the reward given to the most helpful answer.",
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
        resp = self.app.get('/app_discovery', headers={USER_ID_HEADER: str(userid)})
        self.assertEqual(resp.status_code, 200)


        # report a tx from kinit to demo app
        kp = Keypair.random() # generate random address for secod app wallet
        address = kp.address().decode()

        resp = self.app.post('/user/transaction/app2app',
            data=json.dumps({
                'tx_hash': 'F4F3C3BC99EE346C1D37FE28263FC2B3D44802A5753DEADB8262DADC2771386AJSON',
                'destination_app_sid': 1,
                'destination_address': address,
                'amount': 100
            }),
            headers={USER_ID_HEADER: str(userid)},
            content_type='application/json')
        print(json.loads(resp.data))
        self.assertEqual(resp.status_code, 200)

        # validate tx in history
        # get user p2p tx history - should have 1 (app2app) item
        resp = self.app.get('/user/transactions', headers={USER_ID_HEADER: str(userid)})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(json.loads(resp.data)['txs']), 1)


if __name__ == '__main__':
    unittest.main()
