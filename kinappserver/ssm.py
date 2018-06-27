import json
import os

import boto3

from kinappserver import config
from kinappserver.utils import InternalError


def get_truex_creds():
    env = os.environ.get('ENV', 'test')
    partner_hash = get_ssm_parameter('/config/' + env + '/truex/partner_hash', config.KMS_KEY_AWS_REGION)
    callback_secret = get_ssm_parameter('/config/' + env + '/truex/callback_secret', config.KMS_KEY_AWS_REGION)
    app_id = get_ssm_parameter('/config/' + env + '/truex/app_id', config.KMS_KEY_AWS_REGION)
    if None in (app_id, partner_hash, callback_secret):
        print('cant get truex creds')
        raise InternalError('cant get truex creds')

    return app_id, partner_hash, callback_secret


def get_stellar_credentials():
    # get credentials from ssm. the base_seed is required, the channel-seeds are optional
    env = os.environ.get('ENV', 'test')
    base_seed = get_ssm_parameter('/config/' + env + '/stellar/base-seed', config.KMS_KEY_AWS_REGION)
    channel_seeds = get_ssm_parameter('/config/' + env + '/stellar/channel-seeds', config.KMS_KEY_AWS_REGION)

    if base_seed is None:
        print('cant get base_seed, aborting')
        return None, None

    if not channel_seeds:
        return base_seed, []

    return base_seed, convert_string_to_string_array(channel_seeds)


def write_service_account():
    """"creates a service-account file if one does not exist already"""
    import os
    if os.path.exists(config.FIREBASE_SERVICE_ACCOUNT_FILE):
        return config.FIREBASE_SERVICE_ACCOUNT_FILE
    else:
        env = os.environ.get('ENV', 'test')
        service_account_json = get_ssm_parameter('/config/' + env + '/firebase/service-account', config.KMS_KEY_AWS_REGION)

        # travis is a special case - has a unique path:
        is_travis = os.environ.get('TRAVIS', 0)
        path = config.FIREBASE_SERVICE_ACCOUNT_FILE if not is_travis else '/home/travis/build/kinecosystem/kin-app-server/kinappserver/service-account.json'
        with open(path, 'w+') as the_file:
            the_file.write(service_account_json)
        return path


def convert_string_to_string_array(input):
    """converts the input from ssm to a python string array

    used for the channel seeds, which sign txs
    """

    # to add new channels, use this aws command (just plug in the secret keys and kms key
    #  aws ssm put-parameter --name /config/prod/stellar/channel-seeds --value "\"secret_key1\",\"secret_key2\",\"secret_key3\",\"secret_key4\",\"secret_key5\",\"secret_key6\"" --type SecureString --key-id <kms arn> --overwrite

    # this is used to convert the decrypted seed channels string to an array
    return json.loads('[' + str(input) + ']')


def get_ssm_parameter(param_name, kms_key_region):
    """retreives an encrpyetd value from AWSs ssm or None"""
    try:
        ssm_client = boto3.client('ssm', region_name=kms_key_region)
        print('getting param from ssm: %s' % param_name)
        res = ssm_client.get_parameter(Name=param_name, WithDecryption=True)
        return res['Parameter']['Value']
    except Exception as e:
        print('cant get secure value: %s from ssm' % param_name)
        print(e)
        return None


def get_security_password():
    """returns the kinit security password from ssm"""
    env = os.environ.get('ENV', 'test')
    password =  get_ssm_parameter('/config/' + env + '/misc/password', config.KMS_KEY_AWS_REGION)
    return password