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


    def test_book_and_redeem(self):
        """test creating orders"""
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

        db.engine.execute("""update public.push_auth_token set auth_token='%s' where user_id='%s';""" % (str(userid2), str(userid2)))
        db.engine.execute("""update public.push_auth_token set auth_token='%s' where user_id='%s';""" % (str(userid1), str(userid1)))

        resp = self.app.post('/user/auth/ack',
                            data=json.dumps({
                            'token': str(userid2)}),
                            headers={USER_ID_HEADER: str(userid2)},
                            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        resp = self.app.post('/user/auth/ack',
                            data=json.dumps({
                            'token': str(userid1)}),
                            headers={USER_ID_HEADER: str(userid1)},
                            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # get user2 redeem history - should be empty
        resp = self.app.get('/user/redeemed', headers={USER_ID_HEADER: str(userid2)})
        self.assertEqual(resp.status_code, 200)
        print('redeemed: %s' % json.loads(resp.data))
        self.assertEqual(json.loads(resp.data)['redeemed'], [])

        # get user2 tx history - should have 0 items
        resp = self.app.get('/user/transactions', headers={USER_ID_HEADER: str(userid2)})
        self.assertEqual(resp.status_code, 200)
        print('txs: %s' % json.loads(resp.data))
        self.assertEqual(json.loads(resp.data)['txs'], [])

        # create the first order
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

        # pay for the order but give a differet address - should fail
        print('setting memo of %s' % orderid1)
        tx_hash_wrong_address = stellar.send_kin('GCKG5WGBIJP74UDNRIRDFGENNIH5Y3KBI5IHREFAJKV4MQXLELT7EX6V', offer['price'], orderid1)
        print('tx_hash: %s' % tx_hash_wrong_address)

        # try to redeem the goods with the tx_hash - should fail
        print('trying to redeem with the wrong address...')
        resp = self.app.post('/offer/redeem',
                    data=json.dumps({
                    'tx_hash': tx_hash_wrong_address}),
                    headers={USER_ID_HEADER: str(userid1)},
                    content_type='application/json')
        self.assertNotEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        print(data)

        # re-create the first order
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

        # pay for the order - but pay less than expected
        print('setting memo of %s' % orderid1)
        tx_hash_pay_less = stellar.send_kin(offer['address'], offer['price'] - 1, orderid1)
        print('tx_hash: %s' % tx_hash_pay_less)

        # try to redeem the goods - shuld fail
        print('trying to redeem with underpayed tx...')
        resp = self.app.post('/offer/redeem',
                    data=json.dumps({
                    'tx_hash': tx_hash_pay_less}),
                    headers={USER_ID_HEADER: str(userid1)},
                    content_type='application/json')
        self.assertNotEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        print(data)

        # re-create the order (use userid2 now)
        resp = self.app.post('/offer/book',
                    data=json.dumps({
                    'id': offerid}),
                    headers={USER_ID_HEADER: str(userid2)},
                    content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertEqual(data['status'], 'ok')
        self.assertNotEqual(data['order_id'], None)
        orderid1 = data['order_id']
        print('order_id: %s' % orderid1)

        # pay for the order - but use an invalid orderid
        print('setting memo of %s' % orderid1)
        tx_hash_other_orderid = stellar.send_kin(offer['address'], offer['price'], "other_order_id")
        print('tx_hash: %s' % tx_hash_other_orderid)

        # try to redeem the goods - should fail
        print('trying to redeem with unknown order_id...')
        resp = self.app.post('/offer/redeem',
                    data=json.dumps({
                    'tx_hash': tx_hash_other_orderid}),
                    headers={USER_ID_HEADER: str(userid2)},
                    content_type='application/json')
        self.assertNotEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        print(data)

        # re-create the order
        resp = self.app.post('/offer/book',
                    data=json.dumps({
                    'id': offerid}),
                    headers={USER_ID_HEADER: str(userid2)},
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
                    headers={USER_ID_HEADER: str(userid2)},
                    content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        print(data)

        # get user2 redeem history - should have one item
        resp = self.app.get('/user/redeemed', headers={USER_ID_HEADER: str(userid2)})
        self.assertEqual(resp.status_code, 200)
        print('redeemed: %s' % json.loads(resp.data))
        self.assertEqual(len(json.loads(resp.data)['redeemed']), 1)

        # get user2 tx history - should have 2 items
        resp = self.app.get('/user/transactions', headers={USER_ID_HEADER: str(userid2)})
        self.assertEqual(resp.status_code, 200)
        print('txs: %s' % json.loads(resp.data))
        self.assertEqual(len(json.loads(resp.data)['txs']), 1)

        # no unallocated goods at this point
        resp = self.app.get('/good/inventory')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(json.loads(resp.data)['inventory'], {offer['id']: {'total': 4, 'unallocated': 0}})

        print('listing all orders: %s' % models.list_all_order_data())

        # user updates his phone number to the server after client-side verification
        phone_num = '+9720528802120'
        resp = self.app.post('/user/firebase/update-id-token',
                    data=json.dumps({
                        'token': 'fake-token',
                        'phone_number': phone_num}),
                    headers={USER_ID_HEADER: str(userid2)},
                    content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        resp = self.app.post('/user/nuke-data',
                             data=json.dumps({
                                 'phone_number': phone_num}),
                            headers={USER_ID_HEADER: str(userid2)},
                            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        resp = self.app.post('/user/nuke-data',
                             data=json.dumps({
                                 'phone_number': phone_num,
                                    'nuke_all': True}),
                            headers={USER_ID_HEADER: str(userid2)},
                            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

if __name__ == '__main__':
    unittest.main()
