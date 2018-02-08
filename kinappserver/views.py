'''
The Kin App Server API is defined here.
'''

from flask import request, jsonify, abort
import redis_lock
import requests
from uuid import UUID

from kinappserver import app, config
from kinappserver.utils import InvalidUsage, InternalError, create_account
from kinappserver.model import create_user, update_user_token, update_user_app_version, store_task_results, add_task, get_task_ids_for_user, get_task_by_id, is_onboarded, set_onboarded


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

def extract_header(request):
    try:
        return request.headers.get('X-USERID')
    except Exception as e:
        print('cant extract user_id from header')
        raise InvalidUsage('bad header')

@app.route('/health', methods=['GET'])
def get_health():
    return ''

@app.route('/user/app-launch', methods=['POST'])
def app_launch():
    
    payload = request.get_json(silent=True)
    try:
        user_id = extract_header(request)
        app_ver = payload.get('app_ver', None)
    except Exception as e:
        raise InvalidUsage('bad-request')   
    update_user_app_version(user_id, app_ver)
    return jsonify(status='ok')

@app.route('/user/update-token', methods=['POST'])
def update_token():
    ''' update a user's token in the database '''
    payload = request.get_json(silent=True)
    try:
        user_id = extract_header(request)
        token = payload.get('token', None)
        if None in (user_id, token):
            raise InvalidUsage('bad-request')
    except Exception as e:
        raise InvalidUsage('bad-request')
    print('updating token for user %s' % user_id)
    update_user_token(user_id, token)
    return jsonify(status='ok')

@app.route('/user/task/results',methods=['POST'])
def quest_answers():
    payload = request.get_json(silent=True)
    try:
        user_id = extract_header(request)
        task_id = payload.get('id', None)
        address = payload.get('address', None)
        results = payload.get('results', None)
        if None in (user_id, task_id, address, results):
            raise InvalidUsage('bad-request')
        #TODO more input checks here
    except Exception as e:
        raise InvalidUsage('bad-request')
    store_task_results(user_id, task_id, results)
    return jsonify(status='ok')

@app.route('/task/add',methods=['POST'])
def add_task_api():
    limit_to_local_host()
    payload = request.get_json(silent=True)
    try:
        task_id = payload.get('id', None)
        quest = payload.get('task', None)
    except Exception as e:
        raise InvalidUsage('bad-request')
    add_task(task_id, quest)
    return jsonify(status='ok')

@app.route('/user/tasks',methods=['GET'])
def get_next_quest():
    '''return the current questionnaire for the user with the given id'''
    user_id = request.args.get('user-id', None)
    tasks = []
    for tid in get_task_ids_for_user(user_id):
        tasks.append(get_task_by_id(tid))
    print(tasks)
    return jsonify(tasks=tasks)

@app.route('/user/onboard', methods=['POST'])
def onboard_user():
    # input sanity
    try:
        user_id = extract_header(request)
        public_address = request.get_json(silent=True).get('public_address', None)
        if None in (public_address, user_id):
            raise InvalidUsage('bad-request')
    except Exception as e:
        raise InvalidUsage('bad-request')

    # ensure the user exists but does not have an account:
    onboarded = is_onboarded(user_id)
    if onboarded == True:
        raise InvalidUsage('user already has an account')
    elif onboarded is None:
        raise InvalidUsage('no such user exists')
    else:
        # create an account, provided none is already being created
        lock = redis_lock.Lock(app.redis, "address:" + public_address)
        if lock.acquire(blocking=False):
            try:
                if create_account(public_address):
                    set_onboarded(user_id, True)
                else:
                    raise InternalError('unable to create account')
            finally:
                lock.release()
        else:
            raise InvalidUsage('already creating account for user_id: %s and address: %s' % (user_id, public_address))

        return jsonify(status='ok')


@app.route('/user/register', methods=['POST'])
def register():
    ''' register a user to the system. 
    called once by every client until 200OK is received from the server.
    the payload may contain a optional push token.
    '''
    payload = request.get_json(silent=True)
    try:
        user_id = payload.get('user_id', None)
        os = payload.get('os', None)
        device_model = payload.get('device_model', None)
        token = payload.get('token', None)
        time_zone = payload.get('time_zone', None)
        device_id = payload.get('device_id', None)
        app_ver = payload.get('app_ver', None)
        #TODO more input check on the values
        if None in (user_id, os, device_model, time_zone, app_ver): # token is optional, device-id is required but may be None
            raise InvalidUsage('bad-request')
        if os not in ('iOS', 'android'):
            raise InvalidUsage('bad-request')
        user_id = UUID(user_id) # throws exception on invalid uuid
    except Exception as e:
        raise InvalidUsage('bad-request')
    else:
        try:
            create_user(user_id, os, device_model, token, time_zone, device_id, app_ver)
        except InvalidUsage as e:
            raise InvalidUsage('duplicate-userid')
        else:
            print('created user with user_id %s' % (user_id) )
            return jsonify(status='ok')
