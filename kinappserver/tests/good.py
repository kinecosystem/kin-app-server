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


        # enable offer 0 
        resp = self.app.post('/offer/set_active',
                            data=json.dumps({
                            'offer_id': '0',
                            'is_active': True}),
                            headers={},
                            content_type='application/json')
        self.assertEqual(resp.status_code, 200)


        # add a few instances of goods
        resp = self.app.post('/good/add',
                    data=json.dumps({
                    'offer_id': '0',
                    'good_type': 'code',
                    'value': 'abcd'}),
                    headers={},
                    content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # add a few instances of goods: should fail as no such offer exists
        resp = self.app.post('/good/add',
                    data=json.dumps({
                    'offer_id': '1',
                    'good_type': 'code',
                    'value': 'abcd'}),
                    headers={},
                    content_type='application/json')
        self.assertNotEqual(resp.status_code, 200)

if __name__ == '__main__':
    unittest.main()
