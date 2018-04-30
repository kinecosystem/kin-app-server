import simplejson as json
import unittest
import uuid

import testing.postgresql

import kinappserver
from kinappserver import db, models


USER_ID_HEADER = "X-USERID"

class Tester(unittest.TestCase):

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

    def test_register_with_verification(self):
        """test registration scenarios"""
        userid = str(uuid.uuid4())
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

        userid2 = str(uuid.uuid4())
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

        resp = self.app.post('/user/app-launch',
                            data=json.dumps({
                            'app_ver': '1.0'}),
                            headers={USER_ID_HEADER: str(userid)},
                            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        data = json.loads(resp.data)
        print('data: %s' % data)

        # user updates his phone number to the server after client-side verification
        phone_num = '+9720528802120'
        resp = self.app.post('/user/phone',
                    data=json.dumps({
                        'number': phone_num}),
                    headers={USER_ID_HEADER: str(userid)},
                    content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # user re-updates his number to the same number, should work.
        phone_num = '+9720528802120'
        resp = self.app.post('/user/phone',
                    data=json.dumps({
                        'number': phone_num}),
                    headers={USER_ID_HEADER: str(userid)},
                    content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        print('all users: %s' %models.list_all_users())

        # different user updates his number to the same number, should work - and deactivate the previous user
        print('user 2 updates to the same number as user 1...')
        phone_num = '+9720528802120'
        resp = self.app.post('/user/phone',
                    data=json.dumps({
                        'number': phone_num}),
                    headers={USER_ID_HEADER: str(userid2)},
                    content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        print('all users: %s' %models.list_all_users())

        # user2 re-updates his phone number to a different number. should fail
        phone_num = '+9720528802121'
        resp = self.app.post('/user/phone',
                    data=json.dumps({
                        'number': phone_num}),
                    headers={USER_ID_HEADER: str(userid2)},
                    content_type='application/json')
        self.assertNotEqual(resp.status_code, 200)

        # add an offer and have user 1 attempt to book it - it should fail - as he is deactivated
        offerid = '0'
        offer = {'id': offerid,
                 'type': 'gift-card',
                 'type_image_url': "https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png",
                 'domain': 'music',
                 'title': 'offer_title',
                 'desc': 'offer_desc',
                 'image_url': 'image_url',
                 'price': 2,
                 'address': 'GCORIYYEQP3ANHFT6XHMBY7VB3RH53WB5KZZHGCEXYRWCEJQZUXPGWQM',
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

        # create an order with userid1 - should fail as userid1 is deactivated
        resp = self.app.post('/offer/book',
                             data=json.dumps({
                                 'id': offerid}),
                             headers={USER_ID_HEADER: str(userid)},
                             content_type='application/json')
        self.assertNotEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        print('book results: %s' % data)
        self.assertEqual(data['message'], 'user-deactivated')

        # create an order with userid2 - should succeed
        resp = self.app.post('/offer/book',
                             data=json.dumps({
                                 'id': offerid}),
                             headers={USER_ID_HEADER: str(userid2)},
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        print('book results: %s' % data)


if __name__ == '__main__':
    unittest.main()
