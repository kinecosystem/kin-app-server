'''
The Kin App Server API is defined here.
'''

from flask import request, jsonify, abort
import redis_lock
import requests
from uuid import UUID
import json

from kinappserver import app, config
from kinappserver.stellar import create_account, send_kin
from kinappserver.utils import InvalidUsage, InternalError, send_gcm
from kinappserver.models import create_user, update_user_token, update_user_app_version, store_task_results, add_task, get_task_ids_for_user, get_task_by_id, is_onboarded, set_onboarded, send_push_tx_completed, create_tx, update_task_time, get_reward_for_task, add_offer, get_offers_for_user, set_offer_active


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


@app.route('/update-task-time', methods=['POST'])
def update_task_time_endpoint():
    '''temp endpoint for setting a task time'''
    payload = request.get_json(silent=True)
    try:
        task_id = str(payload.get('task_id', None))
        time_string = str(payload.get('time_string', None))
        if None in (task_id, time_string):
            raise InvalidUsage('bad-request')
    except Exception as e:
        print('exception: %s' % e)
        raise InvalidUsage('bad-request')

    update_task_time(task_id, time_string)
    return jsonify(status='ok')


@app.route('/send-kin', methods=['POST'])
def send_kin_to_user():
    '''temp endpoint for testing sending kin TODO remove'''
    payload = request.get_json(silent=True)
    try:
        public_address = payload.get('public_address', None)
        amount = payload.get('amount', None)
        if None in (public_address, amount):
            raise InvalidUsage('bad-request')
    except Exception as e:
        print('exception: %s' % e)
        raise InvalidUsage('bad-request')

    #establish trust
    from stellar_base.asset import Asset
    my_asset = Asset('KIN', 'GCKG5WGBIJP74UDNRIRDFGENNIH5Y3KBI5IHREFAJKV4MQXLELT7EX6V')
    tx_hash = app.kin_sdk.trust_asset(my_asset, limit=2)
    print('trust tx hash: %s' % tx_hash)

    tx_hash = send_kin(public_address, amount, 'test')
    print('transfer tx hash: %s' % tx_hash)
    return jsonify(status='ok')


@app.route('/send-gcm', methods=['POST'])
def send_gcm_push():
    '''temp endpoint for testing gcm TODO remove'''
    payload = request.get_json(silent=True)
    try:
        push_payload = payload.get('push_payload', None)
        push_token = payload.get('push_token', None)
        if None in (push_token, push_payload):
            raise InvalidUsage('bad-request')
    except Exception as e:
        print('exception: %s' % e)
        raise InvalidUsage('bad-request')
    send_gcm(push_token, push_payload)
    return jsonify(status='ok')


@app.route('/send-tx-completed', methods=['POST'])
def send_gcm_push_tx_completed():
    #TODO remove this function
    '''temp endpoint for testing the tx-completed push'''
    payload = request.get_json(silent=True)
    try:
        user_id = extract_header(request)
    except Exception as e:
        print('exception in send_gcm_push_tx_completed: %s' % e)
        raise InvalidUsage('bad-request')
    send_push_tx_completed(user_id, 'tx_hash', 2, 'task_id')
    return jsonify(status='ok')


@app.route('/user/app-launch', methods=['POST'])
def app_launch():
    '''called whenever the app is launched'''
    payload = request.get_json(silent=True)
    app_ver, user_id = None, None
    try:
        print('payload in app-launch: %s' % payload)
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


@app.route('/user/task/results', methods=['POST'])
def quest_answers():
    payload = request.get_json(silent=True)
    try:
        user_id = extract_header(request)
        task_id = payload.get('id', None)
        address = payload.get('address', None)
        results = payload.get('results', None)
        send_push = payload.get('send_push', True)
        if None in (user_id, task_id, address, results):
            raise InvalidUsage('bad-request')
        #TODO more input checks here
    except Exception as e:
        raise InvalidUsage('bad-request')
    # store the results and pay the user
    store_task_results(user_id, task_id, results)
    try:
        reward_store_and_push(address, task_id, send_push, user_id)
    except Exception as e:
        print('exception: %s' % e)
        print('failed to reward task %s at address %s' % (task_id, address))

    return jsonify(status='ok')


