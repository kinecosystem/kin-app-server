import base64
import json

from datadog import statsd
from flask import jsonify, config
from kinappserver import amqp_publisher, config
import boto3
import requests
from Crypto import Random
from Crypto.Cipher import AES

from kinappserver import config

ERROR_ORDERS_COOLDOWN = -1
ERROR_NO_GOODS = -2



def increment_metric(metric_name, count=1):
    '''increment a counter with the given name and value'''
    # set env to undefined for local tests (which do not emit stats, as there's no agent)
    statsd.increment('kinitapp.%s.%s' % (config.DEPLOYMENT_ENV, metric_name), count)


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

def convert_byte_to_string_array(input_byte):
    '''converts the input (a bytestring to a string array without using eval'''
    # this is used to convert the decrypted seed channels bytestring to an array
    return json.loads('['+input_byte.decode("utf-8") +']')


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


def decrypt_kms_key(cipher_text_blob, encrypted_private_key, kms_key_region):
    '''uses KMS to return the unencrypted key for the given encrypted key, blob and aws region'''
    if not (cipher_text_blob and encrypted_private_key and kms_key_region):
        print('cant decrypt key - bad input params')
        return None
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
