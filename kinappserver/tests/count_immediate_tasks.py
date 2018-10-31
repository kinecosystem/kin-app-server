from time import sleep
import unittest
import uuid

import simplejson as json
import testing.postgresql
import arrow

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
        self.app_config = kinappserver.config
        db.drop_all()
        db.create_all()

    def tearDown(self):
        self.postgresql.stop()

    def test_count_immediate_tasks(self):
        """test storting task results"""
        now = arrow.utcnow()

        US_IP_ADDRESS = '50.196.205.141'
        ISRAEL_IP_ADDRESS = '199.203.79.137'

        # add a task
        task = {
          'id': '0',
            "cat_id": '0',
            "position": 0,
          'title': 'do you know horses?',
          'desc': 'horses_4_dummies',
          'type': 'questionnaire',
          'price': 1,
          'skip_image_test': True,
          'min_to_complete': 2,
          'min_client_version_ios': '1.0',
          'min_client_version_android': '1.0',
          'tags': ['music', 'crypto', 'movies', 'kardashians', 'horses'],
          'provider':
            {'name': 'om-nom-nom-food', 'image_url': 'http://inter.webs/horsie.jpg'},
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

        def add_task_to_test(task, cat_id, task_id, position, delay_days=0, excluded_country_codes=None, task_start_date=None, task_expiration_date=None, task_type=None):
            import copy
            task = copy.deepcopy(task)

            task['position'] = position
            task['id'] = str(task_id)
            task['cat_id'] = str(cat_id)
            task['delay_days'] = delay_days
            if task_type:
                task['type'] = task_type
            else:
                task['type'] = 'textimage'
            if position == -1:
                task['task_start_date'] = task_start_date
                task['task_expiration_date'] = task_expiration_date
            if excluded_country_codes:
                task['excluded_country_codes'] = excluded_country_codes
            resp = self.app.post('/task/add',
                                 data=json.dumps({
                                     'task': task}),
                                 headers={},
                                 content_type='application/json')
            self.assertEqual(resp.status_code, 200)

        def nuke_user_data_and_taks():
            db.engine.execute("update user_app_data set completed_tasks_dict=%s;", (json.dumps({'0': [], '1': []}),))
            db.engine.execute("""delete from task2;""")
            db.engine.execute("""delete from truex_blacklisted_user;""")
            self.app_config.TRUEX_BLACKLISTED_TASKIDS = "[]"
            db.engine.execute("""update public.user_app_data set ip_address=null;""")

        for cat_id in range(2):
            print('adding category %s...' % cat_id)
            cat = {'id': str(cat_id),
              'title': 'cat-title',
                   "skip_image_test": True,
              'ui_data': {'color': "#123",
                          'image_url': 'https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png',
                          'header_image_url': 'https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png'}}

            resp = self.app.post('/category/add',
                                data=json.dumps({
                                'category': cat}),
                                headers={},
                                content_type='application/json')
            self.assertEqual(resp.status_code, 200)

        userid = uuid.uuid4()
        userid_ios = uuid.uuid4()
        # register an android with a token
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

        # register an ios with a token
        resp = self.app.post('/user/register',
                             data=json.dumps({
                                 'user_id': str(userid_ios),
                                 'os': 'iOS',
                                 'device_model': 'iphone9',
                                 'device_id': '234234',
                                 'time_zone': '05:00',
                                 'token': 'fake_token',
                                 'app_ver': '1.0'}),
                             headers={},
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        db.engine.execute("""update public.push_auth_token set auth_token='%s' where user_id='%s';""" % (str(userid), str(userid)))
        db.engine.execute("""update public.push_auth_token set auth_token='%s' where user_id='%s';""" % (str(userid_ios), str(userid_ios)))

        resp = self.app.post('/user/auth/ack',
                             data=json.dumps({
                                 'token': str(userid)}),
                             headers={USER_ID_HEADER: str(userid)},
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        resp = self.app.post('/user/auth/ack',
                             data=json.dumps({
                                 'token': str(userid_ios)}),
                             headers={USER_ID_HEADER: str(userid_ios)},
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        #TODO these tests will fail as long as truex is allowed in config.DEBUG (which is a temp thing)
        # test an ios client with Truex task
        # nuke_user_data_and_taks()
        # add_task_to_test(task, cat_id=0, task_id=0, position=0, delay_days=0, task_type='truex')
        # add_task_to_test(task, cat_id=1, task_id=1, position=0, delay_days=0, task_type='truex')
        # self.assertEqual(models.count_immediate_tasks(str(userid_ios)), {'0': 0, '1': 0})


        #TODO these tests will fail as long as truex is allowed in config.DEBUG (which is a temp thing)
        # test an ios client with non-Truex-related task
        # nuke_user_data_and_taks()
        #  add_task_to_test(task, cat_id=0, task_id=0, position=0, delay_days=0)
        #  add_task_to_test(task, cat_id=1, task_id=1, position=0, delay_days=0)
        #  self.assertEqual(models.count_immediate_tasks(str(userid_ios)), {'0': 0, '1': 0})


        #TODO these tests will fail as long as truex is allowed in config.DEBUG (which is a temp thing)
        # test an ios client with Truex-related task - should skip these tasks
        # nuke_user_data_and_taks()
        # self.app_config.TRUEX_BLACKLISTED_TASKIDS = "['1','0']"
        # add_task_to_test(task, cat_id=0, task_id=0, position=0, delay_days=0)
        # add_task_to_test(task, cat_id=1, task_id=1, position=0, delay_days=0)
        # self.assertEqual(models.count_immediate_tasks(str(userid_ios)), {'0': 0, '1': 0})

        # test a US android client with a Truex task
        nuke_user_data_and_taks()
        db.engine.execute("""update public.user_app_data set ip_address='%s' where user_id='%s';""" % (US_IP_ADDRESS, str(userid)))
        add_task_to_test(task, cat_id=0, task_id=0, position=0, delay_days=0, task_type='truex')
        add_task_to_test(task, cat_id=1, task_id=1, position=0, delay_days=0, task_type='truex')
        self.assertEqual(models.count_immediate_tasks(str(userid)), {'0': 1, '1': 1})


        #TODO these tests will fail as long as truex is allowed in config.DEBUG (which is a temp thing)
        # test a US android client with a truex-related task
        # nuke_user_data_and_taks()
        # db.engine.execute("""update public.user_app_data set ip_address='%s' where user_id='%s';""" % (US_IP_ADDRESS, str(userid)))
        # self.app_config.TRUEX_BLACKLISTED_TASKIDS = "['1','0']"
        # add_task_to_test(task, cat_id=0, task_id=0, position=0, delay_days=0)
        # add_task_to_test(task, cat_id=1, task_id=1, position=0, delay_days=0)
        # self.assertEqual(models.count_immediate_tasks(str(userid)), {'0': 0, '1': 0})


        #TODO these tests will fail as long as truex is allowed in config.DEBUG (which is a temp thing)
        # test a non-US android client with a truex task
        # nuke_user_data_and_taks()
        # db.engine.execute("""update public.user_app_data set ip_address='%s' where user_id='%s';""" % (ISRAEL_IP_ADDRESS, str(userid)))
        # add_task_to_test(task, cat_id=0, task_id=0, position=0, delay_days=0, task_type='truex')
        # add_task_to_test(task, cat_id=1, task_id=1, position=0, delay_days=0, task_type='truex')
        # self.assertEqual(models.count_immediate_tasks(str(userid)), {'0': 0, '1': 0})

        # TODO these tests will fail as long as truex is allowed in config.DEBUG (which is a temp thing)
        # test a non-US android client that's blacklisted with a truex task
        # nuke_user_data_and_taks()
        # db.engine.execute("""update public.user_app_data set ip_address='%s' where user_id='%s';""" % (ISRAEL_IP_ADDRESS, str(userid)))
        # db.engine.execute("""insert into truex_blacklisted_user values('%s')""" % str(userid))
        # add_task_to_test(task, cat_id=0, task_id=0, position=0, delay_days=0, task_type='truex')
        # add_task_to_test(task, cat_id=1, task_id=1, position=0, delay_days=0, task_type='truex')
        # self.assertEqual(models.count_immediate_tasks(str(userid)), {'0': 0, '1': 0})

        # TODO these tests will fail as long as truex is allowed in config.DEBUG (which is a temp thing)
        # test a US android client that's blacklisted with a truex-related task
        # nuke_user_data_and_taks()
        # db.engine.execute("""update public.user_app_data set ip_address='%s' where user_id='%s';""" % (US_IP_ADDRESS, str(userid)))
        # db.engine.execute("""insert into truex_blacklisted_user values('%s')""" % str(userid))
        # self.app_config.TRUEX_BLACKLISTED_TASKIDS = "['1','0']"
        # add_task_to_test(task, cat_id=0, task_id=0, position=0, delay_days=0)
        # add_task_to_test(task, cat_id=1, task_id=1, position=0, delay_days=0)
        # self.assertEqual(models.count_immediate_tasks(str(userid)), {'0': 0, '1': 0})

        # TODO these tests will fail as long as truex is allowed in config.DEBUG (which is a temp thing)
        # test a US android client that's blacklisted with a truex task
        # nuke_user_data_and_taks()
        # db.engine.execute("""update public.user_app_data set ip_address='%s' where user_id='%s';""" % (US_IP_ADDRESS, str(userid)))
        # db.engine.execute("""insert into truex_blacklisted_user values('%s')""" % str(userid))
        # add_task_to_test(task, cat_id=0, task_id=0, position=0, delay_days=0, task_type='truex')
        # add_task_to_test(task, cat_id=1, task_id=1, position=0, delay_days=0, task_type='truex')
        # self.assertEqual(models.count_immediate_tasks(str(userid)), {'0': 0, '1': 0})

        # TODO these tests will fail as long as truex is allowed in config.DEBUG (which is a temp thing)
        # test a non-US android client that's blacklisted with a truex-related task
        # nuke_user_data_and_taks()
        # db.engine.execute("""update public.user_app_data set ip_address='%s' where user_id='%s';""" % (ISRAEL_IP_ADDRESS, str(userid)))
        # db.engine.execute("""insert into truex_blacklisted_user values('%s')""" % str(userid))
        # self.app_config.TRUEX_BLACKLISTED_TASKIDS = "['1','0']"
        # add_task_to_test(task, cat_id=0, task_id=0, position=0, delay_days=0)
        # add_task_to_test(task, cat_id=1, task_id=1, position=0, delay_days=0)
        # self.assertEqual(models.count_immediate_tasks(str(userid)), {'0': 0, '1': 0})

        nuke_user_data_and_taks()
        # start testing by adding tasks with various categories
        add_task_to_test(task, cat_id=0, task_id=0, position=0, delay_days=0)
        self.assertEqual(models.count_immediate_tasks(str(userid)), {'0': 1, '1': 0})
        add_task_to_test(task, cat_id=0, task_id=1, position=1, delay_days=0)
        self.assertEqual(models.count_immediate_tasks(str(userid)), {'0': 2, '1': 0})
        add_task_to_test(task, cat_id=1, task_id=2, position=0, delay_days=0)
        self.assertEqual(models.count_immediate_tasks(str(userid)), {'0': 2, '1': 1})
        add_task_to_test(task, cat_id=1, task_id=3, position=1, delay_days=0)
        self.assertEqual(models.count_immediate_tasks(str(userid)), {'0': 2, '1': 2})
        self.assertEqual(models.count_immediate_tasks(str(userid_ios)), {'0': 2, '1': 2})
        # set limit on ios version. task should be seen in android, but not ios
        task['min_client_version_ios'] = '2.0'
        add_task_to_test(task, cat_id=1, task_id=4, position=2, delay_days=0)
        self.assertEqual(models.count_immediate_tasks(str(userid)), {'0': 2, '1': 3})
        self.assertEqual(models.count_immediate_tasks(str(userid_ios)), {'0': 2, '1': 2})
        # set limit on ios version. should not be seen in android
        task['min_client_version_android'] = '2.0'
        task['min_client_version_ios'] = '1.0' # reset version
        add_task_to_test(task, cat_id=1, task_id=5, position=3, delay_days=0)
        self.assertEqual(models.count_immediate_tasks(str(userid)), {'0': 2, '1': 3})
        self.assertEqual(models.count_immediate_tasks(str(userid_ios)), {'0': 2, '1': 3})

        # nuke tasks - lets start testing exclude-by-country
        task['min_client_version_ios'] = '1.0'
        task['min_client_version_android'] = '1.0'
        nuke_user_data_and_taks()

        # set limit on country code - the client should not be affected
        add_task_to_test(task, cat_id=0, task_id=0, position=0, delay_days=0, excluded_country_codes=['IL'])
        # user doesn't have any ip, so should get the task:
        self.assertEqual(models.count_immediate_tasks(str(userid)), {'0': 1, '1': 0})
        # set user's ip address to an iserali address. should no longer get the task
        db.engine.execute("""update public.user_app_data set ip_address='%s' where user_id='%s';""" % (ISRAEL_IP_ADDRESS, str(userid)))
        self.assertEqual(models.count_immediate_tasks(str(userid)), {'0': 0, '1': 0})
        # set user's ip address to an american address - should now be served to user
        db.engine.execute("""update public.user_app_data set ip_address='%s' where user_id='%s';""" % (US_IP_ADDRESS, str(userid)))
        self.assertEqual(models.count_immediate_tasks(str(userid)), {'0': 1, '1': 0})
        # add another task with both US and IL excluded - should not be served to user (currently with US ip)
        add_task_to_test(task, cat_id=1, task_id=1, position=1, delay_days=0, excluded_country_codes=['IL', 'US'])
        self.assertEqual(models.count_immediate_tasks(str(userid)), {'0': 1, '1': 0})
        # back to israeli ip - should still not be served to user
        db.engine.execute("""update public.user_app_data set ip_address='%s' where user_id='%s';""" % (ISRAEL_IP_ADDRESS, str(userid)))
        self.assertEqual(models.count_immediate_tasks(str(userid)), {'0': 1, '1': 0})
        db.engine.execute("""update public.user_app_data set ip_address=null where user_id='%s';""" % (str(userid)))
        self.assertEqual(models.count_immediate_tasks(str(userid)), {'0': 1, '1': 1})


        # nuke tasks - lets start testing delay days
        nuke_user_data_and_taks()

        # add the first task, which is always available - regardless of the delay_days
        add_task_to_test(task, cat_id=0, task_id=0, position=0, delay_days=1)
        # first task is always available - should have 1 task
        self.assertEqual(models.count_immediate_tasks(str(userid)), {'0': 1, '1': 0})

        # add the 2nd task in the same category. should be blocked by the delay days
        add_task_to_test(task, cat_id=0, task_id=1, position=1, delay_days=1)
        # the delay days on the first task should block the 2nd task
        self.assertEqual(models.count_immediate_tasks(str(userid)), {'0': 1, '1': 0})

        # add the 3rd task. shuld still be blocked by the first task
        add_task_to_test(task, cat_id=0, task_id=2, position=2, delay_days=0)
        # the 3rd task makes no difference
        self.assertEqual(models.count_immediate_tasks(str(userid)), {'0': 1, '1': 0})

        # add the first task on the 2nd category. should be available
        add_task_to_test(task, cat_id=1, task_id=3, position=0, delay_days=1)
        # another task in a different category does get counted
        self.assertEqual(models.count_immediate_tasks(str(userid)), {'0': 1, '1': 1})

        # add another task on the 2nd category. should be blocked by the first task
        add_task_to_test(task, cat_id=1, task_id=4, position=1, delay_days=1)
        # the delay days on the first task should block the 2nd task in the 2nd category
        self.assertEqual(models.count_immediate_tasks(str(userid)), {'0': 1, '1': 1})

        # update the delay days on the first task of the first category.
        # should now open up the 2nd task on the first category
        db.engine.execute("""update task2 set delay_days=0 where task_id='0';""")
        # now, cat_id has 2 immediate tasks
        self.assertEqual(models.count_immediate_tasks(str(userid)), {'0': 2, '1': 1})

        # mark some unrelated task. should make no difference
        db.engine.execute("update user_app_data set completed_tasks_dict=%s", (json.dumps({'0': ['9']}),))
        self.assertEqual(models.count_immediate_tasks(str(userid)), {'0': 2, '1': 1})

        nuke_user_data_and_taks()
        add_task_to_test(task, cat_id=0, task_id=1, position=0, delay_days=0)
        add_task_to_test(task, cat_id=0, task_id=2, position=1, delay_days=0)
        add_task_to_test(task, cat_id=0, task_id=3, position=2, delay_days=0)
        self.assertEqual(models.count_immediate_tasks(str(userid)), {'0': 3, '1': 0})

        nuke_user_data_and_taks()
        add_task_to_test(task, cat_id=0, task_id=1, position=0, delay_days=0)
        add_task_to_test(task, cat_id=0, task_id=2, position=1, delay_days=0)
        add_task_to_test(task, cat_id=0, task_id=3, position=2, delay_days=1)
        self.assertEqual(models.count_immediate_tasks(str(userid)), {'0': 3, '1': 0})

        nuke_user_data_and_taks()
        add_task_to_test(task, cat_id=0, task_id=1, position=0, delay_days=0)
        add_task_to_test(task, cat_id=0, task_id=2, position=1, delay_days=1)
        add_task_to_test(task, cat_id=0, task_id=3, position=2, delay_days=1)
        self.assertEqual(models.count_immediate_tasks(str(userid)), {'0': 0, '1': 2})

        nuke_user_data_and_taks()
        add_task_to_test(task, cat_id=0, task_id=1, position=0, delay_days=1)
        add_task_to_test(task, cat_id=0, task_id=2, position=1, delay_days=1)
        add_task_to_test(task, cat_id=0, task_id=3, position=2, delay_days=1)
        self.assertEqual(models.count_immediate_tasks(str(userid)), {'0': 1, '1': 0})


        # delay days = 0
        nuke_user_data_and_taks()
        add_task_to_test(task, cat_id=0, task_id=0, position=0, delay_days=0)
        add_task_to_test(task, cat_id=0, task_id=1, position=1, delay_days=0)
        add_task_to_test(task, cat_id=0, task_id=2, position=2, delay_days=0)
        add_task_to_test(task, cat_id=1, task_id=3, position=0, delay_days=0)
        add_task_to_test(task, cat_id=1, task_id=4, position=1, delay_days=0)
        add_task_to_test(task, cat_id=1, task_id=5, position=2, delay_days=0)
        self.assertEqual(models.count_immediate_tasks(str(userid)), 6)
        db.engine.execute("update user_app_data set completed_tasks_dict=%s", (json.dumps({'0': ['0']}),))
        self.assertEqual(models.count_immediate_tasks(str(userid)), 5)
        db.engine.execute("update user_app_data set completed_tasks_dict=%s", (json.dumps({'0': ['0', '1']}),))
        self.assertEqual(models.count_immediate_tasks(str(userid)), 4)
        db.engine.execute("update user_app_data set completed_tasks_dict=%s", (json.dumps({'0': ['0', '1', '2']}),))
        self.assertEqual(models.count_immediate_tasks(str(userid)), 3)
        db.engine.execute("update user_app_data set completed_tasks_dict=%s", (json.dumps({'0': ['0', '1', '2'], '1': ['3']}),))
        self.assertEqual(models.count_immediate_tasks(str(userid)), 2)
        db.engine.execute("update user_app_data set completed_tasks_dict=%s", (json.dumps({'0': ['0', '1', '2'], '1': ['3', '4']}),))
        self.assertEqual(models.count_immediate_tasks(str(userid)), 1)
        db.engine.execute("update user_app_data set completed_tasks_dict=%s", (json.dumps({'0': ['0', '1', '2'], '1': ['3', '4', '5']}),))
        self.assertEqual(models.count_immediate_tasks(str(userid)), {'0': 1, '1': 0})


        # delay days = 1
        nuke_user_data_and_taks()
        add_task_to_test(task, cat_id=0, task_id=0, position=0, delay_days=1)
        add_task_to_test(task, cat_id=0, task_id=1, position=1, delay_days=1)
        add_task_to_test(task, cat_id=0, task_id=2, position=2, delay_days=1)
        add_task_to_test(task, cat_id=1, task_id=3, position=0, delay_days=1)
        add_task_to_test(task, cat_id=1, task_id=4, position=1, delay_days=1)
        add_task_to_test(task, cat_id=1, task_id=5, position=2, delay_days=1)
        self.assertEqual(models.count_immediate_tasks(str(userid)), 2)
        db.engine.execute("update user_app_data set completed_tasks_dict=%s", (json.dumps({'0': ['0']}),))
        self.assertEqual(models.count_immediate_tasks(str(userid)), 2)
        db.engine.execute("update user_app_data set completed_tasks_dict=%s", (json.dumps({'0': ['0', '1']}),))
        self.assertEqual(models.count_immediate_tasks(str(userid)), 2)
        db.engine.execute("update user_app_data set completed_tasks_dict=%s", (json.dumps({'0': ['0', '1', '2']}),))
        self.assertEqual(models.count_immediate_tasks(str(userid)), 1)
        db.engine.execute("update user_app_data set completed_tasks_dict=%s", (json.dumps({'0': ['0', '1', '2'], '1': ['3']}),))
        self.assertEqual(models.count_immediate_tasks(str(userid)), 1)
        db.engine.execute("update user_app_data set completed_tasks_dict=%s", (json.dumps({'0': ['0', '1', '2'], '1': ['3', '4']}),))
        self.assertEqual(models.count_immediate_tasks(str(userid)), 1)
        db.engine.execute("update user_app_data set completed_tasks_dict=%s", (json.dumps({'0': ['0', '1', '2'], '1': ['3', '4', '5']}),))
        self.assertEqual(models.count_immediate_tasks(str(userid)), {'0': 1, '1': 0})

        # mixed delay days , and delay days = 2 should make no difference
        nuke_user_data_and_taks()
        add_task_to_test(task, cat_id=0, task_id=0, position=0, delay_days=2)
        add_task_to_test(task, cat_id=0, task_id=1, position=1, delay_days=0)
        add_task_to_test(task, cat_id=0, task_id=2, position=2, delay_days=2)
        add_task_to_test(task, cat_id=1, task_id=3, position=0, delay_days=2)
        add_task_to_test(task, cat_id=1, task_id=4, position=1, delay_days=0)
        add_task_to_test(task, cat_id=1, task_id=5, position=2, delay_days=2)
        self.assertEqual(models.count_immediate_tasks(str(userid)), 2)  # 1 + 1
        db.engine.execute("update user_app_data set completed_tasks_dict=%s", (json.dumps({'0': ['0']}),))
        self.assertEqual(models.count_immediate_tasks(str(userid)), 3)  # 2 + 1
        db.engine.execute("update user_app_data set completed_tasks_dict=%s", (json.dumps({'0': ['0', '1']}),))
        self.assertEqual(models.count_immediate_tasks(str(userid)), 2)  # 1 + 1
        db.engine.execute("update user_app_data set completed_tasks_dict=%s", (json.dumps({'0': ['0', '1', '2']}),))
        self.assertEqual(models.count_immediate_tasks(str(userid)), 1)  # 0 + 1
        db.engine.execute("update user_app_data set completed_tasks_dict=%s", (json.dumps({'0': ['0', '1', '2'], '1': ['3']}),))
        self.assertEqual(models.count_immediate_tasks(str(userid)), 2)  # 0 + 2
        db.engine.execute("update user_app_data set completed_tasks_dict=%s", (json.dumps({'0': ['0', '1', '2'], '1': ['3', '4']}),))
        self.assertEqual(models.count_immediate_tasks(str(userid)), 1)  # 0 + 1
        db.engine.execute("update user_app_data set completed_tasks_dict=%s", (json.dumps({'0': ['0', '1', '2'], '1': ['3', '4', '5']}),))
        self.assertEqual(models.count_immediate_tasks(str(userid)), 0)  # 0 + 0

        # throw in a couple of ad-hoc tasks
        nuke_user_data_and_taks()
        add_task_to_test(task, cat_id=0, task_id=0, position=0, delay_days=2)
        add_task_to_test(task, cat_id=0, task_id=1, position=1, delay_days=0)
        add_task_to_test(task, cat_id=0, task_id=2, position=2, delay_days=2)
        add_task_to_test(task, cat_id=1, task_id=3, position=0, delay_days=2)
        add_task_to_test(task, cat_id=1, task_id=4, position=1, delay_days=0)
        add_task_to_test(task, cat_id=1, task_id=5, position=2, delay_days=2)
        # add 2 active ad-hoc tasks
        add_task_to_test(task, cat_id=0, task_id=6, position=-1, delay_days=0, task_start_date=str(now.shift(hours=-1)), task_expiration_date=str(now.shift(hours=1)))
        add_task_to_test(task, cat_id=1, task_id=7, position=-1, delay_days=0, task_start_date=str(now.shift(hours=-1)), task_expiration_date=str(now.shift(hours=1)))
        # 2 yet-inactive ad-hoc tasks
        add_task_to_test(task, cat_id=0, task_id=8, position=-1, delay_days=0, task_start_date=str(now.shift(hours=+10)), task_expiration_date=str(now.shift(hours=11)))
        add_task_to_test(task, cat_id=1, task_id=9, position=-1, delay_days=0, task_start_date=str(now.shift(hours=+10)), task_expiration_date=str(now.shift(hours=11)))
        # 2 already-inactive ad-hoc tasks
        add_task_to_test(task, cat_id=0, task_id=10, position=-1, delay_days=0, task_start_date=str(now.shift(hours=-10)), task_expiration_date=str(now.shift(hours=-9)))
        add_task_to_test(task, cat_id=1, task_id=11, position=-1, delay_days=0, task_start_date=str(now.shift(hours=-10)), task_expiration_date=str(now.shift(hours=-9)))
        self.assertEqual(models.count_immediate_tasks(str(userid)), 4)  # [6,0],[7,3]
        db.engine.execute("update user_app_data set completed_tasks_dict=%s", (json.dumps({'0': ['6']}),))
        self.assertEqual(models.count_immediate_tasks(str(userid)), 3)  # [0],[7,3]
        db.engine.execute("update user_app_data set completed_tasks_dict=%s", (json.dumps({'0': ['6'], '1': ['7']}),))
        self.assertEqual(models.count_immediate_tasks(str(userid)), 2)  # [0],[3]
        db.engine.execute("update user_app_data set completed_tasks_dict=%s", (json.dumps({'0': ['6', '0'], '1': ['7']}),))
        self.assertEqual(models.count_immediate_tasks(str(userid)), 3)  # [1,2],[3]
        db.engine.execute("update user_app_data set completed_tasks_dict=%s", (json.dumps({'0': ['6', '0'], '1': ['7', '3']}),))
        self.assertEqual(models.count_immediate_tasks(str(userid)), 4)  # [1,2],[4,5]
        db.engine.execute("update user_app_data set completed_tasks_dict=%s", (json.dumps({'0': ['6', '0', '1', '2', '3'], '1': ['7', '3', '4', '5']}),))
        self.assertEqual(models.count_immediate_tasks(str(userid)), {'0': 1, '1': 0})  # [], []



if __name__ == '__main__':
    unittest.main()
