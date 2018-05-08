import sys

from flask import Flask
from flask_cors import CORS
import kin

from kinappserver import amqp_publisher


app = Flask(__name__)
CORS(app)

from flask_sqlalchemy import SQLAlchemy
from kinappserver import config, ssm, stellar

base_seed, channel_seed = ssm.get_stellar_credentials()
if not base_seed:
    print('could not get base seed - aborting')
    sys.exit(-1)

if channel_seed is None:
    print('could not get channels seeds - aborting')
    sys.exit(-1)

# TODO REMOVE LATER
# disable channel seed
#app.kin_sdk = kin.SDK(secret_key=base_seed,
#                              horizon_endpoint_uri=config.STELLAR_HORIZON_URL,
#                              network=config.STELLAR_NETWORK,
#                              channel_secret_keys=channel_seeds)

app.kin_sdk = kin.SDK(secret_key=base_seed,
                              horizon_endpoint_uri=config.STELLAR_HORIZON_URL,
                              network=config.STELLAR_NETWORK)

# get (and print) the current balance for the account:
from stellar_base.keypair import Keypair
print('the current KIN balance on the base-seed: %s' % stellar.get_kin_balance(Keypair.from_seed(base_seed).address().decode()))
# get (and print) the current balance for the account:
print('the current XLM balance on the base-seed: %s' % stellar.get_xlm_balance(Keypair.from_seed(base_seed).address().decode()))

if channel_seed:
    print('the current KIN balance on the channel: %s' % stellar.get_kin_balance(Keypair.from_seed(channel_seed).address().decode()))
    # get (and print) the current balance for the account:
    print('the current XLM balance on the channel: %s' % stellar.get_xlm_balance(Keypair.from_seed(channel_seed).address().decode()))



# SQLAlchemy timeouts
app.config['SQLALCHEMY_POOL_SIZE'] = 100
app.config['SQLALCHEMY_POOL_TIMEOUT'] = 5
app.config['SQLALCHEMY_MAX_OVERFLOW'] = 100
app.config['SQLALCHEMY_POOL_RECYCLE'] = 60*5

if config.DEBUG:
    # run a tight boat on stage to detect leaks
    app.config['SQLALCHEMY_POOL_SIZE'] = 5
    app.config['SQLALCHEMY_MAX_OVERFLOW'] = 0

app.config['SQLALCHEMY_DATABASE_URI'] = config.DB_CONNSTR
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = False
db = SQLAlchemy(app)

#SQLAlchemy logging
#import logging
#logging.basicConfig()
#logging.getLogger('sqlalchemy').setLevel(logging.DEBUG)
#logging.getLogger('sqlalchemy.engine').setLevel(logging.DEBUG)
#logging.getLogger('sqlalchemy.pool').setLevel(logging.DEBUG)

import kinappserver.views
import redis

app.redis = redis.StrictRedis(host=config.REDIS_ENDPOINT, port=config.REDIS_PORT, db=0)
amqp_publisher.init_config(config.ESHU_RABBIT_ADDRESS, config.ESHU_QUEUE, config.ESHU_EXCHANGE, config.ESHU_VIRTUAL_HOST, config.ESHU_USERNAME, config.ESHU_PASSWORD, config.ESHU_HEARTBEAT, config.ESHU_APPID)
app.amqp_publisher = amqp_publisher

# sanity for configuration
if not config.DEBUG:
    app.redis.setex('temp-key', 1, 'temp-value')

# useful prints:
state = 'enabled' if config.PHONE_VERIFICATION_ENABLED else 'disabled'
print('phone verification: %s' % state)
state = 'enabled' if config.AUTHENTICATION_TOKEN_ENABLED else 'disabled'
print('authentication token: %s' % state)
state = 'enabled' if config.P2P_TRANSFERS_ENABLED else 'disabled'
print('p2p transfers: %s' % state)

# get the firebase service-account from ssm
service_account_file_path = ssm.write_service_account()

# init the firebase admin stuff
import firebase_admin
from firebase_admin import credentials
cred = credentials.Certificate(service_account_file_path)
firebase_admin.initialize_app(cred)
app.firebase_admin = firebase_admin