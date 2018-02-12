from kinappserver import app

def create_account(public_address, initial_xlm_amount):
    '''create an account for the given public address'''
    app.kin_sdk.create_account(public_address, initial_xlm_amount)