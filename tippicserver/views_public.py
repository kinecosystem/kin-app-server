"""
The Kin App Server public API is defined here.
"""
from threading import Thread
from uuid import UUID

from flask import request, jsonify, abort
from tippicserver.views_common import get_source_ip, extract_headers, limit_to_acl
from flask_api import status
import redis_lock
import arrow
import logging as log
from distutils.version import LooseVersion
from .utils import OS_ANDROID, OS_IOS, random_percent, passed_captcha

from tippicserver import app, config, stellar, utils, ssm
from tippicserver.stellar import create_account, send_kin, send_kin_with_payment_service
from tippicserver.utils import InvalidUsage, InternalError, errors_to_string, increment_metric, gauge_metric, MAX_TXS_PER_USER, extract_phone_number_from_firebase_id_token,\
    sqlalchemy_pool_status, get_global_config, write_payment_data_to_cache, read_payment_data_from_cache
from tippicserver.models import create_user, update_user_token, update_user_app_version, is_onboarded, set_onboarded,\
    create_tx, list_user_transactions, \
    add_p2p_tx, set_user_phone_number, match_phone_number_to_address, user_deactivated,\
    get_address_by_userid, list_p2p_transactions_for_user_id, nuke_user_data, ack_auth_token,\
    is_user_authenticated, is_user_phone_verified, get_user_config, get_user_report,\
    scan_for_deauthed_users, user_exists, is_in_acl,\
    get_email_template_by_type, get_unauthed_users, get_all_user_id_by_phone, get_backup_hints, generate_backup_questions_list, store_backup_hints, \
    validate_auth_token, restore_user_by_address, get_unenc_phone_number_by_user_id, update_tx_ts, \
    should_block_user_by_client_version, deactivate_user, get_user_os_type, should_block_user_by_phone_prefix, count_registrations_for_phone_number, \
    update_ip_address, should_block_user_by_country_code, is_userid_blacklisted, should_allow_user_by_phone_prefix, should_pass_captcha, \
    captcha_solved, get_user_tz, do_captcha_stuff, \
    should_force_update, is_update_available


def get_payment_lock_name(user_id, task_id):
    """generate a user and task specific lock for payments."""
    return "pay:%s-%s" % (user_id, task_id)


@app.route('/user/app-launch', methods=['POST'])
def app_launch():
    """called whenever the app is launched

        updates the user's last-login time,
        also forwards some config items to the client
    """
    payload = request.get_json(silent=True)
    app_ver, user_id = None, None
    try:
        user_id, auth_token = extract_headers(request)
        app_ver = payload.get('app_ver', None)
    except Exception as e:
        raise InvalidUsage('bad-request')

    update_ip_address(user_id, get_source_ip(request))

    update_user_app_version(user_id, app_ver)

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
        user_id, auth_token = extract_headers(request)
        phone_number = payload.get('phone_number', None)
        if None in (user_id, phone_number):
            raise InvalidUsage('bad-request')
    except Exception as e:
        print(e)
        raise InvalidUsage('bad-request')

    if is_userid_blacklisted(user_id):
        print('blocked user_id %s from matching p2p - user_id blacklisted' % user_id)
        return jsonify(status='error', reason='no_match'), status.HTTP_404_NOT_FOUND

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
        user_id, auth_token = extract_headers(request)
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
def set_user_phone_number_endpoint():
    """get the firebase id token and extract the phone number from it"""
    payload = request.get_json(silent=True)
    try:
        user_id, auth_token = extract_headers(request)
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

        # reject blacklisted phone prefixes
        for prefix in app.blocked_phone_prefixes:
            if verified_number.find(prefix) == 0:
                os_type = get_user_os_type(user_id)
                print('found blocked phone prefix (%s) in verified phone number (%s), userid (%s), OS (%s): aborting' % (prefix, verified_number, user_id, os_type))
                abort(403)

        phone = verified_number
    else: #DEBUG
        # for tests, you can use the unverified number if no token was given
        if token:
            phone = extract_phone_number_from_firebase_id_token(token)

        if not phone:
            print('using un-verified phone number in debug')
            phone = unverified_phone_number.strip().replace('-', '')

        if not phone:
            print('could not extract phone in debug')
            return jsonify(status='error', reason='no_phone_number')

    # limit the number of registrations a single phone number can do, unless they come from the ACL
    if not limit_to_acl(return_bool=True) and count_registrations_for_phone_number(phone) > int(config.MAX_NUM_REGISTRATIONS_PER_NUMBER) - 1:
        print('rejecting registration from user_id %s and phone number %s - too many re-registrations' % (user_id, phone))
        increment_metric("reject-too-many_registrations")
        abort(403)

    print('updating phone number for user %s' % user_id)
    set_user_phone_number(user_id, phone)
    increment_metric('user-phone-verified')

    # return success and the backup hint, if they exist
    hints = get_backup_hints(user_id)
    if config.DEBUG:
        print('restore hints for user_id, phone: %s: %s: %s' % (user_id, phone, hints))
    return jsonify(status='ok', hints=hints)


