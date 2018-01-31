from flask import Flask
from flask_cors import CORS
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView

app = Flask(__name__)
CORS(app)

from flask_sqlalchemy import SQLAlchemy
from kinappserver import config

app.config['SQLALCHEMY_DATABASE_URI'] = config.DB_CONNSTR
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# TODO remove this on production
admin = Admin(app, name='KipApp', template_mode='bootstrap3')
from kinappserver.model import User
admin.add_view(ModelView(User, db.session))

import kinappserver.views
import time
import redis_lock, redis
import sys
from threading import Lock

app.redis = redis.StrictRedis(host=config.REDIS_ENDPOINT, port=config.REDIS_PORT, db=0)
