from time import sleep
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

    def test_count_immediate_tasks(self):
        """test storting task results"""

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

        def add_task_to_test(task, cat_id, task_id, position, delay_days=0, excluded_country_codes=None):
            task['position'] = position
            task['id'] = str(task_id)
            task['cat_id'] = str(cat_id)
            task['delay_days'] = delay_days
            if excluded_country_codes:
                task['excluded_country_codes'] = excluded_country_codes
            resp = self.app.post('/task/add',
                                 data=json.dumps({
                                     'task': task}),
                                 headers={},
                                 content_type='application/json')
            self.assertEqual(resp.status_code, 200)

        for cat_id in range(2):
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

        db.engine.execute("""update public.push_auth_token set auth_token='%s' where user_id='%s';""" % (str(userid), str(userid)))

        resp = self.app.post('/user/auth/ack',
                             data=json.dumps({
                                 'token': str(userid)}),
                             headers={USER_ID_HEADER: str(userid)},
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)



        # start testing by adding tasks with various categories
        add_task_to_test(task, cat_id=0,task_id=0,position=0,delay_days=0)
        self.assertEqual(models.count_immediate_tasks(str(userid)), 1)
        add_task_to_test(task, cat_id=0, task_id=1, position=1, delay_days=0)
        self.assertEqual(models.count_immediate_tasks(str(userid)), 2)
        add_task_to_test(task, cat_id=1, task_id=2, position=0, delay_days=0)
        self.assertEqual(models.count_immediate_tasks(str(userid)), 3)
        add_task_to_test(task, cat_id=1, task_id=3, position=1, delay_days=0)
        self.assertEqual(models.count_immediate_tasks(str(userid)), 4)
        # set limit on ios version. should not make a difference for android:
        task['min_client_version_ios'] = '2.0'
        add_task_to_test(task, cat_id=1, task_id=4, position=2, delay_days=0)
        self.assertEqual(models.count_immediate_tasks(str(userid)), 5)
        # set limit on ios version. should make a difference for android:
        task['min_client_version_android'] = '2.0'
        add_task_to_test(task, cat_id=1, task_id=5, position=3, delay_days=0)
        self.assertEqual(models.count_immediate_tasks(str(userid)), 5)

        # nuke tasks - lets start testing exclude-by-country
        task['min_client_version_ios'] = '1.0'
        task['min_client_version_android'] = '1.0'
        db.engine.execute("""delete from task2;""")

        # set limit on country code - the client should not be affected
        add_task_to_test(task, cat_id=0, task_id=0, position=0, delay_days=0, excluded_country_codes=['IL'])
        # user doesn't have any ip, so should get the task:
        self.assertEqual(models.count_immediate_tasks(str(userid)), 1)
        # set user's ip address to an iserali address. should no longer get the task
        db.engine.execute("""update public.user_app_data set ip_address='%s' where user_id='%s';""" % ('199.203.79.137', str(userid)))
        self.assertEqual(models.count_immediate_tasks(str(userid)), 0)
        # set user's ip address to an american address - should now be served to user
        db.engine.execute("""update public.user_app_data set ip_address='%s' where user_id='%s';""" % ('50.196.205.141', str(userid)))
        self.assertEqual(models.count_immediate_tasks(str(userid)), 1)
        # add another task with both US and IL excluded - should not be served to user (currently with US ip)
        add_task_to_test(task, cat_id=1, task_id=1, position=1, delay_days=0, excluded_country_codes=['IL', 'US'])
        self.assertEqual(models.count_immediate_tasks(str(userid)), 1)
        # back to israeli ip - should still not be served to user
        db.engine.execute("""update public.user_app_data set ip_address='%s' where user_id='%s';""" % ('199.203.79.137', str(userid)))
        self.assertEqual(models.count_immediate_tasks(str(userid)), 0)
        db.engine.execute("""update public.user_app_data set ip_address=null where user_id='%s';""" % (str(userid)))
        self.assertEqual(models.count_immediate_tasks(str(userid)), 2)


        # nuke tasks - lets start testing delay days
        db.engine.execute("""delete from task2;""")

        add_task_to_test(task, cat_id=0, task_id=0, position=0, delay_days=1)
        # first task is always available
        self.assertEqual(models.count_immediate_tasks(str(userid)), 1)
        add_task_to_test(task, cat_id=0, task_id=1, position=1, delay_days=1)
        # the delay days on the first task should block the 2nd task
        self.assertEqual(models.count_immediate_tasks(str(userid)), 1)
        add_task_to_test(task, cat_id=0, task_id=2, position=2, delay_days=0)
        # the 3rd task makes no difference
        self.assertEqual(models.count_immediate_tasks(str(userid)), 1)
        add_task_to_test(task, cat_id=1, task_id=3, position=0, delay_days=1)
        # another task in a different category does get counted
        self.assertEqual(models.count_immediate_tasks(str(userid)), 2)
        add_task_to_test(task, cat_id=1, task_id=4, position=1, delay_days=1)
        # the delay days on the first task should block the 2nd task in the 2nd category
        self.assertEqual(models.count_immediate_tasks(str(userid)), 2)

        db.engine.execute("""update task2 set delay_days=0 where task_id='0';""")
        # now, cat_id has 2 immediate tasks
        self.assertEqual(models.count_immediate_tasks(str(userid)), 3)

        # mark some unrelated task. should make no difference
        db.engine.execute("update user_app_data set completed_tasks_dict=%s", (json.dumps({'0': ['9']}),))
        self.assertEqual(models.count_immediate_tasks(str(userid)), 3)

        # mark task no. 0. the number will drop to 2 (task ids 1, 3)
        db.engine.execute("update user_app_data set completed_tasks_dict=%s", (json.dumps({'0': ['0']}),))
        self.assertEqual(models.count_immediate_tasks(str(userid)), 2)

        # mark tasks no. 0,1,2, the number will drop to 1 (only cat 2 tasks remain)
        db.engine.execute("update user_app_data set completed_tasks_dict=%s", (json.dumps({'0': ['0', '1', '2']}),))
        self.assertEqual(models.count_immediate_tasks(str(userid)), 1)

        # mark tasks no. 3,4  the number will drop to 1 (only cat 1 tasks remain)
        db.engine.execute("update user_app_data set completed_tasks_dict=%s", (json.dumps({'1': ['3', '4']}),))
        self.assertEqual(models.count_immediate_tasks(str(userid)), 1)
        return

        # mark tasks no. 0,3,4  the number will drop to 1 (only cat 1 tasks remain)
        db.engine.execute("update user_app_data set completed_tasks_dict=%s", (json.dumps({'1': ['3', '4'], '0': ['0']}),))
        self.assertEqual(models.count_immediate_tasks(str(userid)), 1)

        # mark tasks no. 0,1,3,4  the number will drop to 1 (only cat 1 tasks remain)
        db.engine.execute("update user_app_data set completed_tasks_dict=%s", (json.dumps({'1': ['3', '4'], '0': ['0', '1']}),))
        self.assertEqual(models.count_immediate_tasks(str(userid)), 2)


        # mark all tasks in both cats - nothing should remain
        db.engine.execute("update user_app_data set completed_tasks_dict=%s", (json.dumps({'0': ['0', '1', '2'], '1': ['3', '4']}),))
        self.assertEqual(models.count_immediate_tasks(str(userid)), 0)





if __name__ == '__main__':
    unittest.main()
