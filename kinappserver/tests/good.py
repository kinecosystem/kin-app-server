import unittest
from uuid import uuid4
import json

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

    def test_create_good(self):
        """test good creation and allocation/release"""
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
                            'offer_id': offer['offer_id'],
                            'is_active': True}),
                            headers={},
                            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # no goods at this point
        resp = self.app.get('/good/inventory')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(json.loads(resp.data)['inventory'], {offer['offer_id']: {'total': 0, 'unallocated': 0}})


        # add an instance of goods
        resp = self.app.post('/good/add',
                    data=json.dumps({
                    'offer_id': offer['offer_id'],
                    'good_type': 'code',
                    'value': 'abcd'}),
                    headers={},
                    content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # one good instance at this point
        resp = self.app.get('/good/inventory')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(json.loads(resp.data)['inventory'], {offer['offer_id']: {'total': 1, 'unallocated': 1}})


        # and another instance
        resp = self.app.post('/good/add',
                    data=json.dumps({
                    'offer_id': offer['offer_id'],
                    'good_type': 'code',
                    'value': 'edfg'}),
                    headers={},
                    content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        resp = self.app.get('/good/inventory')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(json.loads(resp.data)['inventory'], {offer['offer_id']: {'total': 2, 'unallocated': 2}})

        # attempt to add another instance of good: should fail as no such offer exists
        print('trying to create a good for an unknown offer_id...')
        resp = self.app.post('/good/add',
                    data=json.dumps({
                    'offer_id': '1',
                    'good_type': 'code',
                    'value': 'abcd'}),
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
                            'time_zone': '+05:00',
                            'token': 'fake_token',
                            'app_ver': '1.0'}),
            headers={},
            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # create an order and allocate a good
        resp = self.app.post('/offer/book',
                    data=json.dumps({
                    'id': offer['offer_id']}),
                    headers={USER_ID_HEADER: str(userid)},
                    content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertEqual(data['status'], 'ok')
        self.assertNotEqual(data['order_id'], None)
        order_id1 = data['order_id']
        print('order_id: %s created for offer_id: %s' % (order_id1, offer['offer_id']))

        resp = self.app.get('/good/inventory')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(json.loads(resp.data)['inventory'], {offer['offer_id']: {'total': 2, 'unallocated': 1}})


if __name__ == '__main__':
    unittest.main()
