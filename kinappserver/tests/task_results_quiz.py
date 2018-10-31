from time import sleep
import unittest
import uuid
import copy

import simplejson as json
import testing.postgresql

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
        #overwrite the db name, dont interfere with stage db data
        self.postgresql = testing.postgresql.Postgresql()
        kinappserver.app.config['SQLALCHEMY_DATABASE_URI'] = self.postgresql.url()
        kinappserver.app.testing = True
        self.app = kinappserver.app.test_client()
        db.drop_all()
        db.create_all()


    def tearDown(self):
        self.postgresql.stop()

    def test_task_results_quiz(self):
        """test storting quiz-type tasks results - and correct calculation of rewards"""


        cat = {'id': '0',
               "skip_image_test": True,
          'title': 'cat-title',
          'ui_data': {'color': "#123",
                      'image_url': 'https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png',
                      'header_image_url': 'https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png'}}

        resp = self.app.post('/category/add',
                            data=json.dumps({
                            'category': cat}),
                            headers={},
                            content_type='application/json')
        self.assertEqual(resp.status_code, 200)


        # add a task
        task = {
          "skip_image_test": True,
          "id": "0",
          "cat_id": '0',
          "position": 0,
          "start_date": 1532252893,
          "provider": {
            "name": "Kinit Team",
            "image_url": "https://cdn.kinitapp.com/brand_img/poll_logo_kin.png"
          },
          "min_to_complete": 2,
          "tags": [
            "Finance"
          ],
          "type": "quiz",
          "title": "Kin Quiz",
          "price": 1,
          "desc": "Let's test your Kinowledge!",
          "items": [
            {
              "id": "844",
              "results": [
                {
                  "id": "46584",
                  "text": "I know that already (Correct)"
                },
                {
                  "id": "4589",
                  "text": "I'm still a bit confused about that"
                }
              ],
              "type": "text",
              "text": "Kin is a cryptocurrency that can be earned or spent on things you like.",
              "quiz_data": {
                "answer_id": "46584",
                "explanation": "In May 25, 2017, Kik announces cryptocurrency as a first step to launching a decentralized ecosystem of digital services.",
                "reward": 1
              }
            },
            {
              "id": "347",
              "results": [
                {
                  "id": "4359698",
                  "text": "For investing my time"
                },
                {
                  "id": "345768",
                  "text": "For participating in the Kin Ecosystem"
                },
                {
                  "id": "45763",
                  "text": "For creating value"
                },
                {
                  "id": "36756",
                  "text": "All of the above (Correct)"
                }
              ],
              "type": "text",
              "text": "Why are you getting Kin?",
              "quiz_data": {
                "answer_id": "36756",
                "explanation": "All of the above is the right answer!",
                "reward": 1
              }
            }
        ]}


        resp = self.app.post('/task/add',
                            data=json.dumps({
                            'task': task}),
                            headers={},
                            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # Try adding a bad task - no explanation on the first item's quiz data:
        bad_task = copy.deepcopy(task)
        bad_task['id'] = '2'
        bad_task['items'][0]['quiz_data'].pop('explanation')
        print(bad_task)
        resp = self.app.post('/task/add',
                            data=json.dumps({
                            'task': bad_task}),
                            headers={},
                            content_type='application/json')
        self.assertNotEqual(resp.status_code, 200)

        # Try adding a bad task - no answer_id on the first item's quiz data:
        bad_task = copy.deepcopy(task)
        bad_task['id'] = '3'
        bad_task['items'][0]['quiz_data'].pop('reward')
        print(bad_task)
        resp = self.app.post('/task/add',
                            data=json.dumps({
                            'task': bad_task}),
                            headers={},
                            content_type='application/json')
        self.assertNotEqual(resp.status_code, 200)

        # Try adding a bad task - no answer_id on the first item's quiz data:
        bad_task = copy.deepcopy(task)
        bad_task['id'] = '4'
        bad_task['items'][0]['quiz_data'].pop('answer_id')
        print(bad_task)
        resp = self.app.post('/task/add',
                            data=json.dumps({
                            'task': bad_task}),
                            headers={},
                            content_type='application/json')
        self.assertNotEqual(resp.status_code, 200)

        # Try adding a bad task - answer_id does not match any question
        bad_task = copy.deepcopy(task)
        bad_task['id'] = '5'
        bad_task['items'][0]['quiz_data']['answer_id'] = '-1'
        print(bad_task)
        resp = self.app.post('/task/add',
                            data=json.dumps({
                            'task': bad_task}),
                            headers={},
                            content_type='application/json')
        self.assertNotEqual(resp.status_code, 200)


        # set the delay_days on all the tasks to zero
        resp = self.app.post('/task/delay_days',
                            data=json.dumps({
                            'days': 0}),
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

        sleep(1)

        # get the user's current tasks
        headers = {USER_ID_HEADER: userid}
        resp = self.app.get('/user/tasks', headers=headers)
        data = json.loads(resp.data)
        print('data: %s' % data)
        self.assertEqual(resp.status_code, 200)
        print('next task id: %s' % data['tasks']['0'][0]['id'])
        print('next task start date: %s' % data['tasks']['0'][0]['start_date'])
        self.assertEqual(data['tasks']['0'][0]['id'], '0')


        # send task results
        resp = self.app.post('/user/task/results',
                            data=json.dumps({
                            'id': '0',
                            'address': 'GCYUCLHLMARYYT5EXJIK2KZJCMRGIKKUCCJKJOAPUBALTBWVXAT4F4OZ',
                            'results': [{"aid": ["46584"], "qid": "844"}, {"aid": ["45763"], "qid": "347"}],  # one right answer and one wrong answer
                            'send_push': False
                            }),
                            headers={USER_ID_HEADER: str(userid)},
                            content_type='application/json')
        print('post task results response: %s' % json.loads(resp.data))
        self.assertEqual(resp.status_code, 200)
        sleep(8) # give the thread enough time to complete before the db connection is shutdown

        #print(model.list_all_users_results_data())

        # get user tx history - should have 1 items
        resp = self.app.get('/user/transactions', headers={USER_ID_HEADER: str(userid)})
        self.assertEqual(resp.status_code, 200)
        print('txs: %s' % json.loads(resp.data))
        self.assertNotEqual(json.loads(resp.data)['txs'], [])
        self.assertEqual(json.loads(resp.data)['txs'][0]['amount'], 2)  # 1 for the task and 1 for the reward

        sleep(8)  # give the thread enough time to complete before the db connection is shutdown


if __name__ == '__main__':
    unittest.main()
