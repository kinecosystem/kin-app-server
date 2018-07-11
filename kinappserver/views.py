"""
The Kin App Server API is defined here.
"""
from threading import Thread
from uuid import UUID

from flask import request, jsonify, abort
from flask_api import status
import redis_lock
import arrow
import redis

from kinappserver import app, config, stellar, utils, ssm
from kinappserver.stellar import create_account, send_kin
from kinappserver.utils import InvalidUsage, InternalError, errors_to_string, increment_metric, MAX_TXS_PER_USER, extract_phone_number_from_firebase_id_token,\
    sqlalchemy_pool_status, get_global_config
from kinappserver.models import create_user, update_user_token, update_user_app_version, \
    store_task_results, add_task, get_tasks_for_user, is_onboarded, \
    set_onboarded, send_push_tx_completed, send_engagement_push, \
    create_tx, get_reward_for_task, add_offer, \
    get_offers_for_user, set_offer_active, create_order, process_order, \
    create_good, list_inventory, release_unclaimed_goods, get_users_for_engagement_push, \
    list_user_transactions, get_redeemed_items, get_offer_details, get_task_details, set_delay_days,\
    add_p2p_tx, set_user_phone_number, match_phone_number_to_address, user_deactivated,\
    handle_task_results_resubmission, reject_premature_results, find_missing_txs, get_address_by_userid, send_compensated_push,\
    list_p2p_transactions_for_user_id, nuke_user_data, send_push_auth_token, ack_auth_token, is_user_authenticated, is_user_phone_verified, init_bh_creds, create_bh_offer,\
    get_task_results, get_user_config, get_user_report, generate_retarget_list, get_task_by_id, get_truex_activity, get_and_replace_next_task_memo,\
    get_next_task_memo, scan_for_deauthed_users, user_exists, send_push_register, get_user_id_by_truex_user_id


def limit_to_local_host():
    """aborts non-local requests for sensitive APIs (nginx specific). allow on DEBUG"""
    if config.DEBUG or request.headers.get('X-Forwarded-For', None) is None:
        pass
    else:
        abort(403)  # Forbidden


def limit_to_password():
    """ensure the request came with the expected security password"""
    if request.headers.get('X-Password', '') == ssm.get_security_password():
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
    """extracts the user_id from the request header"""
    try:
        return request.headers.get('X-USERID')
    except Exception as e:
        print('cant extract user_id from header')
        raise InvalidUsage('bad header')


@app.route('/health', methods=['GET'])
def get_health():
    """health endpoint"""
    return jsonify(status='ok')


@app.route('/user/app-launch', methods=['POST'])
def app_launch():
    """called whenever the app is launched

        updates the user's last-login time,
        also forwards some config items to the client
    """
    payload = request.get_json(silent=True)
    app_ver, user_id = None, None
    try:
        user_id = extract_header(request)
        app_ver = payload.get('app_ver', None)
    except Exception as e:
        raise InvalidUsage('bad-request')

    update_user_app_version(user_id, app_ver)

    # send auth token if needed
    send_push_auth_token(user_id)

    return jsonify(status='ok', config=get_user_config(user_id))


@app.route('/user/contact', methods=['POST'])
def get_address_by_phone_api():
    """tries to match the given contact info against a user"""
    if not config.P2P_TRANSFERS_ENABLED:
        # this api is disabled, clients should not have asked for it
        print('/user/contact api is disabled by server config')
        raise InvalidUsage('api-disabled')

    payload = request.get_json(silent=True)
    try:
        user_id = extract_header(request)
        phone_number = payload.get('phone_number', None)
        if None in (user_id, phone_number):
            raise InvalidUsage('bad-request')
    except Exception as e:
        print(e)
        raise InvalidUsage('bad-request')
    address = match_phone_number_to_address(phone_number, user_id)
    if not address:
        return jsonify(status='error', reason='no_match'), status.HTTP_404_NOT_FOUND
    print('translated contact request into address: %s' % address)
    return jsonify(status='ok', address=address)


@app.route('/user/auth/ack', methods=['POST'])
def ack_auth_token_api():
    """endpoint used by clients to ack the auth-token they received"""
    payload = request.get_json(silent=True)
    try:
        user_id = extract_header(request)
        token = payload.get('token', None)
        if None in (user_id, token):
            raise InvalidUsage('bad-request: invalid input')
    except Exception as e:
        print(e)
        raise InvalidUsage('bad-request')

    if ack_auth_token(user_id, token):
        increment_metric('auth-token-acked')
        return jsonify(status='ok')
    else:
        return jsonify(status='error', reason='wrong-token'), status.HTTP_400_BAD_REQUEST


