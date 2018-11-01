import unittest
import uuid

import simplejson as json
import testing.postgresql


import kinappserver
from kinappserver import db, models

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
        kinappserver.app.config['SQLALCHEMY_DATABASE_URI'] = self.postgresql.url()
        kinappserver.app.testing = True
        self.app = kinappserver.app.test_client()
        db.drop_all()
        db.create_all()


    def tearDown(self):
        self.postgresql.stop()

    def test_category_storing(self):
        """test storing and getting tasks with categories"""

        cat = {'id': '1',
          'title': 'cat-title',
          'supported_os': 'all',
          'ui_data': {'color': "#123",
                      'image_url': 'https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png',
                      'header_image_url': 'https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png'},
          'supported_os': 'android'}

        cat2 = {'id': '2',
          'title': 'cat-title2',
          'supported_os': 'all',
          'ui_data': {'color': "#234",
                      'image_url': 'https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png',
                      'header_image_url': 'https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png'},
          'supported_os': 'all'}

        resp = self.app.post('/category/add',
                            data=json.dumps({
                            'category': cat}),
                            headers={},
                            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        resp = self.app.post('/category/add',
                            data=json.dumps({
                            'category': cat2}),
                            headers={},
                            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        print('all cat ids: %s' % models.get_all_cat_ids())

        print('all cats: %s ' % models.list_all_categories())

        print('all android cats: %s ' % models.list_categories('android'))

        print('all iOS cats: %s ' % models.list_categories('iOS'))

        print('adding the same cat without an overwrite flag: should fail')
        resp = self.app.post('/category/add',
                            data=json.dumps({
                            'category': cat}),
                            headers={},
                            content_type='application/json')
        self.assertEqual(resp.status_code, 400)

        print('adding the same cat with an overwrite flag: should succeed')
        cat['overwrite'] = True
        cat['title'] = 'overwritten_cat'
        resp = self.app.post('/category/add',
                             data=json.dumps({
                                 'category': cat}),
                             headers={},
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        print('all cats: %s ' % models.list_all_categories())

        print('adding the same cat without an overwrite flag: should fail')
        cat['overwrite'] = False
        resp = self.app.post('/category/add',
                             data=json.dumps({
                                 'category': cat}),
                             headers={},
                             content_type='application/json')
        self.assertEqual(resp.status_code, 400)


        # register a user
        userid = uuid.uuid4()
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

        db.engine.execute("""update public.push_auth_token set auth_token='%s' where user_id='%s';""" % (str(userid), str(userid)))

        resp = self.app.post('/user/auth/ack',
                            data=json.dumps({
                            'token': str(userid)}),
                            headers={USER_ID_HEADER: str(userid)},
                            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # get the user's current categories
        headers = {USER_ID_HEADER: userid}
        resp = self.app.get('/user/categories', headers=headers)
        print('user categories: %s ' % resp.data)
        data = json.loads(resp.data)
        self.assertEqual(resp.status_code, 200)

        category_extra_data_dict = {'default': {'title': 'a title', 'subtitle': 'a subtitle'}, 'no_tasks': {'title': 'title2', 'subtitle': 'subtitle2'}}
        db.engine.execute("""insert into system_config values (1,'1','1','1','1')""");
        db.engine.execute("update system_config set categories_extra_data=%s;", (json.dumps(category_extra_data_dict),))

        # get the user's current categories
        headers = {USER_ID_HEADER: userid}
        resp = self.app.get('/user/categories', headers=headers)
        print('user categories: %s ' % resp.data)
        data = json.loads(resp.data)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(data['header_message'], category_extra_data_dict['no_tasks'])

        # add a task and ensure the message is correct:


        task = {  'title': 'do you know horses?',
                  'desc': 'horses_4_dummies',
                  'type': 'questionnaire',
                  'position': 0,
                  'cat_id': '1',
                  'price': 2000,
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
        resp = self.app.post('/task/add',  # task_id should be 0
                            data=json.dumps({
                            'task': task}),
                            headers={},
                            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # get the user's current categories
        headers = {USER_ID_HEADER: userid}
        resp = self.app.get('/user/categories', headers=headers)
        print('user categories: %s ' % resp.data)
        data = json.loads(resp.data)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(data['header_message'], category_extra_data_dict['default'])



        cat3 = {'id': '3',
          'title': 'cat-title3',
          'supported_os': 'iOS',
          'ui_data': {'color': "#234",
                      'image_url': 'https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png',
                      'header_image_url': 'https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png'}
                      }

        # test invalid os - should not work
        cat3['supported_os'] = 'blah'
        resp = self.app.post('/category/add',
                            data=json.dumps({
                            'category': cat3}),
                            headers={},
                            content_type='application/json')
        self.assertNotEqual(resp.status_code, 200)

        # test no os - should not work
        cat3.pop('supported_os')
        resp = self.app.post('/category/add',
                            data=json.dumps({
                            'category': cat3}),
                            headers={},
                            content_type='application/json')
        self.assertNotEqual(resp.status_code, 200)

        # test ios - should work
        cat3['supported_os'] = 'iOS'
        resp = self.app.post('/category/add',
                            data=json.dumps({
                            'category': cat3}),
                            headers={},
                            content_type='application/json')
        self.assertEqual(resp.status_code, 200)



if __name__ == '__main__':
    unittest.main()
