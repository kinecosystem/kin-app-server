import unittest
import uuid

import testing.postgresql
import simplejson as json

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

    def test_update_token(self):
        """test update token scenarios"""
        userid = uuid.uuid4()

        # attempt to update a yet-unregistered user
        resp = self.app.post('/user/update-token',
                            data=json.dumps({
                            'token': 'sometoken'}),
                            headers={USER_ID_HEADER: str(userid)},
                            content_type='application/json')
        self.assertEqual(resp.status_code, 400)

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

        # update the token
        resp = self.app.post('/user/update-token',
                            data=json.dumps({
                            'token': 'newtoken'}),
                            headers={USER_ID_HEADER: str(userid)},
                            content_type='application/json')
        print(json.loads(resp.data))
        self.assertEqual(resp.status_code, 200)


        print(models.list_all_users())
        assert(models.user_exists(userid))
        assert(not models.user_exists(uuid.uuid4()))

if __name__ == '__main__':
    unittest.main()
