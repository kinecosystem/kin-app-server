'''
The Kin App Server API is defined here.
'''
from threading import Thread
from uuid import UUID, uuid4

from flask import request, jsonify, abort
from flask_api import status
import redis_lock

from kinappserver import app, config, stellar, utils
from kinappserver.stellar import create_account, send_kin
from kinappserver.utils import InvalidUsage, InternalError, errors_to_string, increment_metric
from kinappserver.models import create_user, update_user_token, update_user_app_version, store_task_results, add_task, get_tasks_for_user, is_onboarded, set_onboarded, send_push_tx_completed, send_engagement_push, create_tx, update_task_time, get_reward_for_task, add_offer, get_offers_for_user, set_offer_active, create_order, process_order, create_good, list_inventory, release_unclaimed_goods, count_transactions_by_minutes_ago, get_tokens_for_push


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
    '''extracts the user_id from the request header'''
    try:
        return request.headers.get('X-USERID')
    except Exception as e:
        print('cant extract user_id from header')
        raise InvalidUsage('bad header')


@app.route('/health', methods=['GET'])
def get_health():
    '''health endpoint'''
    return jsonify(status='ok')


@app.route('/update-task-time', methods=['POST'])
def update_task_time_endpoint():
    '''temp endpoint for setting a task time TODO DELETE ME'''
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


@app.route('/send-tx-completed', methods=['POST'])
def send_gcm_push_tx_completed():
    #TODO DELETE ME
    '''temp endpoint for testing the tx-completed push'''
    try:
        user_id = extract_header(request)
    except Exception as e:
        print('exception in send_gcm_push_tx_completed: %s' % e)
        raise InvalidUsage('bad-request')
    send_push_tx_completed(user_id, 'tx_hash', 2, 'task_id')
    return jsonify(status='ok')


@app.route('/send_engagement_push', methods=['POST'])
def send_engagement_push_api():
    #TODO DELETE ME
    '''temp endpoint for testing the engagement push'''
    try:
        user_id = extract_header(request)
    except Exception as e:
        print('exception in send_gcm_push_tx_completed: %s' % e)
        raise InvalidUsage('bad-request')
    send_engagement_push(user_id, 'engage-recent')
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
    '''updates a user's token in the database '''
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
    '''receive the results for a tasks and pay the user for them'''
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

    if not store_task_results(user_id, task_id, results):
        # should never happen: the client sent the results too soon
        print('rejecting user %s task %s results' % (user_id, task_id))
        increment_metric('premature_task_results')
        return jsonify(status='error', reason='cooldown_enforced'), status.HTTP_400_BAD_REQUEST
    try:
        memo = utils.KINIT_MEMO_PREFIX + str(uuid4())[:utils.ORDER_ID_LENGTH] # generate a memo string and send it to the client
        reward_store_and_push(address, task_id, send_push, user_id, memo)
    except Exception as e:
        print('exception: %s' % e)
        print('failed to reward task %s at address %s' % (task_id, address))

    increment_metric('task_completed')
    return jsonify(status='ok', memo=str(memo))


@app.route('/task/add', methods=['POST'])
def add_task_api():
    '''used to add tasks to the db'''
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
    '''returns the current task for the user with the given id'''
    user_id = extract_header(request)
    tasks = get_tasks_for_user(user_id)
    try:
        # handle unprintable chars...
        print(tasks)
    except Exception as e:
        print(e)
    return jsonify(tasks=tasks)


@app.route('/user/onboard', methods=['POST'])
def onboard_user():
    '''creates a wallet for the user and deposits some xlms there'''
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
        lock = redis_lock.Lock(app.redis, 'address:%s' % public_address)
        if lock.acquire(blocking=False):
            try:
                print('creating account with address %s and amount %s' % (public_address, config.STELLAR_INITIAL_ACCOUNT_BALANCE))
                tx_id = create_account(public_address, config.STELLAR_INITIAL_ACCOUNT_BALANCE)
                if(tx_id):
                    set_onboarded(user_id, True)
                else:
                    raise InternalError('failed to create account at %s' % public_address)
            except Exception as e:
                print('exception trying to create account:%s' % e)
                raise InternalError('unable to create account')
            else:
                print('created account %s with txid %s' % (public_address, tx_id))
            finally:
                lock.release()
        else:
            raise InvalidUsage('already creating account for user_id: %s and address: %s' % (user_id, public_address))

        increment_metric('user_onboarded')
        return jsonify(status='ok')