@app.route('/user/firebase/update-id-token', methods=['POST'])
def set_user_phone_number_api():
    """get the firebase id token and extract the phone number from it"""
    payload = request.get_json(silent=True)
    try:
        user_id = extract_header(request)
        token = payload.get('token', None)
        unverified_phone_number = payload.get('phone_number', None)  # only used in tests
        if None in (user_id, token):
            raise InvalidUsage('bad-request')
    except Exception as e:
        print(e)
        raise InvalidUsage('bad-request')
    if not config.DEBUG:
        print('extracting verified phone number fom firebase id token...')
        verified_number = extract_phone_number_from_firebase_id_token(token)
        if verified_number is None:
            print('bad id-token: %s' % token)
            return jsonify(status='error', reason='bad_token'), status.HTTP_404_NOT_FOUND
        phone = verified_number
    else:
        # for tests, you can use the unverified number if no token was given
        if token:
            phone = extract_phone_number_from_firebase_id_token(token)

        if not phone:
            print('using un-verified phone number in debug')
            phone = unverified_phone_number.strip().replace('-', '')

        if not phone:
            print('could not extract phone in debug')
            return jsonify(status='error', reason='no_phone_number')

    print('updating phone number for user %s' % user_id)
    set_user_phone_number(user_id, phone)

    return jsonify(status='ok')


@app.route('/user/update-token', methods=['POST'])
def update_token_api():
    """updates a user's token in the database """
    payload = request.get_json(silent=True)
    try:
        user_id = extract_header(request)
        token = payload.get('token', None)
        if None in (user_id, token):
            raise InvalidUsage('bad-request')
    except Exception as e:
        print(e)
        raise InvalidUsage('bad-request')

    print('updating token for user %s' % user_id)
    update_user_token(user_id, token)

    # send auth token now that we have push token
    send_push_auth_token(user_id)

    return jsonify(status='ok')


@app.route('/user/push/update-token', methods=['POST'])
def push_update_token_api():
    """updates a user's push token in the database. also sends the auth token to the user"""
    payload = request.get_json(silent=True)
    try:
        user_id = extract_header(request)
        token = payload.get('token', None)
        if None in (user_id, token):
            raise InvalidUsage('bad-request')
    except Exception as e:
        print(e)
        raise InvalidUsage('bad-request')

    print('updating token for user %s' % user_id)
    update_user_token(user_id, token)

    # send auth token now that we have push token
    send_push_auth_token(user_id)

    return jsonify(status='ok')


@app.route('/user/task/results', methods=['POST'])
def post_user_task_results_endpoint():
    """receive the results for a tasks and pay the user for them"""
    payload = request.get_json(silent=True)
    try:
        user_id = extract_header(request)
        task_id = payload.get('id', None)
        address = payload.get('address', None)
        results = payload.get('results', None)
        send_push = payload.get('send_push', True)
        if None in (user_id, task_id, address, results):
            print('failed input checks on /user/task/results')
            raise InvalidUsage('bad-request')
        # TODO more input checks here
    except Exception as e:
        print('exception in /user/task/results. e=%s' % e)
        raise InvalidUsage('bad-request')

    if config.AUTH_TOKEN_ENFORCED and not is_user_authenticated(user_id):
        print('user %s is not authenticated. rejecting results submission request' % user_id)
        increment_metric('rejected-on-auth')
        return jsonify(status='error', reason='auth-failed'), status.HTTP_400_BAD_REQUEST

    if config.PHONE_VERIFICATION_REQUIRED and not is_user_phone_verified(user_id):
        print('blocking user (%s) results - didnt pass phone_verification' % user_id)
        return jsonify(status='error', reason='user_phone_not_verified'), status.HTTP_400_BAD_REQUEST

    if user_deactivated(user_id):
        print('user %s deactivated. rejecting submission' % user_id)
        return jsonify(status='error', reason='user_deactivated'), status.HTTP_400_BAD_REQUEST

    if reject_premature_results(user_id):
        # should never happen: the client sent the results too soon
        print('rejecting user %s task %s results' % (user_id, task_id))
        increment_metric('premature_task_results')
        return jsonify(status='error', reason='cooldown_enforced'), status.HTTP_400_BAD_REQUEST

    # the following function handles task-results resubmission:

    # there are a few possible scenarios here:
    # the user already submitted these results and did get kins for them.
    # the user already submitted these results *as a different user* and get kins for them:
    # - in both these cases, simply find the memo, and return it to the user.

    # this case isn't handled (yet):
    # another set of cases is where the user DID NOT get compensated for the results.
    # in this case, we want to pay the user, but first to ensure she isn't already in the
    # process of being compensated (perhaps by another server).

    memo, compensated_user_id = handle_task_results_resubmission(user_id, task_id)
    if memo:
        print('detected resubmission of previously payed-for task by user_id: %s. memo:%s' % (compensated_user_id, memo))
        # this task was already submitted - and compensated, so just re-return the memo to the user.
        return jsonify(status='ok', memo=str(memo))

    #  if the last item in the task is of type tip, then figure out how much tip was given:
    #  TODO move to a function
    tip = 0
    task_data = get_task_by_id(task_id)
    if task_data['items'][-1]['type'] == 'tip':
        try:
            #  get the last item in the task - which is where the tipping data is:
            tipping_question = task_data['items'][-1]
            tipping_question_id = tipping_question['id']
            tipping_question_results = tipping_question['results']

            # find the answer that matches the tipping question:
            for item in results:
                if item['qid'] == tipping_question_id:
                    for answer in tipping_question_results:
                        if answer['id'] == item['aid'][0]:
                            tip = answer['tip_value']
                            break
        except Exception as e:
            print('could not get tip value for video_questionnaire. e:%s' % e)

        print('tipping value %s for task_id %s' % (tip, task_id))

    # this should never fail for application-level reasons:
    if not store_task_results(user_id, task_id, results):
            raise InternalError('cant save results for userid %s' % user_id)
    try:
        memo = get_and_replace_next_task_memo(user_id)
        reward_and_push(address, task_id, send_push, user_id, memo, tip)
    except Exception as e:
        print('exception: %s' % e)
        print('failed to reward task %s at address %s' % (task_id, address))

    increment_metric('task_completed')
    return jsonify(status='ok', memo=str(memo))


