import simplejson as json
from uuid import uuid4
from time import sleep
import testing.postgresql

import unittest
import kinappserver
from kinappserver import db, stellar, models


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


    def test_versions(self):
        """test getting the balance"""
        print('testing versions...')
        task = {'min_client_version_ios': '0.1', 'min_client_version_android': '0.1'}
        self.assertEqual(models.can_support_task("android", "0.4.1", task), True)

        task = {'min_client_version_ios': '0.1', 'min_client_version_android': '0.1'}
        self.assertEqual(models.can_support_task("ios", "0.4.1", task), True)

        task = {'min_client_version_ios': '1.1', 'min_client_version_android': '1.1'}
        self.assertEqual(models.can_support_task("android", "0.4.1", task), False)

        task = {'min_client_version_ios': '1.   1', 'min_client_version_android': '1.1'}
        self.assertEqual(models.can_support_task("ios", "0.4.1", task), False)

        task = {'min_client_version_ios': '1.1', 'min_client_version_android': '1.1'}
        self.assertEqual(models.can_support_task("android", "1.4.1", task), True)

        task = {'min_client_version_ios': '1.1', 'min_client_version_android': '1.1'}
        self.assertEqual(models.can_support_task("ios", "1.4.1", task), True)
        print('testing versions...done')



if __name__ == '__main__':
    unittest.main()
