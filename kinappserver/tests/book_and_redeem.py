import base64
import simplejson as json
from json import dumps as json_stringify
from time import mktime
from datetime import datetime
import unittest
from unittest import mock
from uuid import uuid4
from time import sleep

import mockredis
import redis
import testing.postgresql
from flask import Flask

import kinappserver
from kinappserver import db, config, models, stellar


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
                  'price': 2,
                  'address': 'GCORIYYEQP3ANHFT6XHMBY7VB3RH53WB5KZZHGCEXYRWCEJQZUXPGWQM',
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


        # send the moneys with the order id
        tx_hash = send_kin(address['address', offer['price'], memo=orderid1)
        print('tx_hash: %s' % tx_hash)

        print('sleeping 2 seconds...')
        sleep(2)

        # create the first order
        resp = self.app.post('/offer/redeem',
                    data=json.dumps({
                    'order_id': offerid, 
                    'tx_hash': tx_hash}),
                    headers={USER_ID_HEADER: str(userid)},
                    content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        print(data)

       


if __name__ == '__main__':
    unittest.main()
