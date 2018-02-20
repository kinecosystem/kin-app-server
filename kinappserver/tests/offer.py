import base64
import simplejson as json
from json import dumps as json_stringify
from time import mktime
from datetime import datetime
import unittest
from unittest import mock
import uuid

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

    def test_offer_storing(self):
        """test storting and getting offers"""
        offer = { 'offer_id': '0',
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

        # re-try to add the same offer - should fail
        resp = self.app.post('/offer/add',
                            data=json.dumps({
                            'offer': offer}),
                            headers={},
                            content_type='application/json')
        self.assertNotEqual(resp.status_code, 200)

        offer['offer_id'] = '1'
        offer['price'] = 100
        # try to add a new offer - should succeed
        resp = self.app.post('/offer/add',
                            data=json.dumps({
                            'offer': offer}),
                            headers={},
                            content_type='application/json')
        self.assertEqual(resp.status_code, 200)


        offer['offer_id'] = '2'
        offer['price'] = 50
        # try to add a new offer - should succeed
        resp = self.app.post('/offer/add',
                            data=json.dumps({
                            'offer': offer}),
                            headers={},
                            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        print(models.list_all_offer_data())

        # register a user
        userid = uuid.uuid4()
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

        # get the user's current offers - should be empty as no offers are enabled
        resp = self.app.get('/user/offers?user-id=%s' % userid)
        data = json.loads(resp.data)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(data['offers'], [])

        # no such offer - should fail
        resp = self.app.post('/offer/set_active',
                data=json.dumps({
                'offer_id': 'no-such-offer-id',
                'is_active': True}),
                headers={},
                content_type='application/json')
        self.assertEqual(resp.status_code, 400)

        # enable offer 0 
        resp = self.app.post('/offer/set_active',
                            data=json.dumps({
                            'offer_id': '0',
                            'is_active': True}),
                            headers={},
                            content_type='application/json')
        self.assertEqual(resp.status_code, 200)


        # get the user's current offers - should have one offer
        resp = self.app.get('/user/offers?user-id=%s' % userid)
        data = json.loads(resp.data)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(data['offers']), 1)

        # disable offer 0
        resp = self.app.post('/offer/set_active',
                    data=json.dumps({
                    'offer_id': '0',
                    'is_active': False}),
                    headers={},
                    content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # get the user's current offers - should have one offers again
        resp = self.app.get('/user/offers?user-id=%s' % userid)
        data = json.loads(resp.data)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(data['offers'], [])

        
        # enable offer 1 and 2
        resp = self.app.post('/offer/set_active',
                    data=json.dumps({
                    'offer_id': '1',
                    'is_active': True}),
                    headers={},
                    content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        resp = self.app.post('/offer/set_active',
                    data=json.dumps({
                    'offer_id': '0',
                    'is_active': True}),
                    headers={},
                    content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # get the user's current offers - should have 2 offers
        resp = self.app.get('/user/offers?user-id=%s' % userid)
        data = json.loads(resp.data)
        self.assertEqual(resp.status_code, 200)

        self.assertEqual(len(data['offers']), 2)

        resp = self.app.post('/offer/set_active',
            data=json.dumps({
            'offer_id': '2',
            'is_active': True}),
            headers={},
            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # get the user's current offers - should have 3 offers - check that the price is ascending
        resp = self.app.get('/user/offers?user-id=%s' % userid)
        data = json.loads(resp.data)
        self.assertEqual(resp.status_code, 200)

        self.assertEqual(len(data['offers']), 3)

        self.assertEqual((data['offers'][0]['price']), 50)
        self.assertEqual((data['offers'][1]['price']), 100)
        self.assertEqual((data['offers'][2]['price']), 800)



if __name__ == '__main__':
    unittest.main()