@app.route('/task/add', methods=['POST'])
def add_task_api():
    if not config.DEBUG:
        limit_to_local_host()
    payload = request.get_json(silent=True)
    try:
        task = payload.get('task', None)
    except Exception as e:
        print('exception: %s' % e)
        raise InvalidUsage('bad-request')
    if add_task(task):
        return jsonify(status='ok')
    else:
        raise InvalidUsage('failed to add task')


@app.route('/user/tasks', methods=['GET'])
def get_next_task():
    '''return the current task for the user with the given id'''
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
    if onboarded is True:
        raise InvalidUsage('user already has an account')
    elif onboarded is None:
        raise InvalidUsage('no such user exists')
    else:
        # create an account, provided none is already being created
        lock = redis_lock.Lock(app.redis, 'address:' + public_address)
        if lock.acquire(blocking=False):
            try:
                print('creating account with address %s and amount %s' % (public_address, config.STELLAR_INITIAL_ACCOUNT_BALANCE))
                tx_id = create_account(public_address, config.STELLAR_INITIAL_ACCOUNT_BALANCE)
                set_onboarded(user_id, True)
            except Exception as e:
                print('exception trying to create account:%s' % e)
                raise InternalError('unable to create account')
            else:
                print('created account %s with txid %s' % (public_address, tx_id))
            finally:
                lock.release()
        else:
            raise InvalidUsage('already creating account for user_id: %s and address: %s' % (user_id, public_address))

        return jsonify(status='ok')


@app.route('/user/register', methods=['POST'])
def register_api():
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
            print('created user with user_id %s' % (user_id))
            return jsonify(status='ok')


def reward_store_and_push(public_address, task_id, send_push, user_id):
    '''create a thread to perform this function in the background'''
    from threading import Thread
    thread = Thread(target=reward_address_for_task_internal, args=(public_address, task_id, send_push, user_id))
    thread.start()


def reward_address_for_task_internal(public_address, task_id, send_push, user_id):
    '''transfer the correct amount of kins for the task to the given address'''
    # get reward amount from db
    amount = get_reward_for_task(task_id)
    if not amount:
        print('could not figure reward amount for task_id: %s' % task_id)
        raise InternalError('cant find reward for taskid %s' % task_id)
    try:
        # send the moneys
        print('calling send_kin: %s, %s' % (public_address, amount))
        tx_hash = send_kin(public_address, amount, 'kin-app')#-taskid:%s' % task_id)
    except Exception as e:
        print('caught exception sending %s kins to %s - exception: %s:' % (amount, public_address, e))
        raise InternalError('failed sending %s kins to %s' % (amount, public_address))
    finally: #TODO dont do this if we fail with the tx
        if send_push:
            send_push_tx_completed(user_id, tx_hash, amount, task_id)
        create_tx(tx_hash, user_id, public_address, False, amount, {'task_id':task_id}) # TODO Add memeo?


@app.route('/offer/add', methods=['POST'])
def add_offer_api():
    '''endpoint used to populate the server with offers'''
    if not config.DEBUG:
        limit_to_local_host()
    payload = request.get_json(silent=True)
    try:
        offer = payload.get('offer', None)
    except Exception as e:
        print('exception: %s' % e)
        raise InvalidUsage('bad-request')
    if add_offer(offer):
        return jsonify(status='ok')
    else:
        raise InvalidUsage('failed to add offer')


@app.route('/offer/set_active', methods=['POST'])
def set_active_api():
    '''endpoint used to populate the server with offers'''
    if not config.DEBUG:
        limit_to_local_host()
    payload = request.get_json(silent=True)
    try:
        offer_id = payload.get('offer_id', None)
        is_active = payload.get('is_active', None)
    except Exception as e:
        print('exception: %s' % e)
        raise InvalidUsage('bad-request')
    if set_offer_active(offer_id, is_active):
        return jsonify(status='ok')
    else:
        raise InvalidUsage('failed to set offer status')


@app.route('/user/offers', methods=['GET'])
def get_offers_api():
    '''return the list of offers for this user'''
    try:
        user_id = request.args.get('user-id', None)
        if user_id is None:
            raise InvalidUsage('no user_id')
    except Exception as e:
        print('exception: %s' % e)
        raise InvalidUsage('bad-request')
        print('offers %s' % get_offers_for_user(user_id))
    return jsonify(offers=get_offers_for_user(user_id))

