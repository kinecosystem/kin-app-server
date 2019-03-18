import unittest
import uuid
from time import sleep
import simplejson as json
import testing.postgresql

import kinappserver
from kinappserver import db, models

import logging as log

log.getLogger().setLevel(log.INFO)

USER_ID_HEADER = "X-USERID"

category_extra_data_dict = {'default': {'title': 'a title', 'subtitle': 'a subtitle'},
                            'no_tasks': {'title': 'title2', 'subtitle': 'subtitle2'}}

cat = {'id': '1',
       'title': 'cat-title',
       'supported_os': 'android',
       'ui_data': {'color': "#123",
                   'image_url': 'https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png',
                   'header_image_url': 'https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png'}}

cat2 = {'id': '2',
        'title': 'cat-title2',
        'supported_os': 'all',
        'ui_data': {'color': "#234",
                    'image_url': 'https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png',
                    'header_image_url': 'https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png'}}

cat3 = {'id': '3',
       'title': 'cat-title3',
       'supported_os': 'android',
       'ui_data': {'color': "#123",
                   'image_url': 'https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png',
                   'header_image_url': 'https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png'}}

cat4 = {'id': '4',
        'title': 'cat-title4',
        'supported_os': 'all',
        'ui_data': {'color': "#234",
                    'image_url': 'https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png',
                    'header_image_url': 'https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png'}}

