from kinappserver import app

def create_account(public_address, initial_xlm_amount):
    '''create an account for the given public address'''
    return app.kin_sdk.create_account(public_address, initial_xlm_amount)


def send_kin(public_address, amount, memo=None):
    '''send kins to an address'''
    return app.kin_sdk.send_kin(public_address, amount, memo)