from time import sleep
import unittest
import uuid

import simplejson as json
import testing.postgresql
import logging as log

import kinappserver
from kinappserver import db, models

import logging as log
log.getLogger().setLevel(log.INFO)


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

        for cat_id in range(2):
            cat = {'id': str(cat_id),
                   'title': 'cat-title',
                   "skip_image_test": True,
                   'ui_data': {'color': "#123",
                               'image_url': 'https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png',
                               'header_image_url': 'https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png'}}

            resp = self.app.post('/category/add',
                                 data=json.dumps({
                                     'category': cat}),
                                 headers={},
                                 content_type='application/json')
            self.assertEqual(resp.status_code, 200)

        # add task table
        db.engine.execute("""CREATE TABLE task ( 
            task_id VARCHAR(40) NOT NULL,
            task_type VARCHAR(40) NOT NULL,
            title VARCHAR(80) NOT NULL,
            "desc" VARCHAR(200) NOT NULL,
            price INTEGER NOT NULL,
            video_url VARCHAR(100),
            min_to_complete FLOAT NOT NULL,
            provider_data JSON,
            tags JSON,
            items JSON,
            start_date TIMESTAMP WITHOUT TIME ZONE,
            update_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
            delay_days INTEGER NOT NULL,
            min_client_version_android VARCHAR(80) NOT NULL,
            min_client_version_ios VARCHAR(80) NOT NULL,
            post_task_actions JSON,
            PRIMARY KEY (task_id, task_type)
        );""")


        # populate task table
        task_template = """insert into task (task_id, task_type, title, "desc", price, video_url, min_to_complete, provider_data, tags, items, start_date, update_at, delay_days, min_client_version_android, min_client_version_ios, post_task_actions) values ('0', 'task_type', 'task_title', 'task_desc', 1, 'http://google.com', 1, %s, %s, %s, null, null, 5, '1.0','2.0', %s);"""


        d = {'a':1, 'b':2}
        db.engine.execute(task_template, json.dumps(d), json.dumps(d), json.dumps(d), json.dumps(d))
        # migrate task to task2

        models.task20_migrate_task('0', '0', 0, 3)

        print(models.get_task_by_id('0'))




if __name__ == '__main__':
    unittest.main()
