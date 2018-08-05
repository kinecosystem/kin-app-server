import unittest
from uuid import uuid4
import json

import testing.postgresql

import kinappserver
from kinappserver import db

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


    def test_backup_questions_api(self):
        """test good creation and allocation/release"""
        db.engine.execute("insert into public.backup_question values(1,'how much wood?');")
        db.engine.execute("insert into public.backup_question values(2,'how much non-wood?');")

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

        resp = self.app.get('/backup/hints')
        data = json.loads(resp.data)
        print('backup_hints: %s' % data)
        self.assertEqual(resp.status_code, 200)

        resp = self.app.get('/user/backup/hints', headers={USER_ID_HEADER: str(userid)})
        data = json.loads(resp.data)
        print('user_backup_hints: %s' % data)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(data, {'hints': None})

        resp = self.app.post('/user/backup/hints',
                             data=json.dumps({'hints': ['1', '2']}),
                             headers={USER_ID_HEADER: str(userid)},  content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        resp = self.app.get('/user/backup/hints', headers={USER_ID_HEADER: str(userid)})
        data = json.loads(resp.data)
        print('user_backup_hints: %s' % data)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(data, {'hints': ['1', '2']})

        resp = self.app.post('/user/backup/hints',
                             data=json.dumps({'hints': ['1', '2', '3']}),
                             headers={USER_ID_HEADER: str(userid)},  content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        resp = self.app.get('/user/backup/hints', headers={USER_ID_HEADER: str(userid)})
        data = json.loads(resp.data)
        print('user_backup_hints: %s' % data)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(data, {'hints': ['1', '2', '3']})

if __name__ == '__main__':
    unittest.main()