@app.route('/user/register', methods=['POST'])
def register_api():
    ''' register a user to the system
    called once by every client until 200OK is received from the server.
    the payload may contain a optional push token.
    '''
    payload = request.get_json(silent=True)
    try:
        # add redis lock here?
        user_id = payload.get('user_id', None)
        os = payload.get('os', None)
        device_model = payload.get('device_model', None)
        token = payload.get('token', None)
        time_zone = payload.get('time_zone', None)
        print('raw time_zone: %s' % time_zone)
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
            increment_metric('user_registered')
            return jsonify(status='ok')


def reward_store_and_push(public_address, task_id, send_push, user_id, memo):
    '''create a thread to perform this function in the background'''
    Thread(target=reward_address_for_task_internal, args=(public_address, task_id, send_push, user_id, memo)).start()


def reward_address_for_task_internal(public_address, task_id, send_push, user_id, memo):
    '''transfer the correct amount of kins for the task to the given address
    
       this function runs in the background and sends a push message to the client to
       indicate that the money was indeed transferred.
    '''
    # get reward amount from db
    amount = get_reward_for_task(task_id)
    if not amount:
        print('could not figure reward amount for task_id: %s' % task_id)
        raise InternalError('cant find reward for taskid %s' % task_id)
    try:
        # send the moneys
        print('calling send_kin: %s, %s' % (public_address, amount))
        tx_hash = send_kin(public_address, amount, memo)
    except Exception as e:
        print('caught exception sending %s kins to %s - exception: %s:' % (amount, public_address, e))
        raise InternalError('failed sending %s kins to %s' % (amount, public_address))
    finally: #TODO dont do this if we fail with the tx
        if send_push:
            send_push_tx_completed(user_id, tx_hash, amount, task_id)
        create_tx(tx_hash, user_id, public_address, False, amount, {'task_id': task_id, 'memo': memo}) # TODO Add memeo?


@app.route('/offer/add', methods=['POST'])
def add_offer_api():
    '''endpoint used to populate the server with offers'''
    if not config.DEBUG:
        limit_to_local_host()
    payload = request.get_json(silent=True)
    try:
        offer = payload.get('offer', None)
        set_active = payload.get('set_active', False) # optional
    except Exception as e:
        print('exception: %s' % e)
        raise InvalidUsage('bad-request')
    if add_offer(offer, set_active):
        return jsonify(status='ok')
    else:
        raise InvalidUsage('failed to add offer')


@app.route('/offer/set_active', methods=['POST'])
def set_active_api():
    '''enables/disables an offer'''
    if not config.DEBUG:
        limit_to_local_host()
    payload = request.get_json(silent=True)
    try:
        offer_id = payload.get('id', None)
        is_active = payload.get('is_active', None)
    except Exception as e:
        print('exception: %s' % e)
        raise InvalidUsage('bad-request')
    if set_offer_active(offer_id, is_active):
        return jsonify(status='ok')
    else:
        raise InvalidUsage('failed to set offer status')


@app.route('/offer/book', methods=['POST'])
def book_offer_api():
    '''books an offer by a user'''
    payload = request.get_json(silent=True)
    try:
        user_id = extract_header(request)
        offer_id = payload.get('id', None)
        if None in (user_id, offer_id):
            raise InvalidUsage('invalid payload')
    except Exception as e:
        raise InvalidUsage('bad-request')
    order_id, error_code = create_order(user_id, offer_id)
    if order_id:
        increment_metric('offers_booked')
        return jsonify(status='ok', order_id=order_id)
    else:
        return jsonify(status='error', reason=errors_to_string(error_code)), status.HTTP_400_BAD_REQUEST


@app.route('/user/offers', methods=['GET'])
def get_offers_api():
    '''return the list of availble offers for this user'''
    try:
        user_id = extract_header(request)
        if user_id is None:
            raise InvalidUsage('no user_id')
    except Exception as e:
        print('exception: %s' % e)
        raise InvalidUsage('bad-request')
        print('offers %s' % get_offers_for_user(user_id))
    return jsonify(offers=get_offers_for_user(user_id))


