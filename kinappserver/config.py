# tester config file. should be overwritten by ansible in prod/stage.

DEPLOYMENT_ENV = 'test'
DEBUG = True
DB_CONNSTR = "postgresql://localhost:5432/kinit_localhost"
REDIS_ENDPOINT = 'localhost'
REDIS_PORT = 6379

STELLAR_TIMEOUT_SEC = 10  # waitloop for tx data to be available
STELLAR_INITIAL_ACCOUNT_BALANCE = 0

ESHU_USERNAME = ''
ESHU_PASSWORD = ''
ESHU_HEARTBEAT = ''
ESHU_APPID = ''
ESHU_VIRTUAL_HOST = ''
ESHU_EXCHANGE = ''
ESHU_QUEUE = ''
ESHU_RABBIT_ADDRESS = ''
PUSH_TTL_SECS = 60 * 60 * 24

STELLAR_HORIZON_URL = 'https://horizon-testnet.kininfrastructure.com'
STELLAR_NETWORK = 'Kin Testnet ; December 2018'
STELLAR_KIN_ISSUER_ADDRESS = 'GBC3SG6NGTSZ2OMH3FFGB7UVRQWILW367U4GSOOF4TFSZONV42UJXUH7'

MAX_SIMULTANEOUS_ORDERS_PER_USER = 2
ORDER_EXPIRATION_SECS = 15

KMS_KEY_AWS_REGION = 'us-east-1'

PHONE_VERIFICATION_REQUIRED = False
PHONE_VERIFICATION_ENABLED = True

P2P_TRANSFERS_ENABLED = True # leave this on for tests
P2P_MIN_TASKS = 1
P2P_MIN_KIN_AMOUNT = 300
P2P_MAX_KIN_AMOUNT = 12500

TOS_URL = 'http://www.kinitapp.com/terms-and-privacy-policy'
FAQ_URL = 'https://cdn.kinitapp.com/faq2/index.html'
FIREBASE_SERVICE_ACCOUNT_FILE = '/opt/kin-app-server/service-account.json'


AUTH_TOKEN_SEND_INTERVAL_DAYS = 1
AUTH_TOKEN_ENFORCED = True
AUTH_TOKEN_ENABLED = True

#BLACKHAWK
BLACKHAWK_PURCHASES_ENABLED = True
BLACKHAWK_CRITICAL_BALANCE_THRESHOLD = 10

#TRUEX
TRUEX_APP_ID = ''
TRUEX_PARTNER_HASH = ''
TRUEX_CALLBACK_SECRET = ''

PAYMENT_SERVICE_URL = 'https://kin3stage.payments.kinitapp.com:4998'
API_SERVER_URL = 'https://stage.kinitapp.com'

BLOCK_ONBOARDING_IOS_VERSION = '0.1'
BLOCK_ONBOARDING_ANDROID_VERSION = '0.1'


BLOCKED_PHONE_PREFIXES = "[]"
ALLOWED_PHONE_PREFIXES = "[]"
BLOCKED_COUNTRY_CODES = "[]"

TRUEX_BLACKLISTED_TASKIDS = '[]'

MAX_NUM_REGISTRATIONS_PER_NUMBER = 2  # keep this value at 2 for the test
APK_PACKAGE_NAME = 'org.kinecosystem.kinit'
CAPTCHA_STALE_THRESHOLD_SECS = 60
CAPTCHA_MIN_CLIENT_VERSION_ANDROID = '1.2.6'
CAPTCHA_MIN_CLIENT_VERSION_IOS = '99.99'
CAPTCHA_SAFETY_COOLDOWN_SECS = 60*60*1
CAPTCHA_TASK_MODULO = 4
CAPTCHA_AUTO_RAISE = True

SERVERSIDE_CLIENT_VALIDATION_ENABLED = False

OFFER_PER_TIME_RANGE = 1
OFFER_LIMIT_TIME_RANGE = 30  #days
OFFER_RATE_LIMIT_MIN_IOS_VERSION = '1.2.1'
OFFER_RATE_LIMIT_MIN_ANDROID_VERSION = '1.4.1'

USER_LOCKED_OFFERS_REDIS_KEY = 'REDIS_USER_BLOCKED_OFFERS_LIST_%s'
ZENDESK_API_TOKEN = "this gets overwritten by the tester code. it acutally uses a temp postgress db on the local disc"

MIGRATION_SERVICE_URL = "http://localhost:8080/migrate"
MIGRATION_STATUS_URL = "http://localhost:8080/status"
