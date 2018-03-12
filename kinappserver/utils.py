import base64

from flask import jsonify
from kinappserver import db, amqp_publisher, config
import boto3
import requests
#from Crypto import Random
#from Crypto.Cipher import AES

from kinappserver import config

ERROR_ORDERS_COOLDOWN = -1
ERROR_NO_GOODS = -2


def errors_to_string(errorcode):
    '''translate error codes to human-readable reasons'''
    if errorcode == ERROR_ORDERS_COOLDOWN:
        return 'orders-cooldown'
    elif errorcode == ERROR_NO_GOODS:
        return 'no-goods'
    else:
        print('should never happen')
        return 'unknown-error'

def seconds_to_utc_midnight():
    '''returs the (integer) number of seconds to the next midnight at utc'''
    from datetime import datetime, timedelta, timezone

    tomorrow = datetime.date(datetime.today() + timedelta(days=1))
    # convert date objevt to datetime. hack from https://stackoverflow.com/a/27760382/1277048
    tomorrow_dt = datetime.strptime(tomorrow.strftime('%Y%m%d'), '%Y%m%d')
    # calc hours until tomorrow
    return(int((tomorrow_dt - datetime.utcnow()).total_seconds()))


class InvalidUsage(Exception):
    status_code = 400

    def __init__(self, message, status_code=None, payload=None):
        Exception.__init__(self)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv['message'] = self.message
        return rv

class InternalError(Exception):
    status_code = 500

    def __init__(self, message, status_code=None, payload=None):
        Exception.__init__(self)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv['message'] = self.message
        return rv

def send_gcm(token, payload):
    payload_dict = {}
    payload_dict['message'] = payload
    amqp_publisher.send_gcm("eshu-key", payload_dict, [token], False, config.GCM_TTL_SECS)


def send_apns(token, payload):
    #TODO 
    pass

'''
def get_private_key(config):
    # return the private key or None. If a private key was given in the config, return that.
    # Otherwise, try to decrypt the private key using KMS.

    if config.PRIVATE_KEY:
        return config.PRIVATE_KEY
    else: # try to get the key from KMS
        if not (config.KMS_KEY_AWS_REGION and config.CIPHER_TEXT_BLOB and config.ENCRYPTED_PRIVATE_KEY):
            return None
        # decrypt the key:
        return decrypt_key(config.KMS_KEY_AWS_REGION, config.CIPHER_TEXT_BLOB, config.ENCRYPTED_PRIVATE_KEY)
    return None

def decrypt_key(kms_key_region, cipher_text_blob, encrypted_private_key):
    try:
        kms_client = boto3.client('kms', region_name=kms_key_region)

        # convert the encrypted KMS key to plaintext KMS key
        decrypted_kms_key = kms_client.decrypt(CiphertextBlob=base64.b64decode(cipher_text_blob)).get('Plaintext')

        # un-base64 the encrypted data, seperate the iv from the message
        enc = base64.b64decode(encrypted_private_key)
        iv = enc[:AES.block_size]

        # decrypt the message using the plaintext key and the iv
        cypher = AES.new(decrypted_kms_key, AES.MODE_CBC, iv)
        return cypher.decrypt(enc[AES.block_size:]).rstrip()
    except Exception as e:
        print('failed to extract key from kms: %s' % e)
        return None
'''
