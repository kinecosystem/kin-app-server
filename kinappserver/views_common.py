"""
code that's common to both public and private apis
"""

from flask import request, jsonify, abort
from kinappserver.utils import InvalidUsage, InternalError
from kinappserver import app, ssm


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


def get_source_ip(request):
    """returns the source ip of the request from the nginx header"""
    return request.headers.get('X-FORWARDED-FOR', None)


def extract_headers(request):
    """extracts the user_id from the request header"""
    try:
        user_id = request.headers.get('X-USERID')
        auth_token = request.headers.get('X-AUTH-TOKEN', None)
    except Exception as e:
        print('cant extract user_id from header')
        raise InvalidUsage('bad header')
    return user_id, auth_token


def limit_to_localhost():
    """aborts requests with x-forwarded header"""
    if request.headers.get('X-Forwarded', None) is not None:
        print('aborting non-local request trying to access a local-only endpoint')
        abort(403)


def limit_to_acl():
    """aborts unauthorized requests for sensitive APIs (nginx specific). allow on DEBUG"""
    source_ip = request.headers.get('X-Forwarded-For', None)
    if not source_ip:
        print('missing expected header')
        abort(403)
        pass
    if not is_in_acl(source_ip):
        print('%s is not in ACL, rejecting' % source_ip)
        abort(403)


def limit_to_password():
    """ensure the request came with the expected security password"""
    password = request.headers.get('X-Password', '')
    if password in ssm.get_security_passwords():
        pass
    else:
        abort(403)  # Forbidden
