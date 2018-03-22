import base64, json

import boto3
from Crypto import Random
from Crypto.Cipher import AES

from kinappserver import config

def get_stellar_credentials():
    base_seed = get_ssm_parameter('/config/base-seed', config.KMS_KEY_AWS_REGION)
    channel_seeds = get_ssm_parameter('/config/channel-seeds', config.KMS_KEY_AWS_REGION)

    if base_seed is None:
        print('cant get base_seed, aborting')
        return None, None

    if not channel_seeds:
        return base_seed, []

    return base_seed, convert_byte_to_string_array(channel_seeds)

def get_stellar_credentials_old():

    # use ssm to get encrypted base seed:


    # get the base seed: either directly from config or decrypt using kms
    base_seed = config.STELLAR_BASE_SEED
    if not base_seed:
        print('decrypting base seed')
        print('base seed cipher: %s' % config.STELLAR_BASE_SEED_CIPHER_TEXT_BLOB)
        print('encrypted base seed: %s' % config.ENCRYPTED_STELLAR_BASE_SEED)

        base_seed = decrypt_kms_key(config.STELLAR_BASE_SEED_CIPHER_TEXT_BLOB, config.ENCRYPTED_STELLAR_BASE_SEED, config.KMS_KEY_AWS_REGION)

    # get the channel seeds: either directly from config or decrypt using kms
    # channels are a good idea, but they are optional
    channel_seeds = config.STELLAR_CHANNEL_SEEDS
    if not channel_seeds:
        if config.ENCRYPTED_STELLAR_CHANNEL_SEEDS and config.STELLAR_CHANNEL_SEEDS_CIPHER_TEXT_BLOB:
           print('decrypting channel seeds')
           channel_seeds = convert_byte_to_string_array(decrypt_kms_key(config.STELLAR_CHANNEL_SEEDS_CIPHER_TEXT_BLOB, config.ENCRYPTED_STELLAR_CHANNEL_SEEDS, config.KMS_KEY_AWS_REGION))
        elif not (config.ENCRYPTED_STELLAR_CHANNEL_SEEDS and config.STELLAR_CHANNEL_SEEDS_CIPHER_TEXT_BLOB):
            print('no channels provided. continuing w/o them.')
            channel_seeds = []
        else:
            channel_seeds = None

    return base_seed, channel_seeds

def convert_byte_to_string_array(input_byte):
    '''converts the input (a bytestring to a string array without using eval'''
    # this is used to convert the decrypted seed channels bytestring to an array
    return json.loads('['+input_byte.decode("utf-8") +']')


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

def get_ssm_parameter(param_name, kms_key_region):
    '''retreives an encrpyetd value from AWSs ssm or None'''
    try:
        ssm_client = boto3.client('ssm', region_name=kms_key_region)
        res = ssm_client.get_parameter(Name=param_name, WithDecryption=True)
        print(res)
        return res['Parameter']['Value']
    except Exception as e:
        print('cant get secure value: %s from ssm' % param_name)
        print(e)
        return None
