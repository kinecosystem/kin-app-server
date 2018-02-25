
import simplejson as json
import unittest
from uuid import uuid4
from time import sleep

import testing.postgresql

import kinappserver
from kinappserver import db, models


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
        offer = { 'offer_id': offerid,
                  'type': 'gift-card',
                  'domain': 'music',
                  'title': 'offer_title',
                  'desc': 'offer_desc',
                  'image_url': 'image_url',
                  'price': 800,
                  'address': 'the address',
                  'provider': 
                    {'name': 'om-nom-nom-food', 'logo_url': 'http://inter.webs/horsie.jpg'},
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
                            'offer_id': offerid,
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
                            'time_zone': '+05:00',
                            'token': 'fake_token',
                            'app_ver': '1.0'}),
            headers={},
            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # create the first order
        resp = self.app.post('/offer/book',
                    data=json.dumps({
                    'id': offerid}),
                    headers={USER_ID_HEADER: str(userid)},
                    content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertEqual(data['status'],'ok')
        self.assertNotEqual(data['order_id'], None)
        orderid1 = data['order_id']
        print('order_id: %s' % orderid1)

        # create another order for the same offer
        resp = self.app.post('/offer/book',
                    data=json.dumps({
                    'id': offerid}),
                    headers={USER_ID_HEADER: str(userid)},
                    content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertEqual(data['status'],'ok')
        self.assertNotEqual(data['order_id'], None)
        orderid2 = data['order_id']
        print('order_id: %s' % orderid2)

        # should fail as there are already 2 active orders
        resp = self.app.post('/offer/book',
                    data=json.dumps({
                    'id': offerid}),
                    headers={USER_ID_HEADER: str(userid)},
                    content_type='application/json')
        self.assertNotEqual(resp.status_code, 200)

        # delete one active order
        res = models.delete_order(orderid2)

        # try to delete it again, should fail
        try:
            models.delete_order(orderid2)
        except Exception as e:
            pass
        else:
            self.fail('did not catch expected exception')

        # should succeed now
        resp = self.app.post('/offer/book',
                    data=json.dumps({
                    'id': offerid}),
                    headers={USER_ID_HEADER: str(userid)},
                    content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(data['status'],'ok')
        self.assertNotEqual(data['order_id'], None)

        # should fail as there are already 2 active orders
        resp = self.app.post('/offer/book',
                    data=json.dumps({
                    'id': offerid}),
                    headers={USER_ID_HEADER: str(userid)},
                    content_type='application/json')
        self.assertNotEqual(resp.status_code, 200)

        # wait for the order to expire
        print('sleeping 16 secs')
        sleep(16) # TODO read from config
        print('done! now trying to book a new order')

        # should succeed now
        resp = self.app.post('/offer/book',
                    data=json.dumps({
                    'id': offerid}),
                    headers={USER_ID_HEADER: str(userid)},
                    content_type='application/json')
        print(json.loads(resp.data))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(data['status'],'ok')
        self.assertNotEqual(data['order_id'], None)


if __name__ == '__main__':
    unittest.main()