@app.route('/offer/redeem', methods=['POST'])
def purchase_api():
    '''process the given tx_hash and return the payed-for goods'''

    #TODO: at some point we should try to listen in on incoming tx_hashes
    # for our account(s). this should hasten the process of reedeming offers.
    payload = request.get_json(silent=True)
    try:
        user_id = extract_header(request)
        tx_hash =  payload.get('tx_hash', None)
        if None in (user_id, tx_hash):
            raise InvalidUsage('invalid param')
    except Exception as e:
        print('exception: %s' % e)
        raise InvalidUsage('bad-request')

    try:
        # process the tx_hash, provided its not already being processed by another server
        lock = redis_lock.Lock(app.redis, 'redeem:%s' % tx_hash)
        if lock.acquire(blocking=False):
            success, goods = process_order(user_id, tx_hash)
            if not success:
                raise InvalidUsage('cant redeem with tx_hash:%s' % tx_hash)
            increment_metric('offers_redeemed')
            return jsonify(status='ok', goods=goods)
        else:
            return jsonify(status='error', reason='already processing tx_hash')
    finally:
            lock.release()

@app.route('/good/add', methods=['POST'])
def add_good_api():
    '''endpoint used to populate the server with goods'''
    if not config.DEBUG:
        limit_to_local_host()
    payload = request.get_json(silent=True)
    try:
        offer_id = payload.get('offer_id', None)
        good_type = payload.get('good_type', None)
        value = payload.get('value', None)
        if None in (offer_id, good_type, value):
            raise InvalidUsage('invalid params')
    except Exception as e:
        print('exception: %s' % e)
        raise InvalidUsage('bad-request')
    if create_good(offer_id, good_type, value):
        return jsonify(status='ok')
    else:
        raise InvalidUsage('failed to add good')


@app.route('/good/inventory', methods=['GET'])
def inventory_api():
    '''endpoint used to populate the server with goods'''
    if not config.DEBUG:
        limit_to_local_host()
    return jsonify(status='ok', inventory=list_inventory())


@app.route('/balance', methods=['GET'])
def balance_api():
    '''endpoint used to populate the server with goods'''
    if not config.DEBUG:
        limit_to_local_host()
    balance = {}
    balance['kin'] = stellar.get_kin_balance(config.STELLAR_PUBLIC_ADDRESS)
    balance['xlm'] = stellar.get_xlm_balance(config.STELLAR_PUBLIC_ADDRESS)
    if balance[kin] is not None and balance['xlm'] is not None:
        return jsonify(status='ok', balance=balance)
    else:
        return jsonify(status='error'), status.HTTP_500_INTERNAL_SERVER_ERROR  


@app.route('/good/release_unclaimed', methods=['GET'])
def release_unclaimed_api():
    '''endpoint used to get the current balance'''
    if not config.DEBUG:
        limit_to_local_host()
    released=release_unclaimed_goods()
    increment_metric('unclaimed_released', released)
    return jsonify(status='ok', released=released)


@app.route('/engagement/send', methods=['GET'])
def send_engagemnt_api():
    '''endpoint used to send engagement push notifications to users by scheme. password protected'''
    password = request.args.get('password', '')
    from kinappserver import kms

    if password != kms.get_ssm_parameter('/config/web-password', config.KMS_KEY_AWS_REGION):
        print('rejecting request with incorrect password')
        abort(403)

    scheme = request.args.get('scheme')
    if scheme is None:
        raise InvalidUsage('invalid param')

    tokens = get_tokens_for_push(scheme)
    if tokens is None:
         raise InvalidUsage('invalid scheme')

    for token in tokens['iOS']:
        send_engagement_push(None, scheme, token, 'iOS')
    for token in tokens['android']:
        send_engagement_push(None, scheme, token, 'android')
    
    return jsonify(status='ok')


@app.route('/get_push_tokens', methods=['GET'])
def get_apns_tokens_api():
    '''endpoint used to get push-tokens for engagment messages'''
    password = request.args.get('password', '')
    from kinappserver import kms

    if not config.DEBUG and password != kms.get_ssm_parameter('/config/web-password', config.KMS_KEY_AWS_REGION):
        print('rejecting request with incorrect password')
        abort(403)

    scheme = request.args.get('scheme')
    if scheme is None:
        raise InvalidUsage('invalid param')

    tokens = get_tokens_for_push(scheme)
    if tokens is None:
         raise InvalidUsage('invalid scheme')

    return jsonify(status='ok', tokens=tokens)