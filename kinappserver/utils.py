import base64

from flask import jsonify
from kinappserver import db
import boto3
import requests
#from Crypto import Random
#from Crypto.Cipher import AES

from kinappserver import config

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

def create_account(public_address):
    '''creates an account in the stellar network for the given public address.
       This function calls the onboarding service which may take a few seconds
       to return. Return True on success, False otherwise.
    '''
    #TODO find a way to mock this in tests
    if config.DEBUG:
        return True

    try:
        url = 'http://' + config.ONBOARDING_SERVICE_BASE_URL + '/create_account'
        requests.post(url,json={'public_address': public_address}, timeout=config.STELLAR_TIMEOUT_SEC).raise_for_status()
    except Exception as e:
        print('failed to create account (%s). exception: %s', public_address, e)
        return False
    else:
        return True

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
