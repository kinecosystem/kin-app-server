import simplejson as json
from uuid import uuid4
from time import sleep
import testing.postgresql
import arrow

import unittest
import kinappserver
from kinappserver import db, stellar, models, utils, encrypt



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


    def test_utils(self):
        """test various util functions"""

        # requires a redis instance
        memo = '1-kit-sec7ed0797cf340cb979ac'
        user_id = 'f8acc02c-0818-40f7-9938-7f1d1007c43f'
        task_id = '9'
        send_push = False
        timestamp = arrow.utcnow().timestamp
        self.assertEqual(utils.write_payment_data_to_cache(memo, user_id, task_id, timestamp, send_push), True)
        user_id_r, task_id_r, timestamp_r, send_push_r = utils.read_payment_data_from_cache(memo)
        self.assertEqual(user_id, user_id_r)
        self.assertEqual(task_id, task_id_r)
        self.assertEqual(send_push, send_push_r)
        self.assertEqual(timestamp_r, timestamp)






if __name__ == '__main__':
    unittest.main()
