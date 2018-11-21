import unittest
from uuid import uuid4
import json

import testing.postgresql
from kinappserver.models.transaction import create_tx

import kinappserver
from kinappserver import db

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
        kinappserver.app.config['SQLALCHEMY_DATABASE_URI'] = self.postgresql.url()
        kinappserver.app.testing = True
        self.app = kinappserver.app.test_client()
        db.drop_all()
        db.create_all()

    def tearDown(self):
        self.postgresql.stop()

    def test_create_good(self):
        """test good creation and allocation/release"""
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

        task = {'title': 'do you know horses?',
                'desc': 'horses_4_dummies',
                'type': 'questionnaire',
                'position': 0,
                'cat_id': '0',
                'task_id': '0',
                'price': 100,
                'min_to_complete': 2,
                'skip_image_test': False,  # test link-checking code
                'tags': ['music', 'crypto', 'movies', 'kardashians', 'horses'],
                'provider':
                    {'name': 'om-nom-nom-food',
                     'image_url': 'https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png'},
                'post_task_actions': [{'type': 'external-url',
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
        resp = self.app.post('/task/add',  # task_id should be 0
                             data=json.dumps({
                                 'task': task}),
                             headers={},
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        offer = {'id': '0',
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
                     {'name': 'om-nom-nom-food', 'image_url': 'http://inter.webs/horsie.jpg'},
                 }

        resp = self.app.get('/good/inventory')
        self.assertEqual(resp.status_code, 200)
        print(json.loads(resp.data))
        self.assertEqual(json.loads(resp.data)['inventory'], {})

        resp = self.app.post('/offer/add',
                             data=json.dumps({
                                 'offer': offer}),
                             headers={},
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # enable offer 0 
        resp = self.app.post('/offer/set_active',
                             data=json.dumps({
                                 'id': offer['id'],
                                 'is_active': True}),
                             headers={},
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # no goods at this point
        resp = self.app.get('/good/inventory')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(json.loads(resp.data)['inventory'], {offer['id']: {'total': 0, 'unallocated': 0}})

        # add an instance of goods
        resp = self.app.post('/good/add',
                             data=json.dumps({
                                 'offer_id': offer['id'],
                                 'good_type': 'code',
                                 'value': 'abcd'}),
                             headers={},
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # add the same instance of goods again - should fail
        resp = self.app.post('/good/add',
                             data=json.dumps({
                                 'offer_id': offer['id'],
                                 'good_type': 'code',
                                 'value': 'abcd'}),
                             headers={},
                             content_type='application/json')
        self.assertNotEqual(resp.status_code, 200)

        # one good instance at this point
        resp = self.app.get('/good/inventory')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(json.loads(resp.data)['inventory'], {offer['id']: {'total': 1, 'unallocated': 1}})

        # and another instance
        resp = self.app.post('/good/add',
                             data=json.dumps({
                                 'offer_id': offer['id'],
                                 'good_type': 'code',
                                 'value': 'edfg'}),
                             headers={},
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        resp = self.app.get('/good/inventory')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(json.loads(resp.data)['inventory'], {offer['id']: {'total': 2, 'unallocated': 2}})

        # attempt to add another instance of good: should fail as no such offer exists
        print('trying to create a good for an unknown offer_id...')
        resp = self.app.post('/good/add',
                             data=json.dumps({
                                 'offer_id': '1',
                                 'good_type': 'code',
                                 'value': 'abcde'}),
                             headers={},
                             content_type='application/json')
        self.assertNotEqual(resp.status_code, 200)
        print('...done')

        # create a user
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

        db.engine.execute(
            """update public.push_auth_token set auth_token='%s' where user_id='%s';""" % (str(userid), str(userid)))

        resp = self.app.post('/user/auth/ack',
                             data=json.dumps({
                                 'token': str(userid)}),
                             headers={USER_ID_HEADER: str(userid)},
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        phone_num1 = '+9720000000000'
        resp = self.app.post('/user/firebase/update-id-token',
                             data=json.dumps({
                                 'token': 'fake-token',
                                 'phone_number': phone_num1}),
                             headers={USER_ID_HEADER: str(userid)},
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        # add transactions to the user
        create_tx("AAA", userid, "someaddress", False, 1000, {'task_id': '0', 'memo': 'kit-12312312312'})

        # create an order and allocate a good
        resp = self.app.post('/offer/book',
                             data=json.dumps({
                                 'id': offer['id']}),
                             headers={USER_ID_HEADER: str(userid)},
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertEqual(data['status'], 'ok')
        self.assertNotEqual(data['order_id'], None)
        order_id1 = data['order_id']
        print('order_id: %s created for offer_id: %s' % (order_id1, offer['id']))

        resp = self.app.get('/good/inventory')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(json.loads(resp.data)['inventory'], {offer['id']: {'total': 2, 'unallocated': 1}})


if __name__ == '__main__':
    unittest.main()
