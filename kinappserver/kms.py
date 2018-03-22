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

    return base_seed, [] ##convert_byte_to_string_array(channel_seeds)

def convert_byte_to_string_array(input_byte):
    '''converts the input (a bytestring to a string array without using eval'''
    # this is used to convert the decrypted seed channels bytestring to an array
    #return json.loads('['+input_byte.decode("utf-8") +']')
    return json.loads('['+ input_byte +']')

def get_ssm_parameter(param_name, kms_key_region):
    '''retreives an encrpyetd value from AWSs ssm or None'''
    try:
        ssm_client = boto3.client('ssm', region_name=kms_key_region)
        print('getting param from ssm: %s' % param_name)
        res = ssm_client.get_parameter(Name=param_name, WithDecryption=True)
        return res['Parameter']['Value']
    except Exception as e:
        print('cant get secure value: %s from ssm' % param_name)
        print(e)
        return None