@app.route('/task/add', methods=['POST'])
def add_task_api():
    """used to add tasks to the db"""
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


@app.route('/push/please_upgrade', methods=['POST'])
def push_please_upgrade_api():
    """used to populate user tables with public addresses"""
    # TODO REMOVE ME
    if not config.DEBUG:
        limit_to_local_host()

    payload = request.get_json(silent=True)
    try:
        user_ids = payload.get('user_ids', None)
    except Exception as e:
        print('exception: %s' % e)
        raise InvalidUsage('bad-request')

    from .push import send_please_upgrade_push_2
    send_please_upgrade_push_2(user_ids)

    return jsonify(status='ok')


@app.route('/task/delay_days', methods=['POST'])
def set_delay_days_api():
    """used to set the delay_days on all tasks"""
    if not config.DEBUG:
        limit_to_local_host()
    payload = request.get_json(silent=True)
    try:
        delay_days = payload.get('days', None)
    except Exception as e:
        print('exception: %s' % e)
        raise InvalidUsage('bad-request')

    set_delay_days(delay_days)
    print('set delay days to %s' % delay_days)
    return jsonify(status='ok')


@app.route('/user/tasks', methods=['GET'])
def get_next_task():
    """returns the current task for the user with the given id"""
    user_id = extract_header(request)
    tasks = get_tasks_for_user(user_id)
    if len(tasks) == 1:
        tasks[0]['memo'] = get_next_task_memo(user_id)

    if user_deactivated(user_id):
        print('user %s is deactivated. returning empty task array' % user_id)
        return jsonify(tasks=[], reason='user_deactivated')

    try:
        # handle unprintable chars...
        print('tasks returned for user %s: %s' % (user_id, tasks))
    except Exception as e:
        print('cant print returned tasks for user %s' % user_id)
        print(e)
    return jsonify(tasks=tasks)


@app.route('/user/transactions', methods=['GET'])
def get_transactions_api():
    """return a list of the last X txs for this user

    each item in the list contains:
        - the tx_hash
        - tx direction (in, out)
        - amount of kins transferred
        - date
        - title and additional details
    """
    detailed_txs = []
    try:
        user_id = extract_header(request)
        server_txs = [{'type': 'server', 'tx_hash': tx.tx_hash, 'amount': tx.amount, 'client_received': not tx.incoming_tx, 'tx_info': tx.tx_info, 'date': arrow.get(tx.update_at).timestamp} for tx in list_user_transactions(user_id, MAX_TXS_PER_USER)]

        # get the offer, task details
        for tx in server_txs:
            details = get_offer_details(tx['tx_info']['offer_id']) if not tx['client_received'] else get_task_details(tx['tx_info']['task_id'])
            detailed_txs.append({**tx, **details})

        # get p2p details
        p2p_txs = [{'title': 'Kin from a friend' if str(tx.receiver_user_id).lower() == str(user_id).lower() else 'Kin to a friend',
                    'description': 'a friend sent you %sKIN' % tx.amount,
                    'provider': {'image_url': 'https://s3.amazonaws.com/kinapp-static/brand_img/poll_logo_kin.png', 'name': 'friend'},
                    'type': 'p2p',
                    'tx_hash': tx.tx_hash,
                    'amount': tx.amount,
                    'client_received': str(tx.receiver_user_id).lower() == str(user_id).lower(),
                    'tx_info': {'memo': 'na', 'task_id': '-1'},
                    'date': arrow.get(tx.update_at).timestamp} for tx in list_p2p_transactions_for_user_id(user_id, MAX_TXS_PER_USER)]

        # merge txs:
        detailed_txs = detailed_txs + p2p_txs

        # sort by date
        print(detailed_txs)
        detailed_txs = sorted(detailed_txs, key=lambda k: k['date'], reverse=True)
        if len(detailed_txs) > MAX_TXS_PER_USER:
            detailed_txs = detailed_txs[:MAX_TXS_PER_USER]

    except Exception as e:
        print('cant get txs for user')
        print(e)
        return jsonify(status='error', txs=[])

    return jsonify(status='ok', txs=detailed_txs)


@app.route('/user/redeemed', methods=['GET'])
def user_redeemed_api():
    """return the list of offers that were redeemed by this user

    each item in the list contains:
        - the actual redeemed item (i.e. the code
        - localized time
        - info about the offer that was redeemed

        essentially, this is a 3-way join between the good, user and offer tables
        that is implemented iteratively. the implementation can be made more efficient
    """

    redeemed_goods = []
    try:
        user_id = extract_header(request)
        incoming_txs_hashes = [tx.tx_hash for tx in list_user_transactions(user_id) if tx.incoming_tx]
        # get an array of the goods and add details from the offer table:
        for good in get_redeemed_items(incoming_txs_hashes):
            # merge two dicts (python 3.5)
            redeemed_goods.append({**good, **get_offer_details(good['offer_id'])})

    except Exception as e:
        print('cant get redeemed items for user')
        print(e)

    return jsonify(status='ok', redeemed=redeemed_goods)


