import sys

from flask import Flask
from flask_cors import CORS
import kin

from kinappserver import amqp_publisher


app = Flask(__name__)
CORS(app)

from flask_sqlalchemy import SQLAlchemy
from kinappserver import config, ssm, stellar

base_seed, channel_seeds = ssm.get_stellar_credentials()
if not base_seed:
    print('could not get base seed - aborting')
    sys.exit(-1)

if channel_seeds is None:
    print('could not get channels seeds - aborting')
    sys.exit(-1)

print('using kin-stellar sdk version: %s' % kin.version.__version__)

app.kin_sdk = kin.SDK(secret_key=base_seed,
                      horizon_endpoint_uri=config.STELLAR_HORIZON_URL,
                      network=config.STELLAR_NETWORK,
                      channel_secret_keys=channel_seeds)


# get (and print) the current balance for the account:
from stellar_base.keypair import Keypair
print('the current KIN balance on the base-seed: %s' % stellar.get_kin_balance(Keypair.from_seed(base_seed).address().decode()))
# get (and print) the current balance for the account:
print('the current XLM balance on the base-seed: %s' % stellar.get_xlm_balance(Keypair.from_seed(base_seed).address().decode()))


for channel in channel_seeds:
    print('the current XLM balance on channel (%s): %s' % (channel, stellar.get_xlm_balance(Keypair.from_seed(channel).address().decode())))

# create an sqlalchemy engine with "autocommit" to tell sqlalchemy NOT to use un-needed transactions.
# see this: http://oddbird.net/2014/06/14/sqlalchemy-postgres-autocommit/
# and this: https://github.com/mitsuhiko/flask-sqlalchemy/pull/67
class MySQLAlchemy(SQLAlchemy):
    def apply_driver_hacks(self, app, info, options):
        options['isolation_level'] = 'AUTOCOMMIT'
        super(MySQLAlchemy, self).apply_driver_hacks(app, info, options)

app.config['SQLALCHEMY_DATABASE_URI'] = config.DB_CONNSTR

# SQLAlchemy timeouts
app.config['SQLALCHEMY_POOL_SIZE'] = 1000
app.config['SQLALCHEMY_POOL_TIMEOUT'] = 5
app.config['SQLALCHEMY_MAX_OVERFLOW'] = 100
app.config['SQLALCHEMY_POOL_RECYCLE'] = 60*5

if config.DEBUG:
    # run a tight boat on stage to detect leaks
    app.config['SQLALCHEMY_POOL_SIZE'] = 1000
    app.config['SQLALCHEMY_MAX_OVERFLOW'] = 100


app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = False

if config.DEPLOYMENT_ENV in ['prod', 'stage']:
    print('starting sqlalchemy in autocommit mode')
    db = MySQLAlchemy(app)
else:
    db = SQLAlchemy(app)

#SQLAlchemy logging
#import logging
#logging.basicConfig()
#logging.getLogger('sqlalchemy').setLevel(logging.DEBUG)
#logging.getLogger('sqlalchemy.engine').setLevel(logging.DEBUG)
#logging.getLogger('sqlalchemy.pool').setLevel(logging.DEBUG)

import kinappserver.views
import redis

#redis:
app.redis = redis.StrictRedis(host=config.REDIS_ENDPOINT, port=config.REDIS_PORT, db=0)

#push: init the amqplib: two instances, one for beta and one for prod
amqp_publisher.init_config(config.ESHU_RABBIT_ADDRESS, config.ESHU_QUEUE, config.ESHU_EXCHANGE, config.ESHU_VIRTUAL_HOST, config.ESHU_USERNAME, config.ESHU_PASSWORD, config.ESHU_HEARTBEAT, config.ESHU_APPID_BETA, config.PUSH_TTL_SECS)
app.amqp_publisher_beta = amqp_publisher

amqp_publisher.init_config(config.ESHU_RABBIT_ADDRESS, config.ESHU_QUEUE, config.ESHU_EXCHANGE, config.ESHU_VIRTUAL_HOST, config.ESHU_USERNAME, config.ESHU_PASSWORD, config.ESHU_HEARTBEAT, config.ESHU_APPID_PROD, config.PUSH_TTL_SECS)
app.amqp_publisher_prod = amqp_publisher

# sanity for configuration
if not config.DEBUG:
    app.redis.setex('temp-key', 1, 'temp-value')

config.TRUEX_PARTNER_HASH = ssm.get_truex_hash()

# useful prints:
state = 'enabled' if config.PHONE_VERIFICATION_ENABLED else 'disabled'
print('phone verification: %s' % state)
state = 'enabled' if config.AUTH_TOKEN_ENABLED else 'disabled'
print('auth token enabled: %s' % state)
state = 'enabled' if config.AUTH_TOKEN_ENFORCED else 'disabled'
print('auth token enforced: %s' % state)
state = 'enabled' if config.P2P_TRANSFERS_ENABLED else 'disabled'
print('p2p transfers: %s' % state)
print('replenish blackhawk cards enabled: %s' % config.BLACKHAWK_PURCHASES_ENABLED)


# get the firebase service-account from ssm
service_account_file_path = ssm.write_service_account()

# init the firebase admin stuff
import firebase_admin
from firebase_admin import credentials
cred = credentials.Certificate(service_account_file_path)
firebase_admin.initialize_app(cred)
app.firebase_admin = firebase_admin


# uncomment to print db creation statements
#from .utils import print_creation_statement
#print_creation_statement()
