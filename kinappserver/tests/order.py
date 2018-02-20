import base64
import simplejson as json
from json import dumps as json_stringify
from time import mktime
from datetime import datetime
import unittest
from unittest import mock
from uuid import uuid4

import mockredis
import redis
import testing.postgresql
from flask import Flask

import kinappserver
from kinappserver import db, config, models

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
        order_id1 = models.create_order(userid, offerid)
        self.assertNotEqual(order_id1, None)
        print(order_id1)

        # create the second order
        order_id2 = models.create_order(userid, offerid)
        self.assertNotEqual(order_id2, None)
        print(order_id2)

        # should fail as there are already 2 active orders
        order_id3 = models.create_order(userid, offerid)
        self.assertEqual(order_id3, None)

        # delete one active order
        res = models.delete_order(order_id2)

        # try to delete it again, should fail
        try:
            models.delete_order(order_id2)
        except Exception as e:
            pass
        else:
            self.fail('did not catch expected exception')

        # should succeed now
        order_id3 = models.create_order(userid, offerid)
        self.assertNotEqual(order_id3, None)



if __name__ == '__main__':
    unittest.main()
