from kinappserver import app

def create_account(public_address, initial_xlm_amount):
    '''create an account for the given public address'''
    return app.kin_sdk.create_account(public_address, initial_xlm_amount)


def send_kin(public_address, amount, memo=None):
    '''send kins to an address'''
    print('address: %s' % public_address)
    from stellar_base.asset import Asset
    kin_asset = Asset('KIN', 'GCKG5WGBIJP74UDNRIRDFGENNIH5Y3KBI5IHREFAJKV4MQXLELT7EX6V')
    return app.kin_sdk.send_asset(public_address, kin_asset, amount, memo)