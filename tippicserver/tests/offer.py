import unittest
from uuid import uuid4
import json

import testing.postgresql

import tippicserver
from tippicserver import db, models

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
        tippicserver.app.config['SQLALCHEMY_DATABASE_URI'] = self.postgresql.url()
        tippicserver.app.testing = True
        self.app = tippicserver.app.test_client()
        db.drop_all()
        db.create_all()


    def tearDown(self):
        self.postgresql.stop()

    def test_offer_storing(self):
        """test storting and getting offers"""
        offer = { 'id': '0',
                  'type': 'gift-card',
                  'type_image_url': 'https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png',
                  'domain': 'music',
                  'title': 'offer_title',
                  'desc': 'offer_desc',
                  'image_url': 'https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png',
                  'price': 100,
                  'address': 'the address',
                  'provider': 
                    {'name': 'om-nom-nom-food', 'image_url': 'https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png'},
                }


        resp = self.app.post('/offer/add',
                            data=json.dumps({
                            'offer': offer}),
                            headers={},
                            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # no need to test images on this test.
        offer['skip_image_test'] = True

        # re-try to add the same offer - should fail
        print('trying to re-add the same offer')
        resp = self.app.post('/offer/add',
                            data=json.dumps({
                            'offer': offer}),
                            headers={},
                            content_type='application/json')
        self.assertNotEqual(resp.status_code, 200)

        offer['id'] = '1'
        offer['price'] = 100
        # try to add a new offer - should succeed
        resp = self.app.post('/offer/add',
                            data=json.dumps({
                            'offer': offer}),
                            headers={},
                            content_type='application/json')
        self.assertEqual(resp.status_code, 200)


        offer['id'] = '2'
        offer['price'] = 50
        # try to add a new offer - should succeed
        resp = self.app.post('/offer/add',
                            data=json.dumps({
                            'offer': offer}),
                            headers={},
                            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        offer['id'] = '3'
        offer['price'] = 50
        # try to add a new offer - should succeed
        resp = self.app.post('/offer/add',
                            data=json.dumps({
                            'offer': offer}),
                            headers={},
                            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # add an offer that's only for ios
        offer['id'] = '4'
        offer['price'] = 2500
        offer['min_client_version_android'] = '99.99'
        # try to add a new offer - should succeed
        resp = self.app.post('/offer/add',
                            data=json.dumps({
                            'offer': offer}),
                            headers={},
                            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # add an offer that's only for android
        offer['id'] = '5'
        offer['price'] = 2000
        offer.pop('min_client_version_android')
        offer['min_client_version_ios'] = '99.99'
        # try to add a new offer - should succeed
        resp = self.app.post('/offer/add',
                            data=json.dumps({
                            'offer': offer}),
                            headers={},
                            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        print('all offers: %s' % models.list_all_offer_data())

        # create a good instance for the offer (0)
        resp = self.app.post('/good/add',
            data=json.dumps({
            'offer_id': '0',
            'good_type': 'code',
            'value': 'abcd'}),
            headers={},
            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # create a good instance for the offer (1)
        resp = self.app.post('/good/add',
            data=json.dumps({
            'offer_id': '1',
            'good_type': 'code',
            'value': 'abcd1'}),
            headers={},
            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # create a good instance for the offer (2)
        resp = self.app.post('/good/add',
            data=json.dumps({
            'offer_id': '2',
            'good_type': 'code',
            'value': 'abcd2'}),
            headers={},
            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # create a good instance for the offer (4)
        resp = self.app.post('/good/add',
            data=json.dumps({
            'offer_id': '4',
            'good_type': 'code',
            'value': 'abcd3'}),
            headers={},
            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # create a good instance for the offer (5)
        resp = self.app.post('/good/add',
            data=json.dumps({
            'offer_id': '5',
            'good_type': 'code',
            'value': 'abcd4'}),
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

        # register another user - ios
        ios_userid = uuid4()
        resp = self.app.post('/user/register',
            data=json.dumps({
                            'user_id': str(ios_userid),
                            'os': 'iOS',
                            'device_model': 'samsung8',
                            'device_id': '234234',
                            'time_zone': '05:00',
                            'token': 'fake_token',
                            'app_ver': '1.0'}),
            headers={},
            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        resp = self.app.get('/good/inventory')
        self.assertEqual(resp.status_code, 200)
        print(json.loads(resp.data)['inventory'])


        # get the user's current offers - should be empty as no offers are enabled
        headers = {USER_ID_HEADER: userid}
        resp = self.app.get('/user/offers', headers=headers)
        data = json.loads(resp.data)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(data['offers'], [])

        # no such offer - should fail
        resp = self.app.post('/offer/set_active',
                data=json.dumps({
                'id': 'no-such-offer-id',
                'is_active': True}),
                headers={},
                content_type='application/json')
        self.assertEqual(resp.status_code, 400)

        # enable offer 0 
        resp = self.app.post('/offer/set_active',
                            data=json.dumps({
                            'id': '0',
                            'is_active': True}),
                            headers={},
                            content_type='application/json')
        self.assertEqual(resp.status_code, 200)


        # get the user's current offers - should have one offer
        headers = {USER_ID_HEADER: userid}
        resp = self.app.get('/user/offers', headers=headers)
        data = json.loads(resp.data)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(data['offers']), 1)

        # disable offer 0
        resp = self.app.post('/offer/set_active',
                    data=json.dumps({
                    'id': '0',
                    'is_active': False}),
                    headers={},
                    content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # get the user's current offers - should have one offers again
        headers = {USER_ID_HEADER: userid}
        resp = self.app.get('/user/offers', headers=headers)
        data = json.loads(resp.data)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(data['offers'], [])
        
        # enable offer 1,2,4,5
        resp = self.app.post('/offer/set_active',
                    data=json.dumps({
                    'id': '0',
                    'is_active': True}),
                    headers={},
                    content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        resp = self.app.post('/offer/set_active',
                    data=json.dumps({
                    'id': '1',
                    'is_active': True}),
                    headers={},
                    content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        resp = self.app.post('/offer/set_active',
                    data=json.dumps({
                    'id': '4',
                    'is_active': True}),
                    headers={},
                    content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        resp = self.app.post('/offer/set_active',
                    data=json.dumps({
                    'id': '5',
                    'is_active': True}),
                    headers={},
                    content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # get the user's current offers - should have 3 offers [1,2,5]
        headers = {USER_ID_HEADER: userid}
        resp = self.app.get('/user/offers', headers=headers)
        data = json.loads(resp.data)
        self.assertEqual(resp.status_code, 200)

        self.assertEqual(len(data['offers']), 3)

        resp = self.app.post('/offer/set_active',
            data=json.dumps({
            'id': '2',
            'is_active': True}),
            headers={},
            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # get the user's current offers - should have 5 offers - check that the price is ascending
        headers = {USER_ID_HEADER: userid}
        resp = self.app.get('/user/offers', headers=headers)
        data = json.loads(resp.data)
        self.assertEqual(resp.status_code, 200)

        self.assertEqual(len(data['offers']), 4)

        self.assertEqual((data['offers'][0]['price']), 50)
        self.assertEqual((data['offers'][1]['price']), 100)
        self.assertEqual((data['offers'][2]['price']), 100)
        self.assertEqual((data['offers'][3]['price']), 2000) # android task

        resp = self.app.post('/offer/set_active',
            data=json.dumps({
            'id': '3',
            'is_active': True}),
            headers={},
            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # get the user's current offers - should have 4 offers
        headers = {USER_ID_HEADER: userid}
        resp = self.app.get('/user/offers', headers=headers)
        data = json.loads(resp.data)
        print(data)
        self.assertEqual(resp.status_code, 200)

        self.assertEqual(len(data['offers']), 4)

        # get the ios user's current offers - should have 4 offers
        headers = {USER_ID_HEADER: ios_userid}
        resp = self.app.get('/user/offers', headers=headers)
        data = json.loads(resp.data)
        print(data)
        self.assertEqual(resp.status_code, 200)

        self.assertEqual(len(data['offers']), 4)

        self.assertEqual((data['offers'][0]['price']), 50)
        self.assertEqual((data['offers'][1]['price']), 100)
        self.assertEqual((data['offers'][2]['price']), 100)
        self.assertEqual((data['offers'][3]['price']), 2500) # ios task


        


if __name__ == '__main__':
    unittest.main()
