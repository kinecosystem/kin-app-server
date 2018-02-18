from kinappserver import app, config


def create_account(public_address, initial_xlm_amount):
    '''create an account for the given public address'''
    print('creating account with balance:%s' % initial_xlm_amount)
    return app.kin_sdk.create_account(public_address, starting_balance=initial_xlm_amount)


def send_kin(public_address, amount, memo=None):
    '''send kins to an address'''
    print('sending kin to address: %s' % public_address) #TODO REMOVE
    from stellar_base.asset import Asset
    kin_asset = Asset('KIN', config.STELLAR_KIN_ISSUER_ADDRESS)
    return app.kin_sdk.send_asset(public_address, kin_asset, amount, memo)
