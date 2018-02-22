from kinappserver import app, config
from kinappserver.utils import InvalidUsage, InternalError


def create_account(public_address, initial_xlm_amount):
    '''create an account for the given public address'''
    print('creating account with balance:%s' % initial_xlm_amount)
    return app.kin_sdk.create_account(public_address, starting_balance=initial_xlm_amount)


def send_kin(public_address, amount, memo=None):
    '''send kins to an address'''
    print('sending kin to address: %s' % public_address) #TODO REMOVE
    from stellar_base.asset import Asset
    kin_asset = Asset('KIN', config.STELLAR_KIN_ISSUER_ADDRESS)
    return app.kin_sdk._send_asset(kin_asset, public_address, amount, memo)

def extract_tx_payment_data(tx_hash):
    '''ensures that the given tx_hash is a valid payment tx, 
       and return a dict with the memo, amount and to_address'''
    if tx_hash is None:
        raise InvalidUsage('invlid params')

    tx_data = app.kin_sdk.get_transaction_data(tx_hash)
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
    if op['asset_code'] != 'KIN' and op['asset_issuer'] != config.STELLAR_KIN_ISSUER_ADDRESS and op['asset_type'] != 'credit_alphanum4':
        print('unexpected asset-code/issuer/asset_type')
        return False, {}

    # verify memo type
    if tx_data['memo_type'] != 'text':
        print('unexpected memo type')
        return False, {}

    # assemble the result dict
    data = {}
    data['memo'] = tx_data.get('memo', None)
    data['amount'] = tx_data.get('amount', None)
    data['to_address'] = tx_data.get('to_address', None)
    return True, data