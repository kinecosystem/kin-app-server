
import simplejson as json
import unittest
from uuid import uuid4
from time import sleep

import testing.postgresql

import kinappserver
from kinappserver import db, models
import validation_module
import base64
import logging as log
log.getLogger().setLevel(log.INFO)


USER_ID_HEADER = "X-USERID"


class Tester(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        pass

    def setUp(self):
        # overwrite the db name, dont interfere with stage db data
        self.postgresql = testing.postgresql.Postgresql()
        kinappserver.app.config['SQLALCHEMY_DATABASE_URI'] = self.postgresql.url(
        )
        kinappserver.app.testing = True
        self.app = kinappserver.app.test_client()
        db.drop_all()
        db.create_all()

    def tearDown(self):
        self.postgresql.stop()

    def test_orders(self):
        """test creating oders"""
        offerid = '0'
        offer = {'id': offerid,
                 'type': 'gift-card',
                 'type_image_url': "https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png",
                 'domain': 'music',
                 'title': 'offer_title',
                 'desc': 'offer_desc',
                 'image_url': 'image_url',
                 'price': 800,
                 'address': 'the address',
                 'skip_image_test': True,
                 'provider':
                 {'name': 'om-nom-nom-food',
                  'image_url': 'http://inter.webs/horsie.jpg'},
                 }

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

        db.engine.execute("""update public.push_auth_token set auth_token='%s' where user_id='%s';""" % (
            str(userid), str(userid)))

        resp = self.app.post('/user/auth/ack',
                             data=json.dumps({
                                 'token': str(userid)}),
                             headers={USER_ID_HEADER: str(userid)},
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # add an instance of goods
        resp = self.app.post('/good/add',
                             data=json.dumps({
                                 'offer_id': offerid,
                                 'good_type': 'code',
                                 'value': 'abcd1'}),
                             headers={},
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # add an instance of goods (1)
        resp = self.app.post('/good/add',
                             data=json.dumps({
                                 'offer_id': offerid,
                                 'good_type': 'code',
                                 'value': 'abcd2'}),
                             headers={},
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # add an instance of goods (2)
        resp = self.app.post('/good/add',
                             data=json.dumps({
                                 'offer_id': offerid,
                                 'good_type': 'code',
                                 'value': 'abcd3'}),
                             headers={},
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # add an instance of goods (3)
        resp = self.app.post('/good/add',
                             data=json.dumps({
                                 'offer_id': offerid,
                                 'good_type': 'code',
                                 'value': 'abcd4'}),
                             headers={},
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # get nonce
        resp = self.app.get('/validation/get-nonce',
                            headers={USER_ID_HEADER: str(userid)})
        data = json.loads(resp.data)
        self.assertIsNotNone(data['nonce'])
        nonce = data['nonce']

        # mock valid token
        payload = validation_module.config.MOCK_PAYLOAD % nonce
        byte_pl = base64.b64encode(payload.encode('ascii')).decode("utf-8")
        token = validation_module.config.TOKEN % (byte_pl)

        # create the first order (books item 1)
        resp = self.app.post('/offer/book',
                             data=json.dumps({
                                 'id': offerid, 'validation_token': token}),
                             headers={USER_ID_HEADER: str(userid)},
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertEqual(data['status'], 'ok')
        self.assertNotEqual(data['order_id'], None)
        orderid1 = data['order_id']
        print('order_id: %s' % orderid1)

        # get nonce
        resp = self.app.get('/validation/get-nonce',
                            headers={USER_ID_HEADER: str(userid)})
        data = json.loads(resp.data)
        self.assertIsNotNone(data['nonce'])
        nonce = data['nonce']

        # mock valid token
        payload = validation_module.config.MOCK_PAYLOAD % nonce
        byte_pl = base64.b64encode(payload.encode('ascii')).decode("utf-8")
        token = validation_module.config.TOKEN % (byte_pl)

        # create another order for the same offer (books item 2)
        resp = self.app.post('/offer/book',
                             data=json.dumps({
                                 'id': offerid, 'validation_token': token}),
                             headers={USER_ID_HEADER: str(
                                 userid)},
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertEqual(data['status'], 'ok')
        self.assertNotEqual(data['order_id'], None)
        orderid2 = data['order_id']
        print('order_id: %s' % orderid2)

        # get nonce
        resp = self.app.get('/validation/get-nonce',
                            headers={USER_ID_HEADER: str(userid)})
        data = json.loads(resp.data)
        self.assertIsNotNone(data['nonce'])
        nonce = data['nonce']

        # mock valid token
        payload = validation_module.config.MOCK_PAYLOAD % nonce
        byte_pl = base64.b64encode(payload.encode('ascii')).decode("utf-8")
        token = validation_module.config.TOKEN % (byte_pl)

        # should fail as there are already 2 active orders
        resp = self.app.post('/offer/book',
                             data=json.dumps({
                                 'id': offerid, 'validation_token': token}),
                             headers={USER_ID_HEADER: str(
                                 userid)},
                             content_type='application/json')
        self.assertNotEqual(resp.status_code, 200)

        # wait for the order to expire
        print('sleeping 16 secs')
        sleep(16)  # TODO read from config
        print('done! now trying to book a new order')

        # should fail no validation token
        resp = self.app.post('/offer/book',
                             data=json.dumps({
                                 'id': offerid}),
                             headers={USER_ID_HEADER: str(
                                 userid)},
                             content_type='application/json')
        print(json.loads(resp.data))
        self.assertEqual(resp.status_code, 400)

        # get nonce
        resp = self.app.get('/validation/get-nonce',
                            headers={USER_ID_HEADER: str(userid)})
        data = json.loads(resp.data)
        self.assertIsNotNone(data['nonce'])
        nonce = data['nonce']

        # mock invalid token
        payload = validation_module.config.MOCK_INVALID_PAYLOAD
        byte_pl = base64.b64encode(payload.encode('ascii')).decode("utf-8")
        token = validation_module.config.TOKEN % (byte_pl)

        # should fail no validation token
        resp = self.app.post('/offer/book',
                             data=json.dumps({
                                 'id': offerid, 'validation_token': token}),
                             headers={USER_ID_HEADER: str(
                                 userid)},
                             content_type='application/json')
        print(json.loads(resp.data))
        self.assertEqual(resp.status_code, 400)

        # get nonce
        resp = self.app.get('/validation/get-nonce',
                            headers={USER_ID_HEADER: str(userid)})
        data = json.loads(resp.data)
        self.assertIsNotNone(data['nonce'])
        nonce = data['nonce']

        # mock invalid token
        payload = validation_module.config.MOCK_PAYLOAD % nonce
        byte_pl = base64.b64encode(payload.encode('ascii')).decode("utf-8")
        token = validation_module.config.TOKEN % (byte_pl)

        # should succeed now
        resp = self.app.post('/offer/book',
                             data=json.dumps({
                                 'id': offerid, 'validation_token': token}),
                             headers={USER_ID_HEADER: str(
                                 userid)},
                             content_type='application/json')
        print(json.loads(resp.data))
        data = json.loads(resp.data)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(data['status'], 'ok')
        self.assertNotEqual(data['order_id'], None)


if __name__ == '__main__':
    unittest.main()