@app.route('/user/onboard', methods=['POST'])
def onboard_user():
    """creates a wallet for the user and deposits some xlms there"""
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
                if tx_id:
                    set_onboarded(user_id, True, public_address)
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
    """ register a user to the system
    called once by every client until 200OK is received from the server.
    the payload may contain a optional push token.

    this function may be called by the client multiple times to update fields
    """
    payload = request.get_json(silent=True)
    try:
        # add redis lock here?
        user_id = payload.get('user_id', None)
        os = payload.get('os', None)
        device_model = payload.get('device_model', None)

        time_zone = payload.get('time_zone', None)
        device_id = payload.get('device_id', None)
        app_ver = payload.get('app_ver', None)
        # optionals
        token = payload.get('token', None)
        screen_h = payload.get('screen_h', None)
        screen_w = payload.get('screen_w', None)
        screen_d = payload.get('screen_d', None)
        package_id = payload.get('package_id', None)
        if None in (user_id, os, device_model, time_zone, app_ver):  # token is optional, device-id is required but may be None
            raise InvalidUsage('bad-request')
        if os not in (utils.OS_ANDROID, utils.OS_IOS):
            raise InvalidUsage('bad-request')
        user_id = UUID(user_id)  # throws exception on invalid uuid
    except Exception as e:
        raise InvalidUsage('bad-request')
    else:
        try:
            new_user_created = create_user(user_id, os, device_model, token,
                        time_zone, device_id, app_ver,
                        screen_w, screen_h, screen_d, package_id)
        except InvalidUsage as e:
            raise InvalidUsage('duplicate-userid')
        else:
            if new_user_created:
                print('created user with user_id %s' % user_id)
                increment_metric('user_registered')
            else:
                print('updated userid %s data' % user_id)

            # return global config - the user doesn't have user-specific config (yet)
            return jsonify(status='ok', config=get_global_config())


def reward_and_push(public_address, task_id, send_push, user_id, memo, tip):
    """create a thread to perform this function in the background"""
    Thread(target=reward_address_for_task_internal, args=(public_address, task_id, send_push, user_id, memo, tip)).start()


def reward_address_for_task_internal(public_address, task_id, send_push, user_id, memo, tip=0):
    """transfer the correct amount of kins for the task to the given address

       this function runs in the background and sends a push message to the client to
       indicate that the money was indeed transferred.
    """
    # get reward amount from db
    amount = get_reward_for_task(task_id)
    if not amount:
        print('could not figure reward amount for task_id: %s' % task_id)
        raise InternalError('cant find reward for task_id %s' % task_id)

    # take into account tipping: reduce the reward of the user by the amount that was tipped
    amount = amount - tip

    try:
        # send the moneys
        print('calling send_kin: %s, %s' % (public_address, amount))
        tx_hash = send_kin(public_address, amount, memo)
    except Exception as e:
        print('caught exception sending %s kins to %s - exception: %s:' % (amount, public_address, e))
        raise InternalError('failed sending %s kins to %s' % (amount, public_address))
    finally:  # TODO dont do this if we fail with the tx
        create_tx(tx_hash, user_id, public_address, False, amount, {'task_id': task_id, 'memo': memo})
        if send_push:
            send_push_tx_completed(user_id, tx_hash, amount, task_id)


@app.route('/offer/add', methods=['POST'])
def add_offer_api():
    """internal endpoint used to populate the server with offers"""
    if not config.DEBUG:
        limit_to_local_host()
    payload = request.get_json(silent=True)
    try:
        offer = payload.get('offer', None)
        set_active = payload.get('set_active', False)  # optional
    except Exception as e:
        print('exception: %s' % e)
        raise InvalidUsage('bad-request')
    if add_offer(offer, set_active):
        return jsonify(status='ok')
    else:
        raise InvalidUsage('failed to add offer')


@app.route('/offer/set_active', methods=['POST'])
def set_active_api():
    """internal endpoint used to enables/disables an offer"""
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
    """books an offer by a user"""
    payload = request.get_json(silent=True)
    try:
        user_id = extract_header(request)
        offer_id = payload.get('id', None)
        if None in (user_id, offer_id):
            raise InvalidUsage('invalid payload')
    except Exception as e:
        raise InvalidUsage('bad-request')

    if config.AUTH_TOKEN_ENFORCED and not is_user_authenticated(user_id):
        print('user %s is not authenticated. rejecting book request' % user_id)
        increment_metric('rejected-on-auth')
        return jsonify(status='error', reason='auth-failed'), status.HTTP_400_BAD_REQUEST

    order_id, error_code = create_order(user_id, offer_id)
    if order_id:
        increment_metric('offers_booked')
        return jsonify(status='ok', order_id=order_id)
    else:
        return jsonify(status='error', reason=errors_to_string(error_code)), status.HTTP_400_BAD_REQUEST


@app.route('/user/offers', methods=['GET'])
def get_offers_api():
    """return the list of availble offers for this user"""
    try:
        user_id = extract_header(request)
        if user_id is None:
            raise InvalidUsage('no user_id')
    except Exception as e:
        print('exception: %s' % e)
        raise InvalidUsage('bad-request')
        #print('offers %s' % get_offers_for_user(user_id))
    return jsonify(offers=get_offers_for_user(user_id))


