'''
The Kin Wallet Service API is defined here.
'''
import time  # for sleep

from flask import request, jsonify, abort
import redis_lock
import requests

from kinwalletservice import app, config
from kinwalletservice.utils import InvalidUsage, InternalError


def limit_to_local_host():
    '''aborts non-local requests for sensitive APIs (nginx specific). allow on DEBUG'''
    if config.DEBUG or request.headers.get('X-Forwarded-For', None) is None:
        pass
    else:
        abort(403)  # Forbidden


@app.errorhandler(InvalidUsage)
def handle_invalid_usage(error):
    # converts exceptions to responses
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response


@app.errorhandler(InternalError)
def handle_internal_error(error):
    # converts exceptions to responses
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response

'''
@app.route('/get_user_balance', methods=["GET"])
def get_user_balance():
    # return the user's kin balance
    username = request.args.get('kikuserid', None)
    if not username:
        raise InvalidUsage('no kikuserid provided')

    pa = get_address(username)
    if not pa:
        raise InvalidUsage('user has no public address')
    balance = app.kin_sdk.get_address_token_balance(pa)
    return jsonify(kin_balance=balance)
'''