import sys

from flask import Flask
from flask_cors import CORS
import kin

from kinappserver.amqp_publisher import AmqpPublisher
from stellar_base.network import NETWORKS
from .encrypt import AESCipher




app = Flask(__name__)
CORS(app)

from flask_sqlalchemy import SQLAlchemy
from kinappserver import config, ssm, stellar

# get seeds, channels from aws ssm:
base_seed, channel_seeds = ssm.get_stellar_credentials()
if not base_seed:
    print('could not get base seed - aborting')
    sys.exit(-1)

if channel_seeds is None:
    print('could not get channels seeds - aborting')
    sys.exit(-1)

# init sdk:
print('using kin-stellar sdk version: %s' % kin.version.__version__)
print("stellar horizon: %s" % config.STELLAR_HORIZON_URL)
# define an asset to forward to the SDK because sometimes we're using a custom issuer
from stellar_base.asset import Asset
kin_asset = Asset('KIN', config.STELLAR_KIN_ISSUER_ADDRESS)

if config.STELLAR_NETWORK != 'TESTNET':
    print('starting the sdk in a private network')
    network = 'CUSTOM'
    NETWORKS[network] = config.STELLAR_NETWORK
else:
    print('starting the sdk on the public testnet')
    network = config.STELLAR_NETWORK

app.kin_sdk = kin.SDK(secret_key=base_seed,
                      horizon_endpoint_uri=config.STELLAR_HORIZON_URL,
                      network=network,
                      channel_secret_keys=channel_seeds,
                      kin_asset=kin_asset)

# get (and print) the current balance for the account:
from stellar_base.keypair import Keypair
print('the current KIN balance on the base-seed: %s' % stellar.get_kin_balance(Keypair.from_seed(base_seed).address().decode()))
# get (and print) the current balance for the account:
print('the current XLM balance on the base-seed: %s' % stellar.get_xlm_balance(Keypair.from_seed(base_seed).address().decode()))

for channel in channel_seeds:
    address = Keypair.from_seed(channel).address().decode()
    print('the current XLM balance on channel (%s): %s' % (address, stellar.get_xlm_balance(address)))

# init encryption util
key, iv = ssm.get_encrpytion_creds()
app.encryption = AESCipher(key, iv)

# SQLAlchemy stuff:
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

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

if config.DEBUG:
    app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True
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
# redis config sanity
app.redis.setex('temp-key', 1, 'temp-value')

#push: init the amqplib: two instances, one for beta and one for release TODO get rid of this eventually
app.amqp_publisher_beta = AmqpPublisher()
app.amqp_publisher_release = AmqpPublisher()
if not app.amqp_publisher_beta.init_config('beta', config.ESHU_RABBIT_ADDRESS, config.ESHU_QUEUE, config.ESHU_EXCHANGE,
                                  config.ESHU_VIRTUAL_HOST, config.ESHU_USERNAME, config.ESHU_PASSWORD,
                                  config.ESHU_HEARTBEAT, config.ESHU_APPID, config.PUSH_TTL_SECS):
    print('could not init beta amqppublisher')
    sys.exit(-1)

if not app.amqp_publisher_release.init_config('release', config.ESHU_RABBIT_ADDRESS, config.ESHU_QUEUE, config.ESHU_EXCHANGE,
                                  config.ESHU_VIRTUAL_HOST, config.ESHU_USERNAME, config.ESHU_PASSWORD,
                                  config.ESHU_HEARTBEAT, config.ESHU_APPID, config.PUSH_TTL_SECS):
    print('could not init release amqppublisher')
    sys.exit(-1)

# init truex credentials
config.TRUEX_APP_ID, config.TRUEX_PARTNER_HASH, config.TRUEX_CALLBACK_SECRET = ssm.get_truex_creds()

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


# print db creation statements
if config.DEBUG:
    from .utils import print_creation_statement
    print_creation_statement()