@app.route('/offer/redeem', methods=['POST'])
def purchase_api():
    """process the given tx_hash and return the payed-for goods"""

    # TODO: at some point we should try to listen in on incoming tx_hashes
    # for our account(s). this should hasten the process of redeeming offers.
    payload = request.get_json(silent=True)
    try:
        user_id = extract_header(request)
        tx_hash = payload.get('tx_hash', None)
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
            print('redeemed order by user_id: %s' % user_id)
            return jsonify(status='ok', goods=goods)
        else:
            return jsonify(status='error', reason='already processing tx_hash')
    finally:
            lock.release()


@app.route('/good/add', methods=['POST'])
def add_good_api():
    """internal endpoint used to populate the server with goods"""
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
    """internal endpoint used to list the goods inventory"""
    if not config.DEBUG:
        limit_to_local_host()
    return jsonify(status='ok', inventory=list_inventory())


@app.route('/stats/db', methods=['GET'])
def dbstats_api():
    """internal endpoint used to retrieve the number of db connections"""
    if not config.DEBUG:
        limit_to_local_host()
    return jsonify(status='ok', stats=sqlalchemy_pool_status())


@app.route('/balance', methods=['GET'])
def balance_api():
    """endpoint used to get the current balance of the seed and channels"""
    if not config.DEBUG:
        limit_to_local_host()

    base_seed, channel_seeds = ssm.get_stellar_credentials()
    balance = {'base_seed': {}, 'channel_seeds': {}}

    from stellar_base.keypair import Keypair
    balance['base_seed']['kin'] = stellar.get_kin_balance(Keypair.from_seed(base_seed).address().decode())
    balance['base_seed']['xlm'] = stellar.get_xlm_balance(Keypair.from_seed(base_seed).address().decode())
    index = 0
    for channel in channel_seeds:
        # seeds only need to carry XLMs
        balance['channel_seeds'][index] = {'xlm': 0}
        balance['channel_seeds'][index]['xlm'] = stellar.get_xlm_balance(Keypair.from_seed(channel).address().decode())
        index = index + 1

    return jsonify(status='ok', balance=balance)


@app.route('/good/release_unclaimed', methods=['GET'])
def release_unclaimed_api():
    """endpoint used to release goods that were booked but never redeemed"""
    if not config.DEBUG:
        limit_to_local_host()
    released = release_unclaimed_goods()
    increment_metric('unclaimed_released', released)
    return jsonify(status='ok', released=released)


@app.route('/engagement/send', methods=['GET'])
def send_engagemnt_api():
    """endpoint used to send engagement push notifications to users by scheme. password protected"""
    if not config.DEBUG:
        limit_to_local_host()

    args = request.args
    scheme = args.get('scheme')
    if scheme is None:
        raise InvalidUsage('invalid param')

    dry_run = args.get('dryrun', 'True') == 'True'

    user_ids = get_users_for_engagement_push(scheme)
    if scheme is None:
        raise InvalidUsage('invalid scheme')

    print('gathered %d ios user_ids and %d gcm user_ids for scheme: %s, dry-run:%s' % (len(user_ids[utils.OS_IOS]), len(user_ids[utils.OS_ANDROID]), scheme, dry_run))

    if dry_run:
        print('send_engagement_api - dry_run - not sending push')
    else:
        print('sending push ios %d tokens' % len(user_ids[utils.OS_IOS]))
        for user_id in user_ids[utils.OS_IOS]:
            send_engagement_push(user_id, scheme)
        print('sending push android %d tokens' % len(user_ids[utils.OS_ANDROID]))
        for user_id in user_ids[utils.OS_ANDROID]:
            send_engagement_push(user_id, scheme)

    return jsonify(status='ok')


@app.route('/user/transaction/p2p', methods=['POST'])
def report_p2p_tx_api():
    """endpoint used by the client to report successful p2p txs"""

    if not config.P2P_TRANSFERS_ENABLED:
        # this api is disabled, clients should not have asked for it
        print('/user/transaction/p2p/add api is disabled by server config')
        raise InvalidUsage('api-disabled')

    payload = request.get_json(silent=True)
    try:
        # TODO Should we verify the tx against the blockchain?
        # TODO this api needs to be secured with auth token
        sender_id = extract_header(request)
        tx_hash = payload.get('tx_hash', None)
        destination_address = payload.get('destination_address', None)
        amount = payload.get('amount', None)
        if None in (tx_hash, sender_id, destination_address, amount):
            raise InvalidUsage('invalid params')

    except Exception as e:
        print('exception: %s' % e)
        raise InvalidUsage('bad-request')
    res, tx_dict = add_p2p_tx(tx_hash, sender_id, destination_address, amount)
    if res:
        # send back the dict with the tx details
        return jsonify(status='ok', tx=tx_dict)
    else:
        raise InvalidUsage('failed to add p2ptx')


@app.route('/users/missing_txs', methods=['GET'])
def fix_users_api():
    """internal endpoint used to list problems with user data"""
    if not config.DEBUG:
        limit_to_local_host()
    missing_txs = find_missing_txs()
    print('missing_txs: found %s items' % len(missing_txs))
    # sort results by date (4th item in each tuple)
    missing_txs.sort(key=lambda tup: tup[3])
    return jsonify(status='ok', missing_txs=missing_txs)


