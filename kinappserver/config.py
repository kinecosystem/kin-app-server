# tester config file. should be overwritten by ansible in prod/stage.

DEBUG = True
DB_CONNSTR = "this gets overwritten by the tester code. it acutally uses a temp postgress db on the local disc"
REDIS_ENDPOINT = 'localhost'
REDIS_PORT = 6379

ONBOARDING_SERVICE_BASE_URL = 'fake-address.com'
STELLAR_TIMEOUT_SEC = 10 

ESHU_USERNAME = ''
ESHU_PASSWORD = ''
ESHU_HEARTBEAT = ''
ESHU_APPID = ''
ESHU_VIRTUAL_HOST = ''
ESHU_EXCHANGE = ''
ESHU_QUEUE = ''
ESHU_RABBIT_ADDRESS = ''

STELLAR_BASE_SEED = ''
STELLAR_HORIZON_URL = ''
STELLAR_NETWORK = ''
STELLAR_CHANNEL_SEEDS = ''
