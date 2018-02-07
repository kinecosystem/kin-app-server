from flask import Flask
from flask_cors import CORS
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView

import redis

app = Flask(__name__)
CORS(app)

from flask_sqlalchemy import SQLAlchemy
from kinappserver import config

app.config['SQLALCHEMY_DATABASE_URI'] = config.DB_CONNSTR
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# TODO remove this on production
admin = Admin(app, name='KinApp', template_mode='bootstrap3')
from kinappserver.model import User, UserAppData, UserTaskResults, Task
admin.add_view(ModelView(User, db.session))
admin.add_view(ModelView(UserAppData, db.session))
admin.add_view(ModelView(UserTaskResults, db.session))
admin.add_view(ModelView(Task, db.session))

import kinappserver.views
import time
import redis_lock, redis
import sys
from threading import Lock

app.redis = redis.StrictRedis(host=config.REDIS_ENDPOINT, port=config.REDIS_PORT, db=0)

# sanity for configuration
if not config.DEBUG:
	# redis
	app.redis.setex('temp-key','temp-value',time=1)
	
	# onboarding service:
	if not config.ONBOARDING_SERVICE_BASE_URL:
		raise Exception('no ONBOARDING_SERVICE_BASE_URL configured. aborting')
	response = requests.get(config.ONBOARDING_SERVICE_BASE_URL + '/status')
	if (json.loads(response.data)['status']) != 'healthy':
		raise Exception('onboarding service is not healthy. aborting')