@app.route('/user/compensate', methods=['POST'])
def compensate_user_api():
    """internal endpoint used to manually compensate users for missing txs"""
    limit_to_password()

    payload = request.get_json(silent=True)
    user_id = payload.get('user_id', None)
    kin_amount = int(payload.get('kin_amount', None))
    task_id = payload.get('task_id', None)
    memo = utils.generate_memo(is_manual=True)
    if None in (user_id, kin_amount, task_id):
        raise InvalidUsage('invalid param')
    public_address = get_address_by_userid(user_id)
    if not public_address:
        print('cant compensate user %s - no public address' % user_id)
        return jsonify(status='error', reason='no_public_address')

    user_tx_task_ids = [tx.tx_info.get('task_id', '-1') for tx in list_user_transactions(user_id)]
    if task_id in user_tx_task_ids:
        print('refusing to compensate user %s for task %s - already received funds!' % (user_id, task_id))
        return jsonify(status='error', reason='already_compensated')

    print('calling send_kin: %s, %s' % (public_address, kin_amount))
    try:
        tx_hash = send_kin(public_address, kin_amount, memo)
        create_tx(tx_hash, user_id, public_address, False, kin_amount, {'task_id': task_id, 'memo': memo})
    except Exception as e:
        print('error attempting to compensate user %s for task %s' % (user_id, task_id))
        print(e)
        return jsonify(status='error', reason='internal_error')
    else:
        print('compensated user %s with %s kins for task_id %s' % (user_id, kin_amount, task_id))
        # also send push to the user
        task_title = get_task_details(task_id)['title']
        send_compensated_push(user_id, kin_amount, task_title)

        return jsonify(status='ok', tx_hash=tx_hash)


@app.route('/user/nuke-data', methods=['POST'])
def nuke_user_api():
    """internal endpoint used to nuke a user's task and tx data. use with care"""
    if not config.DEBUG:
        limit_to_local_host()

    try:
        payload = request.get_json(silent=True)
        phone_number = payload.get('phone_number', None)
        nuke_all = payload.get('nuke_all', False) == True
        if None in (phone_number,):
            raise InvalidUsage('bad-request')
    except Exception as e:
        print(e)
        raise InvalidUsage('bad-request')

    user_ids = nuke_user_data(phone_number, nuke_all)
    if user_ids is None:
        print('could not find any user with this number: %s' % phone_number)
        return jsonify(status='error', reason='no_user')
    else:
        print('nuked users with phone number: %s and user_ids %s' % (phone_number, user_ids))
        return jsonify(status='ok', user_id=user_ids)


@app.route('/blackhawk/creds/init', methods=['POST'])
def init_bh_creds_api():
    """internal endpoint used to init blackhawk credentials"""
    if not config.DEBUG:
        limit_to_local_host()

    try:
        payload = request.get_json(silent=True)
        username = payload.get('username', None)
        password = payload.get('password', None)
        account_id = payload.get('account_id', None)
        digital_signature = payload.get('digital_signature', None)
        if None in (username, password, digital_signature, account_id):
            raise InvalidUsage('bad-request')
    except Exception as e:
        print(e)
        raise InvalidUsage('bad-request')

    from .blackhawk import refresh_bh_auth_token
    init_bh_creds(account_id, username, password, digital_signature)
    refresh_bh_auth_token(force=True)

    return jsonify(status='ok')


@app.route('/blackhawk/offers/add', methods=['POST'])
def add_bh_offer_api():
    """adds a blackhawk offer to the db. the offer_id must already exist in the offers table"""
    if not config.DEBUG:
        limit_to_local_host()

    try:
        payload = request.get_json(silent=True)
        offer_id = payload.get('offer_id', None)
        merchant_code = payload.get('merchant_code', None)
        merchant_template_id = payload.get('merchant_template_id', None)
        batch_size = payload.get('batch_size', None)
        denomination = payload.get('denomination', None)
        minimum_threshold = payload.get('minimum_threshold', None)
        if None in (offer_id, merchant_code, merchant_template_id, batch_size, denomination, minimum_threshold):
            raise InvalidUsage('bad-request')
    except Exception as e:
        print(e)
        raise InvalidUsage('bad-request')

    if create_bh_offer(offer_id, merchant_code, merchant_template_id, batch_size, denomination, minimum_threshold):
        return jsonify(status='ok')
    else:
        raise InvalidUsage('failed to add blackhawk offer')


@app.route('/blackhawk/account/balance', methods=['GET'])
def get_bh_balance():
    """returns the current balance of the bh account"""
    if not config.DEBUG:
        limit_to_local_host()

    if not config.BLACKHAWK_PURCHASES_ENABLED:
        print('blackhawk purchases disabled by config. ignoring cron')
        return jsonify(status='ok', balance=-1)

    from .blackhawk import get_account_balance
    return jsonify(status='ok', balance=get_account_balance())


@app.route('/blackhawk/cards/replenish', methods=['POST'])
def replenish_bh_cards_endpoint():
    """buy additional cards from blackhawk if below threshold"""
    if not config.DEBUG:
        limit_to_local_host()

    from .blackhawk import replenish_bh_cards, refresh_bh_auth_token
    if not config.BLACKHAWK_PURCHASES_ENABLED:
        print('blackhawk purchases disabled by config. ignoring cron')
        return jsonify(status='ok')

    refresh_bh_auth_token()

    # buys cards if needed
    retval = replenish_bh_cards()
    if retval > 0:
        return jsonify(status='ok', unprocessed_orders=retval)
    else:
        return jsonify(status='error')


