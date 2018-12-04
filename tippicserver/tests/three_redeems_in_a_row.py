import simplejson as json
from uuid import uuid4
from time import sleep
import testing.postgresql

import unittest
import tippicserver
from tippicserver import db, stellar, models

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
        tippicserver.app.config['SQLALCHEMY_DATABASE_URI'] = self.postgresql.url()
        tippicserver.app.testing = True
        self.app = tippicserver.app.test_client()
        db.drop_all()
        db.create_all()


    def tearDown(self):
        self.postgresql.stop()


    def test_book_and_redeem_in_a_row(self):
        """test creating orders"""
        offerid = '0'
        offer = {'id': offerid,
                 'type': 'gift-card',
                 'type_image_url': "https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png",
                 'domain': 'music',
                 'title': 'offer_title',
                 'desc': 'offer_desc',
                 'image_url': 'image_url',
                 'price': 2,
                 'skip_image_test': True,
                 'address': 'GCYUCLHLMARYYT5EXJIK2KZJCMRGIKKUCCJKJOAPUBALTBWVXAT4F4OZ',
                 'provider': 
                    {'name': 'om-nom-nom-food', 'image_url': 'http://inter.webs/horsie.jpg'},
                }


        print('listing all orders: %s' % models.list_all_order_data())

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
            'value': 'abcd1'}),
            headers={},
            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # create a good instance for the offer (2)
        resp = self.app.post('/good/add',
            data=json.dumps({
            'offer_id': offerid,
            'good_type': 'code',
            'value': 'abcd2'}),
            headers={},
            content_type='application/json')
        self.assertEqual(resp.status_code, 200)
 

        # create a good instance for the offer (3)
        resp = self.app.post('/good/add',
            data=json.dumps({
            'offer_id': offerid,
            'good_type': 'code',
            'value': 'abcd3'}),
            headers={},
            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # create a good instance for the offer (4)
        resp = self.app.post('/good/add',
            data=json.dumps({
            'offer_id': offerid,
            'good_type': 'code',
            'value': 'abcd4'}),
            headers={},
            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # 4 goods at this point
        resp = self.app.get('/good/inventory')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(json.loads(resp.data)['inventory'], {offer['id']: {'total': 4, 'unallocated': 4}})


        # register a users
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

        db.engine.execute("""update public.push_auth_token set auth_token='%s' where user_id='%s';""" % (str(userid1), str(userid1)))

        resp = self.app.post('/user/auth/ack',
                             data=json.dumps({
                                 'token': str(userid1)}),
                             headers={USER_ID_HEADER: str(userid1)},
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        for _ in range(4):
            # create the order
            resp = self.app.post('/offer/book',
                        data=json.dumps({
                        'id': offerid}),
                        headers={USER_ID_HEADER: str(userid1)},
                        content_type='application/json')
            self.assertEqual(resp.status_code, 200)
            data = json.loads(resp.data)
            self.assertEqual(data['status'], 'ok')
            self.assertNotEqual(data['order_id'], None)
            orderid1 = data['order_id']
            print('order_id: %s' % orderid1)

            # pay for the order
            print('setting memo of %s' % orderid1)
            tx_hash = stellar.send_kin(offer['address'], offer['price'], orderid1)
            print('tx_hash: %s' % tx_hash)

            # try to redeem the goods - should work
            resp = self.app.post('/offer/redeem',
                        data=json.dumps({
                        'tx_hash': tx_hash}),
                        headers={USER_ID_HEADER: str(userid1)},
                        content_type='application/json')
            self.assertEqual(resp.status_code, 200)
            data = json.loads(resp.data)
            print(data)

        # no unallocated goods at this point
        resp = self.app.get('/good/inventory')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(json.loads(resp.data)['inventory'], {offer['id']: {'total': 4, 'unallocated': 0}})

        print('listing all orders: %s' % models.list_all_order_data())

if __name__ == '__main__':
    unittest.main()
