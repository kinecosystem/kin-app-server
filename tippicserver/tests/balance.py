import simplejson as json
from uuid import uuid4
from time import sleep
import testing.postgresql

import unittest
import tippicserver
from tippicserver import db, stellar, models

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
        tippicserver.app.config['SQLALCHEMY_DATABASE_URI'] = self.postgresql.url()
        tippicserver.app.testing = True
        self.app = tippicserver.app.test_client()
        db.drop_all()
        db.create_all()


    def tearDown(self):
        self.postgresql.stop()


    def test_balance(self):
        """test getting the balance"""

        resp = self.app.get('/balance')
        self.assertEqual(resp.status_code, 200)
        print(json.loads(resp.data))

if __name__ == '__main__':
    unittest.main()