@app.route('/user/push/update-token', methods=['POST'])
def update_token_api_old():
    """updates a user's token in the database """
    payload = request.get_json(silent=True)
    try:
        user_id, auth_token = extract_headers(request)
        token = payload.get('token', None)
        if None in (user_id, token):
            raise InvalidUsage('bad-request')
    except Exception as e:
        print(e)
        raise InvalidUsage('bad-request')

    lock = redis_lock.Lock(app.redis, 'update_token:%s' % user_id)
    if lock.acquire(blocking=False):
        try:
            print('updating token for user %s to %s' % (user_id, token))
            update_user_token(user_id, token)

        except Exception as e:
            print('exception trying to update token for user_id %s with token: %s. exception: %s' % (user_id, token, e))
            return jsonify(status='error'), status.HTTP_400_BAD_REQUEST
        finally:
            lock.release()

    else:
        print('already updating token for user %s. ignoring request' % user_id)

    return jsonify(status='ok')


@app.route('/user/update-token', methods=['POST'])
def update_token_api():
    """updates a user's token in the database """
    payload = request.get_json(silent=True)
    try:
        user_id, auth_token = extract_headers(request)
        token = payload.get('token', None)
        if None in (user_id, token):
            raise InvalidUsage('bad-request')
    except Exception as e:
        print(e)
        raise InvalidUsage('bad-request')

    lock = redis_lock.Lock(app.redis, 'update_token:%s' % user_id)
    if lock.acquire(blocking=False):
        try:
            print('updating token for user %s' % user_id)
            update_user_token(user_id, token)

        except Exception as e:
            print('exception trying to update token for user_id %s' % user_id)
            return jsonify(status='error'), status.HTTP_400_BAD_REQUEST
        finally:
            lock.release()

    else:
        print('already updating token for user %s. ignoring request' % user_id)

    return jsonify(status='ok')


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
        user_id, auth_token = extract_headers(request)
        server_txs = [{'type': 'server', 'tx_hash': tx.tx_hash, 'amount': tx.amount, 'client_received': not tx.incoming_tx, 'tx_info': tx.tx_info, 'date': arrow.get(tx.update_at).timestamp} for tx in list_user_transactions(user_id, MAX_TXS_PER_USER)]

        # get the offer, task details
        for tx in server_txs:
            details = get_offer_details(tx['tx_info']['offer_id']) if not tx['client_received'] else get_task_details(tx['tx_info']['task_id'])
            detailed_txs.append({**tx, **details})

        # get p2p details
        import emoji
        kin_from_a_friend_text=emoji.emojize(':party_popper: Kin from a friend')
        p2p_txs = [{'title': kin_from_a_friend_text if str(tx.receiver_user_id).lower() == str(user_id).lower() else 'Kin to a friend',
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
        detailed_txs = sorted(detailed_txs, key=lambda k: k['date'], reverse=True)
        if len(detailed_txs) > MAX_TXS_PER_USER:
            detailed_txs = detailed_txs[:MAX_TXS_PER_USER]

    except Exception as e:
        log.error('cant get txs for user')
        print(e)
        return jsonify(status='error', txs=[])

    return jsonify(status='ok', txs=detailed_txs)



@app.route('/user/onboard', methods=['POST'])
def onboard_user():
    """creates a wallet for the user and deposits some xlms there"""
    # input sanity
    try:
        user_id, auth_token = extract_headers(request)
        public_address = request.get_json(silent=True).get('public_address', None)
        if None in (public_address, user_id):
            raise InvalidUsage('bad-request')
    except Exception as e:
        raise InvalidUsage('bad-request')

    # block users with an older version from onboarding. and send them a push message
    if should_block_user_by_client_version(user_id):
        print('blocking + deactivating user %s on onboarding with older version and sending push' % user_id)
        # send_please_upgrade_push_2([user_id])
        # and also, deactivate the user
        deactivate_user(user_id)

        abort(403)
    elif config.PHONE_VERIFICATION_REQUIRED and not is_user_phone_verified(user_id):
        raise InvalidUsage('user isnt phone verified')

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
        package_id = payload.get('package_id', None)
        if None in (user_id, os, device_model, time_zone, app_ver):  # token is optional, device-id is required but may be None
            raise InvalidUsage('bad-request')

        if os not in (utils.OS_ANDROID, utils.OS_IOS):
            raise InvalidUsage('bad-request')

        if 'Genymotion'.upper() in device_model.upper(): # block android emulator
            print('refusing to register Genymotion devices. user_id %s' % user_id)
            raise InvalidUsage('bad-request')

        user_id = UUID(user_id)  # throws exception on invalid uuid
    except Exception as e:
        raise InvalidUsage('bad-request')
    else:
        try:
            new_user_created = create_user(user_id, os, device_model, token,
                        time_zone, device_id, app_ver, package_id)
        except InvalidUsage as e:
            raise InvalidUsage('duplicate-userid')
        else:
            if new_user_created:
                print('created user with user_id %s' % user_id)
                increment_metric('user_registered')
            else:
                print('updated userid %s data' % user_id)

            #TODO find a way to dry up this code which is redundant with get_user_config()

            # turn off phone verfication for older clients:
            disable_phone_verification = False
            disable_backup_nag = False
            if os == OS_ANDROID and LooseVersion(app_ver) <= LooseVersion(config.BLOCK_ONBOARDING_ANDROID_VERSION):
                    disable_phone_verification = True
                    disable_backup_nag = True
            elif os == OS_IOS and LooseVersion(app_ver) <= LooseVersion(config.BLOCK_ONBOARDING_IOS_VERSION):
                    disable_phone_verification = True
                    disable_backup_nag = True

            global_config = get_global_config()
            if disable_phone_verification:
                print('disabling phone verification for registering userid %s' % user_id)
                global_config['phone_verification_enabled'] = False
            if disable_backup_nag:
                print('disabling backup nag for registering userid %s' % user_id)
                global_config['backup_nag'] = False

            if should_force_update(os, app_ver):
                global_config['force_update'] = True

            if is_update_available(os, app_ver):
                global_config['is_update_available'] = True


            # return global config - the user doesn't have user-specific config (yet)
            return jsonify(status='ok', config=global_config)


# def reward_and_push(public_address, task_id, send_push, user_id, memo, delta):
#     """create a thread to perform this function in the background"""
#     Thread(target=reward_address_for_task_internal, args=(public_address, task_id, send_push, user_id, memo, delta)).start()
#
#
# def reward_address_for_task_internal(public_address, task_id, send_push, user_id, memo, delta=0):
#     """transfer the correct amount of kins for the task to the given address
#
#        this function runs in the background and sends a push message to the client to
#        indicate that the money was indeed transferred.
#
#        typically, tips are negative delta and quiz-results are positive delta
#     """
#     # get reward amount from db
#     amount = get_reward_for_task(task_id)
#     if not amount:
#         print('could not figure reward amount for task_id: %s' % task_id)
#         raise InternalError('cant find reward for task_id %s' % task_id)
#
#     # take into account the delta: add or reduce kins from the amount
#     amount = amount + delta
#
#     try:
#         # send the moneys
#         print('calling send_kin: %s, %s' % (public_address, amount))
#         tx_hash = send_kin(public_address, amount, memo)
#         create_tx(tx_hash, user_id, public_address, False, amount, {'task_id': task_id, 'memo': memo})
#     except Exception as e:
#         print('caught exception sending %s kins to %s - exception: %s:' % (amount, public_address, e))
#         increment_metric('outgoing_tx_failed')
#         raise InternalError('failed sending %s kins to %s' % (amount, public_address))
#     finally:  # TODO dont do this if we fail with the tx
#         if tx_hash and send_push:
#             send_push_tx_completed(user_id, tx_hash, amount, task_id, memo)
#         try:
#             redis_lock.Lock(app.redis, get_payment_lock_name(user_id, task_id)).release()
#         except Exception as e:
#             log.error('failed to release payment lock for user_id %s and task_id %s' % (user_id, task_id))
#
#
#
# def reward_address_for_task_internal_payment_service(public_address, task_id, send_push, user_id, memo, delta=0):
#     """transfer the correct amount of kins for the task to the given address using the payment service.
#        the payment service is async and calls a callback when its done. the tx is written into the db
#        in the callback function.
#
#        typically, tips are negative delta and quiz-results are positive delta
#     """
#     memo = memo[6:]  # trim down the memo because the payment service adds the '1-kit-' bit.
#     # get reward amount from db
#     amount = get_reward_for_task(task_id)
#     if not amount:
#         print('could not figure reward amount for task_id: %s' % task_id)
#         raise InternalError('cant find reward for task_id %s' % task_id)
#
#     # take into account the delta: add or reduce kins from the amount
#     amount = amount + delta
#     write_payment_data_to_cache(memo, user_id, task_id, arrow.utcnow().timestamp,send_push)  # store this info in cache for when the callback is called
#     print('calling send_kin with the payment service: %s, %s' % (public_address, amount))
#     # sends a request to the payment service. result comes back via a callback
#     send_kin_with_payment_service(public_address, amount, memo)


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
        sender_id, auth_token = extract_headers(request)
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
        increment_metric('p2p-tx-added')
        return jsonify(status='ok', tx=tx_dict)
    else:
        raise InvalidUsage('failed to add p2ptx')


@app.route('/backup/hints', methods=['GET'])
def get_back_questions_endpoint():
    """return a dict of the backup questions"""
    return jsonify(hints=generate_backup_questions_list())


@app.route('/user/ui-alerts', methods=['GET'])
def get_ui_alerts_endpoint():
    """return a dict of the backup questions"""
    alerts = [{"type": "backup_nag", "text": "please use our amazing backup mechanism please. lorem ipsum est dolour"}]
    return jsonify(status='ok', alerts=alerts)


@app.route('/user/email_backup', methods=['POST'])
def email_backup_endpoint():
    """generates an email with the user's backup details and sends it"""
    user_id, auth_token = extract_headers(request)
    if config.AUTH_TOKEN_ENFORCED and not validate_auth_token(user_id, auth_token):
        print('received a bad auth token from user_id %s: %s. ignoring for now' % (user_id, auth_token))
    if config.AUTH_TOKEN_ENFORCED and not is_user_authenticated(user_id):
        abort(403)
    try:
        payload = request.get_json(silent=True)
        to_address = payload.get('to_address', None)
        enc_key = payload.get('enc_key', None)
        if None in (to_address, enc_key):
            raise InvalidUsage('bad-request')
        # TODO validate email address is legit
    except Exception as e:
        print(e)
        raise InvalidUsage('bad-request')

    #get_template from db, generate email and send with ses
    from .models.email_template import EMAIL_TEMPLATE_BACKUP_NAG_1
    template_dict = get_email_template_by_type(EMAIL_TEMPLATE_BACKUP_NAG_1)
    if not template_dict:
        raise InternalError('cant fetch email template')

    from .send_email import send_mail_with_qr_attachment
    try:
        res = send_mail_with_qr_attachment(
            template_dict['sent_from'],
            [to_address],
            template_dict['title'],
            template_dict['body'],
            enc_key)
        print('email result: %s' % res)
        increment_metric('backup-email-sent-success')
    except Exception as e:
        log.error('failed to sent backup email to %s. e:%s' % (to_address, e))
        increment_metric('backup-email-sent-failure')
    #TODO handle errors

    return jsonify(status='ok')


@app.route('/user/backup/hints', methods=['POST'])
def post_backup_hints_endpoint():
    """store the user's backup hints"""
    user_id, auth_token = extract_headers(request)
    if config.AUTH_TOKEN_ENFORCED and not validate_auth_token(user_id, auth_token):
        print('received a bad auth token from user_id %s: %s. ignoring for now' % (user_id, auth_token))
    if config.AUTH_TOKEN_ENFORCED and not is_user_authenticated(user_id):
        abort(403)
    try:
        payload = request.get_json(silent=True)
        hints = payload.get('hints', None)
        if None in (user_id, hints):
            raise InvalidUsage('bad-request')
        if hints == []:
            raise InvalidUsage('bad-request')
    except Exception as e:
        print(e)
        raise InvalidUsage('bad-request')
    else:
        if store_backup_hints(user_id, hints):
            return jsonify(status='ok')
        else:
            raise InvalidUsage('cant store ')


@app.route('/user/restore', methods=['POST'])
def post_backup_restore():
    """restore the user to the one with the previous private address

    this api is protected by the following means:
     - a phone number can only restore if a previous back was performed
     - a phone number can only restore to a previously owned address
    """
    user_id, auth_token = extract_headers(request)
    #TODO consider adding this if it doesn't break anything
    #if config.AUTH_TOKEN_ENFORCED and not validate_auth_token(user_id, auth_token):
    #    abort(403) #
    try:
        payload = request.get_json(silent=True)
        address = payload.get('address', None)
        if address is None:
            raise InvalidUsage('bad-request')
    except Exception as e:
        print(e)
        raise InvalidUsage('bad-request')
    else:
        user_id = restore_user_by_address(user_id, address)
        if user_id:
            increment_metric('restore-success')
            return jsonify(status='ok', user_id=user_id)
        else:
            increment_metric('restore-failure')
            raise InvalidUsage('cant restore user')


@app.route('/blacklist/areacodes', methods=['GET'])
def get_blacklist_areacodes_endpoint():
    """returns a list of blacklisted areacodes"""
    return jsonify(areacodes=app.blocked_phone_prefixes)


@app.route('/payments/callback', methods=['POST'])
def payment_service_callback_endpoint():
    """an endpoint for the payment service."""
    payload = request.get_json(silent=True)
    print(payload) #TODO remove eventually

    try:
        action = payload.get('action', None)
        obj = payload.get('object', None)
        state = payload.get('state', None)
        val = payload.get('value', None)

        if None in (action, obj, state, val):
            print('should never happen: cant process payment service callback: %s' % payload)
            increment_metric('payment-callback-error')
            return jsonify(status='error', reason='internal_error')

        #  process payment:
        if action == 'send' and obj == 'payment':
            if state == 'success':
                memo = val.get('id', None)
                tx_hash = val.get('transaction_id', None)
                amount = val.get('amount', None)
                payment_ts = payload.get('timestamp', None)
                public_address = val.get('sender_address')
                if None in (memo, tx_hash, amount):
                    print('should never happen: cant process successful payment callback: %s' % payload)
                    increment_metric('payment-callback-error')
                    return jsonify(status='error', reason='internal_error')

                # retrieve the user_id and task_id from the cache
                user_id, task_id, request_timestamp, send_push = read_payment_data_from_cache(memo)

                # compare the timestamp from the callback with the one from the original request, and
                # post as a gauge  metric for tracking
                try:
                    request_duration_sec = arrow.get(payment_ts) - arrow.get(request_timestamp)
                    request_duration_sec = int(request_duration_sec.total_seconds())
                    print('payment request for tx_hash: %s took %s seconds' % (tx_hash, request_duration_sec))
                    gauge_metric('payment-req-dur', request_duration_sec)
                except Exception as e:
                    log.error('failed to calculate payment request duration. e=%s' % e)

                # slap the '1-kit' on the memo
                memo = '1-kit-%s' % memo

                create_tx(tx_hash, user_id, public_address, False, amount, {'task_id': task_id, 'memo': memo})
                increment_metric('payment-callback-success')
                #
                # if tx_hash and send_push:
                #     send_push_tx_completed(user_id, tx_hash, amount, task_id, memo)

                try:
                    redis_lock.Lock(app.redis, get_payment_lock_name(user_id, task_id)).release()
                except Exception as e:
                    log.error('failed to release payment lock for user_id %s and task_id %s' % (user_id, task_id))

            else:
                print('received failed tx from the payment service: %s' % payload)
                #TODO implement some retry mechanism here
                increment_metric('payment-callback-failed')
        else:
            print('should never happen: unhandled callback from the payment service: %s' % payload)

    except Exception as e:

        increment_metric('payment-callback-error')
        log.error('failed processing the payment service callback')
        print(e)
        return jsonify(status='error', reason='internal_error')

    return jsonify(status='ok')
