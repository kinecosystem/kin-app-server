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


def verify_tx(tx_hash, expected_kin_cost, expected_dst_address, expected_memo):
    '''ensures that the given tx_hash meets the expectations'''
    if None in (tx_hash, expected_memo, expected_dst_address, expected_kin_cost):
        raise InvalidUsage('invlid params')

    tx_data = app.kin_sdk.get_transaction_data(tx_hash)
    if len(tx_data.operations) != 1:
        print('too many ops')
        return False

    #import simplejson as json
    #print(int(tx_data.operations[0]['amount']))

    op = tx_data.operations[0]

    # verify type
    if op['type'] != 'payment':
        print('unexpected type: %s' % op['type'])
        return False

    if op['asset_code'] != 'KIN' and op['asset_issuer'] != config.STELLAR_KIN_ISSUER_ADDRESS and op['asset_type'] != 'credit_alphanum4':
        print('unexpected asset/issuer/asset_type')
        return False

    if tx_data['memo'] != expected_memo and tx_data['memo_type'] != 'text':
        print('unexpected memo')
        return False
    
    if int(op['amount']) != expected_kin_cost:
        print('unexpected amount')
        return False

    if op['to_address'] != expected_dst_address:
        print('unexpected dst address')
        return False
    
    return True