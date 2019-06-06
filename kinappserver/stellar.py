from kinappserver import app, config
from kinappserver.utils import InvalidUsage, increment_metric
from time import sleep
import kin
import requests
import random
import json
import logging as log
ASSET_NAME = 'KIN'


def create_account(public_address, initial_kin_amount):
    """create an account for the given public address"""
    print('creating account with balance:%s' % initial_kin_amount)
    try:
        return app.kin_account.create_account(public_address, starting_balance=initial_kin_amount, fee=0)
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

    print('sending kin to address: %s' % public_address)
    try:
        return app.kin_account.send_kin(public_address, amount, fee=0, memo_text=memo)
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
        print('posting %s/payments, payment_payload %s' % (config.PAYMENT_SERVICE_URL, payment_payload))
        res = requests.post('%s/payments' % config.PAYMENT_SERVICE_URL, headers=headers, json=payment_payload)
        res.raise_for_status()
    except Exception as e:
        increment_metric('send_kin_error')
        print('caught exception sending kin to address %s using the payment service' % public_address)
        print(e)


def link_wallets_whitelist(sender_address, recipient_address, transaction):
    print('whitelisting wallets linking -> from %s to: %s' %(sender_address, recipient_address))
    headers = {'X-REQUEST-ID': str(random.randint(1, 1000000))}  # doesn't actually matter
    payment_payload = {
        'sender_address': sender_address,
        'recipient_address': recipient_address,
        'transaction': transaction,
        'network_id': config.STELLAR_NETWORK
    }

    try:
        print('posting %s/linking/whitelist payload: %s' % (config.PAYMENT_SERVICE_URL, payment_payload))
        result = requests.post('%s/linking/whitelist' % config.PAYMENT_SERVICE_URL, headers=headers, json=payment_payload)
        result.raise_for_status()
        print('result %s ' % result.text)
        print('result %s ' % result.content)
        tx_json = json.loads(result.content.decode("utf-8"))
        print('tx_json %s ' % tx_json)
        print('returning tx= %s ' % tx_json['tx'])
        return tx_json['tx']
    except Exception as e:
        increment_metric('whitelist_error')
        print('caught exception while whitelisting wallets linking from %s to %s' % (sender_address, recipient_address))
        print(e)

def add_signature(id, sender_address, recipient_address, amount, transaction):
    """add backend signature to transaction"""

    print('adding whitelisted signature for transaction from %s to: %s' %(sender_address, recipient_address))
    headers = {'X-REQUEST-ID': str(random.randint(1, 1000000))}  # doesn't actually matter
    payment_payload = {
        'id': id,
        'sender_address': sender_address,
        'recipient_address': recipient_address,
        'amount': amount,
        'transaction': transaction,
        'app_id': 'kit',
        'network_id': config.STELLAR_NETWORK
    }

    try:
        print('posting %s/tx/whitelist payload: %s' % (config.PAYMENT_SERVICE_URL, payment_payload))
        result = requests.post('%s/tx/whitelist' % config.PAYMENT_SERVICE_URL, headers=headers, json=payment_payload)
        result.raise_for_status()
        print('result %s ' % result.text)
        print('result %s ' % result.content)
        tx_json = json.loads(result.content.decode("utf-8"))
        print('tx_json %s ' % tx_json)
        print('returning tx= %s ' % tx_json['tx'])
        return tx_json['tx']
    except Exception as e:
        increment_metric('whitelist_error')
        print('caught exception while whitelisting transaction from %s to %s' % (sender_address, recipient_address))
        print(e)


def extract_tx_payment_data(tx_hash):
    """ensures that the given tx_hash is a valid payment tx,
       and return a dict with the memo, amount and to_address"""
    if tx_hash is None:
        raise InvalidUsage('invalid params')

    # get the tx_hash data. this might take a second,
    # so retry while 'Resource Missing' is recevied
    count = 0
    tx_data = None
    while count < config.STELLAR_TIMEOUT_SEC:
        try:
            tx_data = app.kin_sdk.get_transaction_data(tx_hash)

        except kin.KinErrors.ResourceNotFoundError:
            count = count + 1
            sleep(1)
        else:
            break

    if tx_data is None:
        print('could not get tx_data for tx_hash: %s. waited %s seconds' % (tx_hash, count))
        increment_metric('tx_data_timeout')
        return False, {}

    # get the simple op:
    op = tx_data.operation

    # verify op type
    from kin.transactions import OperationTypes
    if op.type != OperationTypes.PAYMENT:
        print('unexpected type: %s' % op.type)
        return False, {}

    # assemble the result dict
    data = {'memo': tx_data.memo, 'amount': op.amount, 'to_address': op.destination}
    return True, data


def get_kin_balance(public_address):
    """returns the current kin balance for this account"""
    try:
        return app.kin_sdk.get_account_balance(public_address)
    except Exception as e:
        print(e)
        print('could not get kin balance for address: %s' % public_address)
        return None

