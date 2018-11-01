import simplejson as json
import testing.postgresql
import unittest
import kinappserver
import redis as rds
import base64
import validation_module
from uuid import uuid4, UUID
from time import sleep
from kinappserver import db, stellar, models, config


redis = rds.StrictRedis(host=config.REDIS_ENDPOINT,
                        port=config.REDIS_PORT, db=0)

USER_ID_HEADER = "X-USERID"
AUTH_TOKEN = "X-AUTH-TOKEN"
VALIDATION_VALID_TOKEN = ""
NONCE = ""
NONCE_REDIS_KEY = 'validation_nonce-%s'
NONCE_REDIS_TIMEOUT = 60


class Tester(unittest.TestCase):
    """tests the entire spend-scenario: creating an order and then redeeming it"""

    @classmethod
    def setUpClass(cls):
        pass

    def setUp(self):
        # overwrite the db name, dont interfere with stage db data
        self.postgresql = testing.postgresql.Postgresql()
        kinappserver.app.config[
            'SQLALCHEMY_DATABASE_URI'] = self.postgresql.url()
        kinappserver.app.testing = True
        self.app = kinappserver.app.test_client()
        db.drop_all()
        db.create_all()

    def tearDown(self):
        self.postgresql.stop()

    def test_get_nonce(self):
        """test nonce creation"""

        # Create test user
        userid = str(uuid4())
        # get a nonce for the user
        headers = {USER_ID_HEADER: userid}

        resp = self.app.get('/validation/get-nonce', headers=headers)
        self.assertEqual(resp.status_code, 200)

        data = json.loads(resp.data)
        print('responds: %s' % data)
        self.assertIsNot(data['nonce'], "")


if __name__ == '__main__':
    unittest.main()
