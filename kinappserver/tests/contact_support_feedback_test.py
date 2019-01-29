import simplejson as json
from uuid import uuid4
from time import sleep
import testing.postgresql

import unittest
import kinappserver
from kinappserver import db, stellar, models

import logging as log
log.getLogger().setLevel(log.INFO)


USER_ID_HEADER = "X-USERID"

class Tester(unittest.TestCase):
    """tests the entire spend-scenario: creating an order and then redeeming it"""

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


    def test_contact_support_enpoint(self):
        resp = self.app.post('/contact-us',
                             data=json.dumps({
                                 'category': "Backup & Restore",
                                 'sub_category': "How to backup your account",
                                 'name': "Aryeh Katz",
                                 'email': "somemail@dom.com",
                                 'description': "Lurm ipsumLurm ipsumLurm ipsumLurm ipsumLurm ipsumLurm ipsumLurm ipsumpsumLurm ipsumLurm ipsumLurm ipsumLurm ipsumLurm ipsumpsumLurm ipsumLurm ipsumLurm ipsumLurm ipsumLurm ipsum",
                                 'user_id': str(uuid4()),
                                 'platform': 'android',
                                 'version': '1.1.1',
                                 'debug': 'true'
                             }),
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        resp = self.app.post('/feedback',
                             data=json.dumps({
                                 'category': "Feedback",
                                 'name': "Aryeh Katz",
                                 'email': "somemail@dom.com",
                                 'description': "Lurm ipsumLurm ipsumLurm ipsumLurm ipsumLurm ipsumLurm ipsumLurm ipsumpsumLurm ipsumLurm ipsumLurm ipsumLurm ipsumLurm ipsumpsumLurm ipsumLurm ipsumLurm ipsumLurm ipsumLurm ipsum",
                                 'user_id': str(uuid4()),
                                 'platform': 'android',
                                 'version': '1.1.1',
                                 'debug': 'true'
                             }),
                             content_type='application/json')
        self.assertEqual(resp.status_code, 200)

if __name__ == '__main__':
    unittest.main()