@app.route('/task/results', methods=['POST'])
def post_task_results_endpoint():
    """an endpoint that can be used to return task results for bi"""
    limit_to_password()

    try:
        payload = request.get_json(silent=True)
        task_id = payload.get('task_id', None)
        if task_id is None:
            raise InvalidUsage('bad-request')
    except Exception as e:
        print(e)
        raise InvalidUsage('bad-request')

    return jsonify(status='ok', results=get_task_results(task_id))


@app.route('/user/report', methods=['POST'])
def user_report_endpoint():
    """returns a summary of the user's data"""
    limit_to_password()

    try:
        payload = request.get_json(silent=True)
        user_id = payload.get('user_id', None)
        if user_id is None:
            raise InvalidUsage('bad-request')
    except Exception as e:
        print(e)
        raise InvalidUsage('bad-request')

    # sanitize user_id:
    try:
        UUID(user_id)
    except Exception as e:
        print('cant generate report for user_id: %s ' % user_id)
        return jsonify(error='invalid_userid')

    if not user_exists(user_id):
        print('user_report_endpoint: user_id %s does not exist. aborting' % user_id)
        return jsonify(erorr='no_such_user')

    return jsonify(report=get_user_report(user_id))


@app.route('/auth/retarget', methods=['POST'])
def retarget_auth_endpoint():
    """re-send auth push tokens for users that have not answered"""
    limit_to_local_host()

    user_ids = generate_retarget_list()
    print('re-sending auth token to %s users' % len(user_ids))
    for user_id in user_ids:
        print('user_id: %s' % user_id)
        send_push_auth_token(user_id, force_send=True)

    return jsonify(status='ok')


@app.route('/truex/activity', methods=['GET'])
def truex_activity_endpoint():
    """returns a truex activity for the requesting user, provided this user is allowed to get one now:
       meaning that her current task is of type truex and the submission time was met"""
    try:
        remote_ip = request.headers.get('X-Forwarded-For', None)
        user_id = extract_header(request)
        if user_id is None:
            raise InvalidUsage('no user_id')
        if remote_ip is None:
            print('truex_activity_endpoint - should never happen - cant get remote ip for client')
            raise InvalidUsage('no remote_ip')
        user_agent = request.args.get('user-agent', None)  # optional
    except Exception as e:
        print('exception: %s' % e)
        raise InvalidUsage('bad-request')

    if config.AUTH_TOKEN_ENFORCED and not is_user_authenticated(user_id):
        print('user %s is not authenticated. rejecting truex-activity request' % user_id)
        increment_metric('rejected-on-auth')
        return jsonify(status='error', reason='auth-failed'), status.HTTP_400_BAD_REQUEST

    activity = get_truex_activity(user_id, remote_ip, user_agent)
    if not activity:
        print('userid %s failed to get a truex activity' % user_id)
        return jsonify(status='error', reason='no_activity')
    return jsonify(status='ok', activity=activity)


TRUEX_CALLBACK_RECOVERABLE_ERROR = '0'
TRUEX_CALLBACK_PROCESSED = '1'
TRUEX_CALLBACK_BAD_SIG = '2'
TRUEX_CALLBACK_DUP_ENGAGEMENT_ID = '3'
TRUEX_ENG_UNIQUENESS_TTL_SEC = 60*60*24*10 # 10 days

TRUEX_SERVERS_ADRESSES = ['8.3.218.160', '8.3.218.161', '8.3.218.162', '8.3.218.163', '8.3.218.164', '8.3.218.165',
                          '8.3.218.166', '8.3.218.167', '8.3.218.168', '8.3.218.169', '8.3.218.170', '8.3.218.171',
                          '8.3.218.172', '8.3.218.173', '8.3.218.174', '8.3.218.175', '8.3.218.176', '8.3.218.177',
                          '8.3.218.178', '8.3.218.179', '8.3.218.181', '8.3.218.182', '8.3.218.183', '8.3.218.184',
                          '8.3.218.185', '8.3.218.186', '8.3.218.187', '8.3.218.188', '8.3.218.189', '8.3.218.190',
                          '184.73.184.219', '184.73.184.220', '184.73.184.224', '184.73.184.229', '184.73.184.233',
                          '174.129.192.205', '174.129.193.108', '174.129.195.123', '174.129.195.144', '174.129.34.246',
                          '184.73.195.45', '184.73.195.48', '184.73.195.50', '184.73.195.87', '204.236.224.121', '204.236.224.129',
                          '204.236.224.49', '204.236.225.149', '204.236.225.17', '204.236.225.63', '50.16.244.72', '50.16.245.107',
                          '50.16.245.109', '50.16.245.111', '50.16.245.33']


