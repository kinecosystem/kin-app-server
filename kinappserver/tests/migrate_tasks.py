from time import sleep
import unittest
import uuid

import simplejson as json
import testing.postgresql
import logging as log

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

    def test_task_migration(self):
        """test migrating tasks from task1 to task2"""

        # add task table
        db.engine.execute("""add table task""";

        # populate task table

        # migrate task to task2




if __name__ == '__main__':
    unittest.main()
