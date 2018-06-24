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

    def test_truex_callback(self):

        url = "/truex/callback?application_key=e8e7dbe7d7b1d16f0ab2&network_user_id=c1ee58d9-c068-44fc-8c62-400f0537e8d2&currency_amount=1&currency_label=&revenue=0.0072&placement_hash=21be84de4fa0cc0315a5563d02e293b99b67cd16&campaign_name=Kik+-+Kin+-+KF+Panda+Mobile+SVNRE&campaign_id=13255&creative_name=KF+Panda+Mobile+SVNRE&creative_id=8974&engagement_id=883635952&client_request_id=1529492319&sig=eXeHQVjiJEx%2BaCnctbZq1g08q0Y%3D"

        print('processing truex callback - should work')
        # get the truex activity - should fail
        resp = self.app.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(b'1', resp.data)

if __name__ == '__main__':
    unittest.main()
