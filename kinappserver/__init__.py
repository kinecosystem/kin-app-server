from flask import Flask
from flask_cors import CORS
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView

import redis
from kin import sdk as stellar_sdk

from kinappserver import amqp_publisher


app = Flask(__name__)
CORS(app)

from flask_sqlalchemy import SQLAlchemy
from kinappserver import config

app.kin_sdk = stellar_sdk.SDK(base_seed=config.STELLAR_BASE_SEED,
                              horizon_endpoint_uri=config.STELLAR_HORIZON_URL,
                              network=config.STELLAR_NETWORK,
                              channel_seeds=config.STELLAR_CHANNEL_SEEDS)

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
import requests

app.redis = redis.StrictRedis(host=config.REDIS_ENDPOINT, port=config.REDIS_PORT, db=0)
amqp_publisher.init_config(config.ESHU_RABBIT_ADDRESS, config.ESHU_QUEUE, config.ESHU_EXCHANGE, config.ESHU_VIRTUAL_HOST, config.ESHU_USERNAME, config.ESHU_PASSWORD, config.ESHU_HEARTBEAT, config.ESHU_APPID)
app.amqp_publisher = amqp_publisher

# sanity for configuration
if not config.DEBUG:
	# redis
	app.redis.setex('temp-key', 1, 'temp-value')
	
