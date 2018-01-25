'''
The Kin Wallet Service API is defined here.
'''

from flask import request, jsonify, abort
import redis_lock
import requests

from kinwalletservice import app, config
from kinwalletservice.utils import InvalidUsage, InternalError
from kinwalletservice.model import create_user


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

@app.route('/health', methods=['GET'])
def get_health():
    return jsonify(status='ok')

def extract_userid(request):
    user_id = request.headers.get('x-userid', None)
    if user_id is None:
        raise InvalidUsage('bad-request')
    return user_id

@app.route('/user/register', methods=['POST'])
def register():
    ''' register a user to the system. 
    called once by every client until 200OK is received from the server.
    the payload may contain a optional push token.
    '''
    user_id = extract_userid(request)
    payload = request.get_json(silent=True)
    try:
        os = payload.get('os', None)
        device_model = payload.get('device_model', None)
        token = payload.get('token', None)
        time_zone = payload.get('time_zone', None)
        device_id = payload.get('device_id', None)
        #TODO more input check on the values
        if None in (user_id, os, device_model, time_zone, device_id): # token is optional
            raise InvalidUsage('bad-request')
        if os not in ('ios', 'android'):
            raise InvalidUsage('bad-request')
    except Exception as e:
        raise InvalidUsage('bad-request')
    else:
        try:
            create_user(user_id, os, device_model, token, time_zone, device_id)
        except InvalidUsage as e:
            raise InvalidUsage('duplicate-userid')
        else:
            print('created user with user_id %s' % (user_id) )
            return jsonify(status='ok')