task = {
    "cat_id": '1',
    "position": 0,
    'title': 'do you know horses?',
    'desc': 'horses_4_dummies',
            'type': 'questionnaire',
            'price': 1,
            'delay_days': 2,
            'skip_image_test': True,
            'min_to_complete': 2,
            'tags': ['music', 'crypto', 'movies', 'kardashians', 'horses'],
            'provider':
                {'name': 'om-nom-nom-food',
                    'image_url': 'http://inter.webs/horsie.jpg'},
            'items': [
                {
                    'id': '435',
                    'text': 'what animal is this?',
                    'type': 'textimage',
                    'results': [
                        {'id': '235',
                         'text': 'a horse!',
                         'image_url': 'cdn.helllo.com/horse.jpg'},
                        {'id': '2465436',
                         'text': 'a cat!',
                         'image_url': 'cdn.helllo.com/kitty.jpg'},
                    ],
                }]
}


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
        db.engine.execute("""insert into system_config values (1,'1','1','1','1')""")
        db.engine.execute("update system_config set categories_extra_data=%s;",(json.dumps(category_extra_data_dict)))

    def tearDown(self):
        self.postgresql.stop()

    def test_caching(self):
        """ test categories & tasks caching """
        
        # add categories
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

        resp = self.app.post('/category/add',
                             data=json.dumps({
                                 'category': cat3}),
                             headers={},
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        resp = self.app.post('/category/add',
                             data=json.dumps({
                                 'category': cat4}),
                             headers={},
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # manipulate and add another
        task2 = task.copy()
        task2['position'] = 1
        task2['cat_id'] = 1
        

        task3 = task.copy()
        task3['position'] = 2
        task3['cat_id'] = 2

        task4 = task.copy()
        task4['position'] = 3
        task4['cat_id'] = 2

        task5 = task.copy()
        task5['position'] = 3
        task5['cat_id'] = 3

        task6 = task.copy()
        task6['position'] = 5
        task6['cat_id'] = 3

        task7 = task.copy()
        task7['position'] = 6
        task7['cat_id'] = 4

        task8 = task.copy()
        task8['position'] = 7
        task8['cat_id'] = 4

        resp = self.app.post('/task/add',
                             data=json.dumps({
                                 'task': task}),
                             headers={},
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        resp = self.app.post('/task/add',
                             data=json.dumps({
                                 'task': task2}),
                             headers={},
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        resp = self.app.post('/task/add',
                             data=json.dumps({
                                 'task': task3}),
                             headers={},
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        resp = self.app.post('/task/add',
                             data=json.dumps({
                                 'task': task4}),
                             headers={},
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        resp = self.app.post('/task/add',
                             data=json.dumps({
                                 'task': task5}),
                             headers={},
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        resp = self.app.post('/task/add',
                             data=json.dumps({
                                 'task': task6}),
                             headers={},
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        resp = self.app.post('/task/add',
                             data=json.dumps({
                                 'task': task7}),
                             headers={},
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        resp = self.app.post('/task/add',
                             data=json.dumps({
                                 'task': task8}),
                             headers={},
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)

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

        db.engine.execute(
            """update public.push_auth_token set auth_token='%s' where user_id='%s';""" % (str(userid), str(userid)))

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
        self.assertEqual(data['header_message'],
                         category_extra_data_dict['default'])

        self.assertEqual(data['categories'][0]['available_tasks_count'], 1)
        self.assertEqual(data['categories'][1]['available_tasks_count'], 1)
        self.assertEqual(data['categories'][2]['available_tasks_count'], 1)
        self.assertEqual(data['categories'][3]['available_tasks_count'], 1)
        self.assertEqual(data['categories'][0]['id'], '1')
        self.assertEqual(data['categories'][1]['id'], '2')
        self.assertEqual(data['categories'][2]['id'], '3')
        self.assertEqual(data['categories'][3]['id'], '4')

        # validate cache is working
        db.engine.execute(
            """update category set title = 'alt title' where category_id = '1'""")

        resp = self.app.get('/user/categories', headers=headers)
        print('user categories: %s ' % resp.data)
        data = json.loads(resp.data)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(data['categories'][0]['available_tasks_count'], 1)
        self.assertEqual(data['categories'][1]['available_tasks_count'], 1)
        self.assertEqual(data['categories'][2]['available_tasks_count'], 1)
        self.assertEqual(data['categories'][3]['available_tasks_count'], 1)
        self.assertEqual(data['categories'][0]['id'], '1')
        self.assertEqual(data['categories'][1]['id'], '2')
        self.assertEqual(data['categories'][2]['id'], '3')
        self.assertEqual(data['categories'][3]['id'], '4')
        

        # clear tasks cache
        from kinappserver.utils import delete_pattern, delete_from_cache
        from kinappserver import config

        delete_from_cache(config.USER_CATEGORIES_CACHE_REDIS_KEY % userid)
        delete_pattern(config.USER_TASK_IN_CATEGORY_CACHE_REDIS_KEY_PREFIX % userid)

        resp = self.app.get('/user/categories', headers=headers)
        print('user categories: %s ' % resp.data)
        data = json.loads(resp.data)
        self.assertEqual(resp.status_code, 200)
        
        self.assertEqual(data['categories'][1]['title'], 'cat-title2')

        resp = self.app.get('/user/category/1/tasks', headers=headers)
        print('user categories: %s ' % resp.data)
        resp = self.app.get('/user/category/2/tasks', headers=headers)
        print('user categories: %s ' % resp.data)
        resp = self.app.get('/user/category/3/tasks', headers=headers)
        print('user categories: %s ' % resp.data)
        resp = self.app.get('/user/category/4/tasks', headers=headers)
        print('user categories: %s ' % resp.data)

        # send task results - should be accepted as there's no delay)
        resp = self.app.post('/user/task/results',
                             data=json.dumps({
                                 'id': '0',
                                 'address': 'GCYUCLHLMARYYT5EXJIK2KZJCMRGIKKUCCJKJOAPUBALTBWVXAT4F4OZ',
                                 'results': {'2234': 'werw', '5345': '345345'},
                                 'captcha_token': '23234',
                                 'send_push': False
                             }),
                             headers={USER_ID_HEADER: str(userid)},
                             content_type='application/json')

        print('data: %s' % data)
        self.assertEqual(resp.status_code, 200)

        sleep(5)

        # get the user's current tasks
        headers = {USER_ID_HEADER: userid}
        resp = self.app.get('/user/tasks', headers=headers)
        data = json.loads(resp.data)
        print('data: %s' % data)
        self.assertEqual(resp.status_code, 200)
        print('next task id: %s' % data['tasks']['1'][0]['id'])
        print('next task start date: %s' % data['tasks']['1'][0]['start_date'])

        # the next start date should be at least 24 hours into the future:
        import arrow

        future = arrow.get(data['tasks']['1'][0]['start_date'])
        now = arrow.utcnow()
        self.assertEqual((future-now).total_seconds() / 3600 > 24, True)

        resp = self.app.get('/user/category/1/tasks', headers=headers)
        print('user categories: %s ' % resp.data)
        data = json.loads(resp.data)
        self.assertEqual(resp.status_code, 200)
        print('next task id: %s' % data['tasks'][0]['id'])
        print('next task start date: %s' % data['tasks'][0]['start_date'])
        
        future = arrow.get(data['tasks'][0]['start_date'])
        now = arrow.utcnow()
        self.assertEqual((future-now).total_seconds() / 3600 > 24, True)
        
        resp = self.app.get('/user/category/2/tasks', headers=headers)
        print('user categories: %s ' % resp.data)
        resp = self.app.get('/user/category/3/tasks', headers=headers)
        print('user categories: %s ' % resp.data)
        resp = self.app.get('/user/category/4/tasks', headers=headers)
        print('user categories: %s ' % resp.data)

        resp = self.app.get('/user/categories', headers=headers)
        print('user categories: %s ' % resp.data)
        data = json.loads(resp.data)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(data['categories'][0]['available_tasks_count'], 0)
        self.assertEqual(data['categories'][1]['available_tasks_count'], 1)
        self.assertEqual(data['categories'][2]['available_tasks_count'], 1)
        self.assertEqual(data['categories'][3]['available_tasks_count'], 1)
        self.assertEqual(data['categories'][0]['id'], '1')
        self.assertEqual(data['categories'][1]['id'], '2')
        self.assertEqual(data['categories'][2]['id'], '3')
        self.assertEqual(data['categories'][3]['id'], '4')


    def test_category_storing(self):
        """test storing and getting tasks with categories"""

        

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

        db.engine.execute(
            """update public.push_auth_token set auth_token='%s' where user_id='%s';""" % (str(userid), str(userid)))

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

        # verify keys in redis
        cached_results = kinappserver.utils.read_json_from_cache(
            kinappserver.config.USER_CATEGORIES_CACHE_REDIS_KEY % userid)
        self.assertListEqual(data['categories'], [cat for cat in cached_results.values()])

        
        # categories were manipulated - clear redis
        kinappserver.app.redis.flushdb()

        # get the user's current categories
        headers = {USER_ID_HEADER: userid}
        resp = self.app.get('/user/categories', headers=headers)
        print('user categories: %s ' % resp.data)
        data = json.loads(resp.data)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(data['header_message'], category_extra_data_dict['no_tasks'])
        
        print('user categories: %s ' % resp.data)
        # add a task and ensure the message is correct:

        # categories were manipulated - clear redis
        kinappserver.app.redis.flushdb()

    
        # task_id isn't given, should be '0'
        resp = self.app.post('/task/add',  # task_id should be 0
                             data=json.dumps({
                                 'task': task}),
                             headers={},
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # categories were manipulated - clear redis
        kinappserver.app.redis.flushdb()

        # get the user's current categories
        headers = {USER_ID_HEADER: userid}
        resp = self.app.get('/user/categories', headers=headers)
        print('user categories: %s ' % resp.data)
        data = json.loads(resp.data)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(data['header_message'], category_extra_data_dict['default'])

        cat3 = {'id': '3', 'title': 'cat-title3', 'supported_os': 'asbsd', 'ui_data': {'color': "#234",
                                                                                      'image_url': 'https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png',
                                                                                      'header_image_url': 'https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png'}}

        # test invalid os - should not work
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