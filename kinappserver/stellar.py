from kinappserver import app, config
from kinappserver.utils import InvalidUsage, increment_metric
from time import sleep
import kin
import requests
import random
import logging as log
ASSET_NAME = 'KIN'


def create_account(public_address, initial_xlm_amount):
    """create an account for the given public address"""
    #TODO all repeating logic?
    print('creating account with balance:%s' % initial_xlm_amount)
    try:
        return app.kin_sdk.create_account(public_address, starting_balance=initial_xlm_amount)
    except Exception as e:
        increment_metric('create_account_error')
        print('caught exception creating account for address %s' % (public_address))
        print(e)


def send_kin(public_address, amount, memo=None):
    """send kins to an address"""

    #  sanity:
    if public_address in (None, ''):
        log.error('cant send kin to address: %s' % public_address)
        return False, None

    if amount is None or amount < 1:
        log.error('cant send kin amount: %s' % amount)
        return False, None

    print('sending kin to address: %s' % public_address) #TODO REMOVE
    from stellar_base.asset import Asset
    try:
        kin_asset = Asset(ASSET_NAME, config.STELLAR_KIN_ISSUER_ADDRESS)
        return app.kin_sdk._send_asset(kin_asset, public_address, amount, memo)
    except Exception as e:
        increment_metric('send_kin_error')
        print('caught exception sending %s kin to address %s' % (amount, public_address))
        print(e)


def send_kin_with_payment_service(public_address, amount, memo=None):
    """send kins to an address using the payment service"""

    #  sanity:
    if public_address in (None, ''):
        log.error('cant send kin to address: %s' % public_address)
        return False, None

    if amount is None or amount < 1:
        log.error('cant send kin amount: %s' % amount)
        return False, None

    print('sending kin to address: %s' % public_address)
    headers = {'X-REQUEST-ID': str(random.randint(1, 1000000))}  # doesn't actually matter
    payment_payload = {
        'id': memo,
        'amount': amount,
        'app_id': 'kit',
        'recipient_address': public_address,
        'callback': "%s/payments/callback" % config.API_SERVER_URL
    }

    try:
        res = requests.post('%s/payments' % config.PAYMENT_SERVICE_URL, headers=headers, json=payment_payload)
        res.raise_for_status()
    except Exception as e:
        increment_metric('send_kin_error')
        print('caught exception sending %s kin to address %s using the payment service' % (amount, public_address))
        print(e)


def extract_tx_payment_data(tx_hash):
    """ensures that the given tx_hash is a valid payment tx,
       and return a dict with the memo, amount and to_address"""
    if tx_hash is None:
        raise InvalidUsage('invlid params')

    # get the tx_hash data. this might take a second,
    # so retry while 'Resource Missing' is recevied
    count = 0
    tx_data = None
    while (count < config.STELLAR_TIMEOUT_SEC):
        try:
            tx_data = app.kin_sdk.get_transaction_data(tx_hash)

        except kin.ResourceNotFoundError as e:
            count = count + 1
            sleep(1)
        else:
            break


    if tx_data is None:
        print('could not get tx_data for tx_hash: %s. waited %s seconds' % (tx_hash, count))
        increment_metric('tx_data_timeout')
        return False, {}

    if len(tx_data.operations) != 1:
        print('too many ops')
        return False, {}

    # get the first (and only) op:
    op = tx_data.operations[0]

    # verify op type
    if op['type'] != 'payment':
        print('unexpected type: %s' % op['type'])
        return False, {}

    # verify asset params
    if op['asset_code'] != ASSET_NAME and op['asset_issuer'] != \
            config.STELLAR_KIN_ISSUER_ADDRESS and op['asset_type'] != 'credit_alphanum4':
        print('unexpected asset-code/issuer/asset_type')
        return False, {}

    # verify memo type
    if tx_data['memo_type'] != 'text':
        print('unexpected memo type')
        return False, {}

    # assemble the result dict
    data = {}
    data['memo'] = tx_data.get('memo', None)
    data['amount'] = op.get('amount', None)
    data['to_address'] = op.get('to_address', None)
    return True, data


def get_kin_balance(public_address):
    """returns the current kin balance for this account"""
    try:
        from stellar_base.asset import Asset
        kin_asset = Asset(ASSET_NAME, config.STELLAR_KIN_ISSUER_ADDRESS)
        return app.kin_sdk._get_account_asset_balance(public_address, kin_asset)
    except Exception as e:
        print(e)
        print('could not get kin balance for address: %s' % public_address)
        return None


def get_xlm_balance(public_address):
    """returns the current xl, balance for this account"""
    try:
        return app.kin_sdk.get_account_native_balance(public_address)
    except Exception as e:
        print(e)
        print('could not get xlm balance for address: %s' % public_address)
        return None
