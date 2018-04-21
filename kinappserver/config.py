# tester config file. should be overwritten by ansible in prod/stage.

DEPLOYMENT_ENV = 'test'
DEBUG = True
DB_CONNSTR = "this gets overwritten by the tester code. it acutally uses a temp postgress db on the local disc"
REDIS_ENDPOINT = 'localhost'
REDIS_PORT = 6379

STELLAR_TIMEOUT_SEC = 10  # waitloop for tx data to be available
STELLAR_INITIAL_ACCOUNT_BALANCE = 10

ESHU_USERNAME = ''
ESHU_PASSWORD = ''
ESHU_HEARTBEAT = ''
ESHU_APPID = ''
ESHU_VIRTUAL_HOST = ''
ESHU_EXCHANGE = ''
ESHU_QUEUE = ''
ESHU_RABBIT_ADDRESS = ''
GCM_TTL_SECS = 60*60

STELLAR_HORIZON_URL = 'https://horizon-testnet.stellar.org/'
STELLAR_NETWORK = 'TESTNET'
STELLAR_KIN_ISSUER_ADDRESS = 'GCKG5WGBIJP74UDNRIRDFGENNIH5Y3KBI5IHREFAJKV4MQXLELT7EX6V'

MAX_SIMULTANEOUS_ORDERS_PER_USER = 2
ORDER_EXPIRATION_SECS = 15
TASK_ALLOCATION_POLICY = 'default'

KMS_KEY_AWS_REGION = 'us-east-1'
