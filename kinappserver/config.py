# tester config file. should be overwritten by ansible in prod/stage.

DEPLOYMENT_ENV = 'test'
DEBUG = True
DB_CONNSTR = "this gets overwritten by the tester code. it acutally uses a temp postgress db on the local disc"
REDIS_ENDPOINT = 'localhost'
REDIS_PORT = 6379

STELLAR_TIMEOUT_SEC = 10 # waitloop for tx data to be available
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

STELLAR_BASE_SEED = 'SDEMLLRTVT3AORRSHKAIRYOMW6UE2GKNUYMAVRLZ3EDML4JTADF4BEBO'
STELLAR_HORIZON_URL = 'https://horizon-testnet.stellar.org/'
STELLAR_NETWORK = 'TESTNET'
STELLAR_CHANNEL_SEEDS = ['SB7FTL22P4LCTNRI43EOLXTLPGNQ6OX6FQZ6A5P6T4S7YYX5YVFNQTRG']
STELLAR_KIN_ISSUER_ADDRESS = 'GCKG5WGBIJP74UDNRIRDFGENNIH5Y3KBI5IHREFAJKV4MQXLELT7EX6V'
STELLAR_PUBLIC_ADDRESS = 'GC3VEVNMPOIFIQOKUYFROWR6LWQQM57OQSWLLD6TGDIPOA5S6UXQWHVL'

MAX_SIMULTANEOUS_ORDERS_PER_USER = 2
ORDER_EXPIRATION_SECS = 15
TASK_ALLOCATION_POLICY = 'default'

KMS_KEY_AWS_REGION = 'us-east-1'
STELLAR_BASE_SEED_CIPHER_TEXT_BLOB = 'something'
ENCRYPTED_STELLAR_BASE_SEED = 'some_other_thing'
STELLAR_CHANNEL_SEEDS_CIPHER_TEXT_BLOB = 'something'
ENCRYPTED_STELLAR_CHANNEL_SEEDS = ['some_other_thing']
