import unittest
from uuid import uuid4
import json
import time

import testing.postgresql

import kinappserver
from kinappserver import db

import logging as log
log.getLogger().setLevel(log.INFO)

USER_ID_HEADER = "X-USERID"
AUTH_TOKEN_HEADER = "X-AUTH-TOKEN"

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
        """test various aspects of the backup questions"""
        db.engine.execute("insert into public.backup_question values(1,'how much wood?');")
        db.engine.execute("insert into public.backup_question values(2,'how much non-wood?');")

        # create a user
        userid1 = uuid4()
        resp = self.app.post('/user/register',
            data=json.dumps({
                            'user_id': str(userid1),
                            'os': 'android',
                            'device_model': 'samsung8',
                            'device_id': '234234',
                            'time_zone': '05:00',
                            'token': 'fake_token',
                            'app_ver': '1.0'}),
            headers={},
            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # set a fake token
        db.engine.execute("""update public.push_auth_token set auth_token='%s' where user_id='%s';""" % (str(userid1), str(userid1)))


        resp = self.app.post('/user/auth/ack',
                            data=json.dumps({
                            'token': str(userid1)}),
                            headers={USER_ID_HEADER: str(userid1)},
                            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # should succeed anyways
        resp = self.app.get('/backup/hints')
        data = json.loads(resp.data)
        print('backup_hints: %s' % data)
        self.assertEqual(resp.status_code, 200)

        # user1 updates his phone number to the server after client-side verification
        phone_num = '+9720528802120'
        resp = self.app.post('/user/firebase/update-id-token',
                    data=json.dumps({
                        'token': 'fake-token',
                        'phone_number': phone_num}),
                    headers={USER_ID_HEADER: str(userid1)},
                    content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        print('backup_hints as received from phone-verification of user_id1: %s' % data)
        self.assertEqual(data['hints'], [])  # no hints yet

        # mock onboarding
        db.engine.execute("""update public.user set public_address='%s' where user_id='%s';""" % ('my-address-1', str(userid1)))
        db.engine.execute("""update public.user set onboarded=true where user_id='%s';""" % str(userid1))

        # try to restore user_id PRIOR to setting hints - should fail
        resp = self.app.post('/user/restore',
                             data=json.dumps({
                                 'address': 'my-address-1'}),
                             headers={USER_ID_HEADER: str(userid1)},
                             content_type='application/json')
        self.assertNotEqual(resp.status_code, 200)

        # deauth user
        db.engine.execute("""update public.push_auth_token set authenticated=false where user_id='%s';""" % (str(userid1)))

        resp = self.app.post('/user/backup/hints',  # should fail - not authenticated
                             data=json.dumps({'hints': [1, 2]}),
                             headers={USER_ID_HEADER: str(userid1)},  content_type='application/json')
        self.assertEqual(resp.status_code, 403)

        # auth user
        db.engine.execute("""update public.push_auth_token set authenticated=true where user_id='%s';""" % (str(userid1)))


        import arrow
        now = arrow.utcnow().timestamp
        resp = self.app.post('/user/backup/hints',  # should succeed
                             data=json.dumps({'hints': [1, 2]}),
                             headers={USER_ID_HEADER: str(userid1), AUTH_TOKEN_HEADER: str(userid1)},  content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        res = db.engine.execute("select previous_hints from phone_backup_hints;")
        previous_hints = res.fetchall()[0]
        print('previous_hints %s' % previous_hints)
        self.assertEqual(previous_hints, (None,))

        resp = self.app.post('/user/backup/hints',  # should fail as there are no such hints
                             data=json.dumps({'hints': [1, 11]}),
                             headers={USER_ID_HEADER: str(userid1), AUTH_TOKEN_HEADER: str(userid1)},  content_type='application/json')
        self.assertNotEqual(resp.status_code, 200)

        resp = self.app.post('/user/backup/hints',  # should fail as there are no hints
                             data=json.dumps({'hints': []}),
                             headers={USER_ID_HEADER: str(userid1), AUTH_TOKEN_HEADER: str(userid1)},  content_type='application/json')
        self.assertNotEqual(resp.status_code, 200)

        time.sleep(1)
        now1 = arrow.utcnow().timestamp
        resp = self.app.post('/user/backup/hints',  # should succeed, also - overrides previous results
                             data=json.dumps({'hints': [1, 1]}),
                             headers={USER_ID_HEADER: str(userid1), AUTH_TOKEN_HEADER: str(userid1)},  content_type='application/json')
        self.assertEqual(resp.status_code, 200)


        res = db.engine.execute("select previous_hints from phone_backup_hints;")
        previous_hints = res.fetchall()[0]
        print('previous_hints %s' % previous_hints)
        self.assertEqual(previous_hints, ([{'date': now, 'hints': [1, 2]}],))


        time.sleep(1)
        now2 = arrow.utcnow().timestamp
        resp = self.app.post('/user/backup/hints',  # should succeed, also - overrides previous results
                             data=json.dumps({'hints': [2, 2]}),
                             headers={USER_ID_HEADER: str(userid1), AUTH_TOKEN_HEADER: str(userid1)},  content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        res = db.engine.execute("select previous_hints from phone_backup_hints;")
        previous_hints = res.fetchall()[0]
        print('previous_hints %s' % previous_hints)
        self.assertEqual(previous_hints, ([{'date': now, 'hints': [1, 2]}, {'date': now1, 'hints': [1, 1]}],))

        time.sleep(1)
        now3 = arrow.utcnow().timestamp
        resp = self.app.post('/user/backup/hints',  # should succeed, also - overrides previous results
                             data=json.dumps({'hints': [2, 1]}),
                             headers={USER_ID_HEADER: str(userid1), AUTH_TOKEN_HEADER: str(userid1)},  content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        res = db.engine.execute("select previous_hints from phone_backup_hints;")
        previous_hints = res.fetchall()[0]
        print('previous_hints %s' % previous_hints)
        self.assertEqual(previous_hints, ([{'date': now, 'hints': [1, 2]}, {'date': now1, 'hints': [1, 1]}, {'date': now2, 'hints': [2, 2]}],))


        resp = self.app.post('/user/backup/hints',  # should succeed, also - overrides previous results
                             data=json.dumps({'hints': [2, 1]}),
                             headers={USER_ID_HEADER: str(userid1), AUTH_TOKEN_HEADER: str(userid1)},  content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        res = db.engine.execute("select previous_hints from phone_backup_hints;")
        previous_hints = res.fetchall()[0]
        print('hints %s' % previous_hints)
        self.assertEqual(previous_hints, ([{'date': now, 'hints': [1, 2]}, {'date': now1, 'hints': [1, 1]}, {'date': now2, 'hints': [2, 2]}, {'date': now3, 'hints': [2, 1]}],))


        # create another user with the same phone
        userid2 = uuid4()
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

        # set a fake token
        db.engine.execute("""update public.push_auth_token set auth_token='%s' where user_id='%s';""" % (str(userid2), str(userid2)))

        # user2 updates his phone number to the server after client-side verification.
        # should have the same hints as user1
        resp = self.app.post('/user/firebase/update-id-token',
                             data=json.dumps({
                                 'token': 'fake-token',
                                 'phone_number': phone_num}),
                             headers={USER_ID_HEADER: str(userid2)},
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        print('backup_hints as received from phone-verification of user_id2: %s' % data)
        self.assertEqual(data['hints'],  [2, 1])

        # try to restore with the wrong address - should fail
        resp = self.app.post('/user/restore',
                             data=json.dumps({
                                 'address': 'no-such-address'}),
                             headers={USER_ID_HEADER: str(userid2)},
                             content_type='application/json')
        self.assertNotEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        print('restore result: %s' % data)


        # try to restore with the right address
        resp = self.app.post('/user/restore',
                             data=json.dumps({
                                 'address': 'my-address-1'}),
                             headers={USER_ID_HEADER: str(userid2)},
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        print('restore result: %s' % data)
        data = json.loads(resp.data)
        self.assertEqual(data['user_id'], str(userid1))

        res = db.engine.execute("select * from phone_backup_hints;")
        print('hints %s' % res.fetchall()[0])



if __name__ == '__main__':
    unittest.main()
