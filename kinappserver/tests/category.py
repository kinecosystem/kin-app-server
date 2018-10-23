import unittest
import uuid

import simplejson as json
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

    def test_category_storing(self):
        """test storting and getting tasks with categories"""

        cat = {'id': '1',
          'title': 'cat-title',
          'ui_data': {'color': "#123",
                      'image_url': 'https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png',
                      'header_image_url': 'https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png'}}

        cat2 = {'id': '2',
          'title': 'cat-title2',
          'ui_data': {'color': "#234",
                      'image_url': 'https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png',
                      'header_image_url': 'https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png'}}

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

        category_extra_data_dict = {'title': 'a title', 'subtitle': 'a subtitle'}
        db.engine.execute("""insert into system_config values (1,'1','1','1','1')""");
        db.engine.execute("update system_config set categories_extra_data=%s;", (json.dumps(category_extra_data_dict),))

        # get the user's current categories
        headers = {USER_ID_HEADER: userid}
        resp = self.app.get('/user/categories', headers=headers)
        print('user categories: %s ' % resp.data)
        data = json.loads(resp.data)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(data['header_message'], category_extra_data_dict)







if __name__ == '__main__':
    unittest.main()
