import simplejson as json
from uuid import uuid4
from time import sleep
import testing.postgresql

import unittest
import tippicserver
from tippicserver import db, stellar, models
from tippicserver.models.transaction import create_tx

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


    def test_book_and_dont_redeem(self):
        """test creating orders but not redeeming them"""

        cat = {'id': '0',
        'title': 'cat-title',
        'supported_os': 'all',
        'ui_data': {'color': "#something",
                    'image_url': 'https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png',
                    'header_image_url': 'https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png'}}

        resp = self.app.post('/category/add',
                            data=json.dumps({
                            'category': cat}),
                            headers={},
                            content_type='application/json')
        self.assertEqual(resp.status_code, 200)


        task = {  'title': 'do you know horses?',
                  'desc': 'horses_4_dummies',
                  'type': 'questionnaire',
                  'position': 0,
                  'cat_id': '0',
                  'task_id': '0',
                  'price': 100,
                  'min_to_complete': 2,
                  'skip_image_test': False, # test link-checking code
                  'tags': ['music',  'crypto', 'movies', 'kardashians', 'horses'],
                  'provider': 
                    {'name': 'om-nom-nom-food', 'image_url': 'https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png'},
                  'post_task_actions':[{'type': 'external-url',
                                        'text': 'please vote mofos',
                                        'text_ok': 'yes! register!',
                                        'text_cancel': 'no thanks mofos',
                                        'url': 'https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png',
                                        'icon_url': 'https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png',
                                        'campaign_name': 'buy-moar-underwear'}],
                  'items': [
                    {
                     'id': '435', 
                     'text': 'what animal is this?',
                     'image_url': 'https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png',
                     'type': 'textimage',
                         'results': [
                                {'id': '235',
                                 'text': 'a horse!', 
                                 'image_url': 'https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png'},
                                    {'id': '2465436',
                                 'text': 'a cat!', 
                                 'image_url': 'https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png'},
                                 ],
                    }]
            }

        # task_id isn't given, should be '0'
        resp = self.app.post('/task/add', # task_id should be 0
                            data=json.dumps({
                            'task': task}),
                            headers={},
                            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        offerid = '0'
        offer = {'id': offerid,
                 'type': 'gift-card',
                 'type_image_url': "https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png",
                 'domain': 'music',
                 'title': 'offer_title',
                 'desc': 'offer_desc',
                 'image_url': 'image_url',
                 'price': 2,
                 'address': 'GCYUCLHLMARYYT5EXJIK2KZJCMRGIKKUCCJKJOAPUBALTBWVXAT4F4OZ',
                 'skip_image_test': True,
                 'provider':
                    {'name': 'om-nom-nom-food', 'image_url': 'http://inter.webs/horsie.jpg'},
                }

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
            'value': 'abcd'}),
            headers={},
            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # register a couple of users
        userid1 = uuid4()
        resp = self.app.post('/user/register',
            data=json.dumps({
                            'user_id': str(userid1),
                            'os': 'android',
                            'device_model': 'samsung8',
                            'device_id': '234234',
                            'time_zone': '',
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

        # user updates his phone number to the server after client-side verification
        phone_num1 = '+9720000000000'
        resp = self.app.post('/user/firebase/update-id-token',
                    data=json.dumps({
                        'token': 'fake-token',
                        'phone_number': phone_num1}),
                    headers={USER_ID_HEADER: str(userid1)},
                    content_type='application/json')
        self.assertEqual(resp.status_code, 200)


        # add transactions to the user
        create_tx("AAA", userid1, "someaddress", False, 100, {'task_id': '0', 'memo': 'kit-12312312312'})

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

        # one allocated good at this point
        resp = self.app.get('/good/inventory')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(json.loads(resp.data)['inventory'], {offer['id']: {'total': 1, 'unallocated': 0}})

        # try to release unclaimed good - should not release anything as order is still active
        resp = self.app.get('/good/release_unclaimed')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(json.loads(resp.data)['released'], 0)

        # sleep 16 seoncds
        print('sleeping 16 seconds...')
        sleep(16)
        print('done')

        # try to release unclaimed good - should release one
        resp = self.app.get('/good/release_unclaimed')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(json.loads(resp.data)['released'], 1)

        # zero allocated goods at this point
        resp = self.app.get('/good/inventory')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(json.loads(resp.data)['inventory'], {offer['id']: {'total': 1, 'unallocated': 1}})

if __name__ == '__main__':
    unittest.main()
