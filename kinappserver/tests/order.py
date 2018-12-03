
import simplejson as json
import unittest
from uuid import uuid4
from time import sleep

import testing.postgresql

import kinappserver
from kinappserver import db, models, utils
from kinappserver.config import SERVERSIDE_CLIENT_VALIDATION_ENABLED
from kinit_client_validation_module.config import MOCK_B64_NONCE, MOCK_B64_TOKEN, NONCE_REDIS_KEY

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


    def tearDown(self):
        self.postgresql.stop()

    def test_orders(self):
        """test creating oders"""
        offerid = '0'
        offer = { 'id': offerid,
                  'type': 'gift-card',
                  'type_image_url': "https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png",
                  'domain': 'music',
                  'title': 'offer_title',
                  'desc': 'offer_desc',
                  'image_url': 'image_url',
                  'price': 1,
                  'address': 'the address',
                  'skip_image_test': True,
                  'provider': 
                    {'name': 'om-nom-nom-food', 'image_url': 'http://inter.webs/horsie.jpg'},
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
                            'app_ver': '1.4.1'}),
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


         # user updates his phone number to the server after client-side verification
        phone_num = '+972111111111'
        resp = self.app.post('/user/firebase/update-id-token',
                    data=json.dumps({
                        'token': 'fake-token',
                        'phone_number': phone_num}),
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

        # store a mocked token
        utils.write_json_to_cache(NONCE_REDIS_KEY % str(userid),MOCK_B64_NONCE)
        
        # create the first order (books item 1) - no funds - should fail
        resp = self.app.post('/offer/book',
                    data=json.dumps({
                    'id': offerid, 'validation-token': MOCK_B64_TOKEN}),
                    headers={USER_ID_HEADER: str(userid)},
                    content_type='application/json')
        self.assertEqual(resp.status_code,400)

        
        # add transactions to the user
        from kinappserver.models.transaction import create_tx
        create_tx("AAA", userid, "someaddress", False, 100, {'task_id': 1, 'memo': 'AAA'})

        # store a mocked token
        utils.write_json_to_cache(NONCE_REDIS_KEY % str(userid),MOCK_B64_NONCE)

        # create the first order (books item 1)
        resp = self.app.post('/offer/book',
                    data=json.dumps({
                    'id': offerid, 'validation-token': MOCK_B64_TOKEN}),
                    headers={USER_ID_HEADER: str(userid)},
                    content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertEqual(data['status'], 'ok')
        self.assertNotEqual(data['order_id'], None)
        orderid1 = data['order_id']
        print('order_id: %s' % orderid1)



         # store a mocked token
        utils.write_json_to_cache(NONCE_REDIS_KEY % str(userid),MOCK_B64_NONCE)

        # create another order for the same offer (books item 2)
        resp = self.app.post('/offer/book',
                    data=json.dumps({
                    'id': offerid, 'validation-token': MOCK_B64_TOKEN}),
                    headers={USER_ID_HEADER: str(userid)},
                    content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertEqual(data['status'], 'ok')
        self.assertNotEqual(data['order_id'], None)
        orderid2 = data['order_id']
        print('order_id: %s' % orderid2)

         # store a mocked token
        utils.write_json_to_cache(NONCE_REDIS_KEY % str(userid),MOCK_B64_NONCE)
        

        # should fail as there are already 2 active orders
        resp = self.app.post('/offer/book',
                    data=json.dumps({
                    'id': offerid, 'validation-token': MOCK_B64_TOKEN}),
                    headers={USER_ID_HEADER: str(userid)},
                    content_type='application/json')
        self.assertNotEqual(resp.status_code, 200)

        # wait for the order to expire
        print('sleeping 16 secs')
        sleep(16) # TODO read from config
        print('done! now trying to book a new order')
        
        # should fail if config is True -  no validation token
        resp = self.app.post('/offer/book',
                             data=json.dumps({
                                 'id': offerid}),
                             headers={USER_ID_HEADER: str(
                                 userid)},
                             content_type='application/json')
        print(json.loads(resp.data))
        if SERVERSIDE_CLIENT_VALIDATION_ENABLED:
            self.assertEqual(resp.status_code, 400)
        else:
            self.assertEqual(resp.status_code, 200)

         # store a mocked token
        utils.write_json_to_cache(NONCE_REDIS_KEY % str(userid),MOCK_B64_NONCE)
        
        # should succeed now
        resp = self.app.post('/offer/book',
                    data=json.dumps({
                    'id': offerid, 'validation-token': MOCK_B64_TOKEN}),
                    headers={USER_ID_HEADER: str(userid)},
                    content_type='application/json')
        print(json.loads(resp.data))
        data = json.loads(resp.data)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(data['status'], 'ok')
        self.assertNotEqual(data['order_id'], None)


if __name__ == '__main__':
    unittest.main()
