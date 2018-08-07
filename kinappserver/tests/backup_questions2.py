import unittest
from uuid import uuid4
import json

import testing.postgresql

import kinappserver
from kinappserver import db

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


    def test_steal_address_with_backup(self):
        """test restoring using someone else's address"""

        db.engine.execute("insert into public.backup_question values(1,'how much wood?');")
        db.engine.execute("insert into public.backup_question values(2,'how much non-wood?');")
        db.engine.execute("insert into public.backup_question values(3,'how much whatever man. whatever');")

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

        resp = self.app.post('/user/backup/hints', # should succeed
                             data=json.dumps({'hints': [1, 2]}),
                             headers={USER_ID_HEADER: str(userid1), AUTH_TOKEN_HEADER: str(userid1)},  content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # create another (3rd) user. this is an unsuspecting 3rd party. we'll try to steal his address
        userid3 = uuid4()
        resp = self.app.post('/user/register',
            data=json.dumps({
                            'user_id': str(userid3),
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
        db.engine.execute("""update public.push_auth_token set auth_token='%s' where user_id='%s';""" % (str(userid3), str(userid3)))

        # userid3 updates his phone number to the server after client-side verification
        phone_num2 = '+9720528802121'
        resp = self.app.post('/user/firebase/update-id-token',
                    data=json.dumps({
                        'token': 'fake-token',
                        'phone_number': phone_num2}),
                    headers={USER_ID_HEADER: str(userid3)},
                    content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        print('backup_hints as received from phone-verification of user_id1: %s' % data)
        self.assertEqual(data['hints'], [])  # no hints yet

        # mock onboarding
        db.engine.execute("""update public.user set public_address='%s' where user_id='%s';""" % ('my-address-3', str(userid3)))
        db.engine.execute("""update public.user set onboarded=true where user_id='%s';""" % str(userid3))

        resp = self.app.post('/user/backup/hints', # should succeed
                             data=json.dumps({'hints': [2, 3]}),
                             headers={USER_ID_HEADER: str(userid3), AUTH_TOKEN_HEADER: str(userid3)},  content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # try to use userid2 to restore with userid3's address

        # create another user with the same phone and address
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
        self.assertEqual(data['hints'],  [1, 2])

        # try to restore with userid3 address - should fail
        resp = self.app.post('/user/restore',
                             data=json.dumps({
                                 'address': 'my-address-3'}),
                             headers={USER_ID_HEADER: str(userid2)},
                             content_type='application/json')
        self.assertNotEqual(resp.status_code, 200)

        # try to restore with userid1 address - should succeed
        resp = self.app.post('/user/restore',
                             data=json.dumps({
                                 'address': 'my-address-1'}),
                             headers={USER_ID_HEADER: str(userid2)},
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertEqual(data['user_id'], str(userid1))

if __name__ == '__main__':
    unittest.main()