@app.route('/truex/callback', methods=['GET'])
def truex_callback_endpoint():
    """called by truex whenever an activity was completed.

    This endpoint triggers the sequence that leads to the user
    getting payed for his truex task.

    -this request can only arrive from a set of specific ips
    and contains a signature that must be authenticated before the request is processed,
    as per Truex's API doc.

    in addition, the request contains an engagement_id which must be checked for uniqueness
    to prevent over-crediting our users.

    the request must return an appropriate response code, as follows:
        0  – Recoverable failure (request will be retried)
        1  – Callback successfully processed
        2  – Invalid signature (this will notify  true[ X ]  for investigation)
        3  – Invalid user or duplicate engagement_id (request will not be retried)

    """
    args = request.args
    network_user_id = args.get('network_user_id')
    eng_id = args.get('engagement_id', None)

    # translate network_user_id to user_id
    user_id = str(get_user_id_by_truex_user_id(network_user_id))

    # allow easy simulation of the callback in stage
    if config.DEBUG and args.get('skip_callback_processing', False):
        print('skipping truex callback processing - compensating debug user %s' % user_id)
        compensate_truex_activity(user_id)
        return TRUEX_CALLBACK_PROCESSED

    try:
        # ensure acl:
        remote_ip = request.headers.get('X-Forwarded-For', None)
        if config.DEBUG and remote_ip is None:
            remote_ip = '50.16.245.33'  # hard-coded ip from the truex list
            print('truex_callback_endpoint: overwriting remote ip for DEBUG to %s' % remote_ip)
        if remote_ip not in TRUEX_SERVERS_ADRESSES:
            # just return whatever. this isn't from truex
            print('truex_callback_endpoint: got request from %s, which isn\'t in the acl. ignoring request' % remote_ip)
            return TRUEX_CALLBACK_RECOVERABLE_ERROR

        # validate sig
        from .truex import verify_sig
        if not verify_sig(args):
            print('truex_callback_endpoint: failed to authenticate request from truex')
            return TRUEX_CALLBACK_BAD_SIG

        # ensure eng_id uniqueness with ttl
        if not app.redis.set('truex-%s' % eng_id, 1, nx=True, ex=TRUEX_ENG_UNIQUENESS_TTL_SEC):
            # dup eng_id
            print('truex_callback_endpoint: detected duplicate eng-id. ignoring request')
            return TRUEX_CALLBACK_DUP_ENGAGEMENT_ID

        # okay. pay the user
        # translate truex user-string to user_id

        print('paying user %s for truex activity' % user_id)
        res = compensate_truex_activity(user_id)
        if not res:
            print('failed to pay user %s for truex activity' % user_id)
        # process request
    except Exception as e:
        print('unhandled exception in truex process. exception: %s' % e)
        return TRUEX_CALLBACK_RECOVERABLE_ERROR

    return TRUEX_CALLBACK_PROCESSED


def compensate_truex_activity(user_id):
    """pay a user for her truex activity

    this function has a lot of duplicate code from post_user_task_results_endpoint
    """
    if not user_exists(user_id):
        print('compensate_truex_activity. user_id %s does not exist. aborting' % user_id)
        return False

    if config.PHONE_VERIFICATION_REQUIRED and not is_user_phone_verified(user_id):
        print('blocking user (%s) results - didnt pass phone_verification' % user_id)
        return jsonify(status='error', reason='user_phone_not_verified'), status.HTTP_400_BAD_REQUEST

    if user_deactivated(user_id):
        print('user %s deactivated. rejecting submission' % user_id)
        return jsonify(status='error', reason='user_deactivated'), status.HTTP_400_BAD_REQUEST

    if reject_premature_results(user_id):
        print('compensate_truex_activity: should never happen - premature task submission')
        return False

    # get the user's current task_id
    tasks = get_tasks_for_user(user_id)
    if len(tasks) == 0:
        print('compensate_truex_activity: should never happen - user doesnt have any tasks')
        return False
    else:
        task_id = tasks[0]['id']
    print('compensate_truex_activity: current task_id: %s' % task_id)

    memo, compensated_user_id = handle_task_results_resubmission(user_id, task_id)
    if memo:
        print('compensate_truex_activity: detected resubmission of previously payed-for task by user_id: %s. memo:%s' % (compensated_user_id, memo))
        # this task was already submitted - and compensated, so just re-return the memo to the user.
        return True

    # store some fake results as this task doesn't have any
    if not store_task_results(user_id, task_id, [{'aid': '0', 'qid': '0'}]):
            raise InternalError('cant save results for user_id %s' % user_id)
    try:
        memo = get_and_replace_next_task_memo(user_id)
        address = get_address_by_userid(user_id)
        reward_and_push(address, task_id, False, user_id, memo, tip=0)
    except Exception as e:
        print('failed to reward truex task %s at address %s for user_id %s. exception: %s' % (task_id, address, user_id, e))
        raise(e)

    increment_metric('task_completed')
    return True


@app.route('/users/deauth', methods=['GET'])
def deauth_users_endpoint():
    """disables users that were sent an auth token but did not ack it in time"""
    scan_for_deauthed_users()
    return jsonify(status='ok')


@app.route('/users/push_register', methods=['POST'])
def push_register_endpoint():
    """ask a set of userids to re-register via push"""
    limit_to_password()

    try:
        payload = request.get_json(silent=True)
        user_ids = payload.get('user_ids', [])
    except Exception as e:
        print(e)
        raise InvalidUsage('bad-request')
    else:
        for user_id in user_ids:
            send_push_register(user_id)

    return jsonify(status='ok')
