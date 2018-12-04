"""
The Kin App Server private API is defined here.
"""
from uuid import UUID

from flask import request, jsonify, abort

from tippicserver.views_common import limit_to_acl, limit_to_localhost, limit_to_password, get_source_ip, extract_headers

from tippicserver import app, config, stellar, utils, ssm
from .push import send_please_upgrade_push_2
from tippicserver.stellar import create_account, send_kin, send_kin_with_payment_service
from tippicserver.utils import InvalidUsage, InternalError, errors_to_string, increment_metric, gauge_metric, MAX_TXS_PER_USER, extract_phone_number_from_firebase_id_token,\
    sqlalchemy_pool_status, get_global_config, write_payment_data_to_cache, read_payment_data_from_cache
from tippicserver.models import create_user, update_user_token, update_user_app_version, \
    is_onboarded, set_onboarded, send_push_tx_completed, send_engagement_push, \
    create_tx,list_user_transactions,\
    add_p2p_tx, set_user_phone_number, match_phone_number_to_address, user_deactivated,\
    get_address_by_userid, send_compensated_push,\
    list_p2p_transactions_for_user_id, nuke_user_data, send_push_auth_token, ack_auth_token, is_user_authenticated, is_user_phone_verified,\
    get_user_config, get_user_report, get_user_tx_report,\
    scan_for_deauthed_users, user_exists, send_push_register, is_in_acl,\
    get_email_template_by_type, get_unauthed_users, get_all_user_id_by_phone, get_backup_hints, generate_backup_questions_list, store_backup_hints, \
    validate_auth_token, restore_user_by_address, get_unenc_phone_number_by_user_id, update_tx_ts, \
    should_block_user_by_client_version, deactivate_user, get_user_os_type, should_block_user_by_phone_prefix, delete_all_user_data, count_registrations_for_phone_number, \
    blacklist_phone_number, blacklist_phone_by_user_id, migrate_restored_user_data, re_register_all_users, get_tx_totals, set_should_solve_captcha, \
    set_update_available_below, set_force_update_below


@app.route('/health', methods=['GET'])
def get_health():
    """health endpoint"""
    return jsonify(status='ok')


@app.route('/user/data/delete', methods=['POST'])
def delete_user_data_endpoint():
    """endpoint used to delete all of a users data"""
    #disabling this function as its too risky
    abort(403)
    if not config.DEBUG:
        limit_to_localhost()

    payload = request.get_json(silent=True)
    user_id = payload.get('user_id', None)
    are_u_sure = payload.get('are_u_sure', False)
    delete_all_user_data(user_id, are_u_sure)
    return jsonify(status='ok')


@app.route('/push/please_upgrade', methods=['POST'])
def push_please_upgrade_api():
    """sends a please-upgrade message to the given user_ids"""
    # TODO REMOVE ME
    if not config.DEBUG:
        limit_to_localhost()

    payload = request.get_json(silent=True)
    try:
        user_ids = payload.get('user_ids', None)
    except Exception as e:
        print('exception: %s' % e)
        raise InvalidUsage('bad-request')

    send_please_upgrade_push_2(user_ids)
    return jsonify(status='ok')


@app.route('/stats/db', methods=['GET'])
def dbstats_api():
    """internal endpoint used to retrieve the number of db connections"""
    if not config.DEBUG:
        limit_to_localhost()

    return jsonify(status='ok', stats=sqlalchemy_pool_status()) # cant be async, used by the reboot script


@app.route('/balance', methods=['GET'])
def balance_api():
    """endpoint used to get the current balance of the seed and channels"""
    if not config.DEBUG:
        limit_to_localhost()

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


@app.route('/user/nuke-data', methods=['POST'])
def nuke_user_api():
    """internal endpoint used to nuke a user's task and tx data. use with care"""
    if not config.DEBUG:
        limit_to_acl()
        limit_to_password()

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


@app.route('/user/txs/report', methods=['POST'])
def user_tx_report_endpoint():
    """returns a summary of the user's txs data"""
    limit_to_acl()
    limit_to_password()

    try:
        payload = request.get_json(silent=True)
        user_id = payload.get('user_id', None)
        user_phone = payload.get('phone', None)
        if (user_id is None and user_phone is None) or (user_id is not None and user_phone is not None):
            print('user_tx_report_endpoint: userid %s, user_phone %s' % (user_id, user_phone))
            raise InvalidUsage('bad-request')
    except Exception as e:
        print(e)
        raise InvalidUsage('bad-request')

    try:  # sanitize user_id:
        if user_id:
            UUID(user_id)
    except Exception as e:
        log.error('cant generate tx report for user_id: %s ' % user_id)
        return jsonify(error='invalid_userid')

    if user_id:
        if not user_exists(user_id):
            print('user_tx_report_endpoint: user_id %s does not exist. aborting' % user_id)
            return jsonify(erorr='no_such_user')
        else:
            return jsonify(report=[get_user_tx_report(user_id)])

    else: # user_phone
        user_ids = get_all_user_id_by_phone(user_phone) # there may be a few users with this phone
        if not user_ids:
            print('user_tx_report_endpoint: user_phone %s does not exist. aborting' % user_phone)
            return jsonify(erorr='no_such_phone')
        else:
            return jsonify(report=[get_user_tx_report(user_id) for user_id in user_ids])


@app.route('/user/report', methods=['POST'])
def user_report_endpoint():
    """returns a summary of the user's data"""
    limit_to_acl()
    limit_to_password()

    try:
        payload = request.get_json(silent=True)
        user_id = payload.get('user_id', None)
        user_phone = payload.get('phone', None)
        if (user_id is None and user_phone is None) or (user_id is not None and user_phone is not None):
            print('user_report_endpoint: userid %s, user_phone %s' % (user_id, user_phone))
            raise InvalidUsage('bad-request')
    except Exception as e:
        print(e)
        raise InvalidUsage('bad-request')

    try:  # sanitize user_id:
        if user_id:
            UUID(user_id)
    except Exception as e:
        log.error('cant generate report for user_id: %s ' % user_id)
        return jsonify(error='invalid_userid')

    if user_id:
        if not user_exists(user_id):
            print('user_report_endpoint: user_id %s does not exist. aborting' % user_id)
            return jsonify(erorr='no_such_user')
        else:
            return jsonify(report=[get_user_report(user_id)])

    else: # user_phone
        user_ids = get_all_user_id_by_phone(user_phone) # there may be a few users with this phone
        if not user_ids:
            print('user_report_endpoint: user_phone %s does not exist. aborting' % user_phone)
            return jsonify(erorr='no_such_phone')
        else:
            return jsonify(report=[get_user_report(user_id) for user_id in user_ids])


@app.route('/users/deauth', methods=['GET'])
def deauth_users_endpoint():
    """disables users that were sent an auth token but did not ack it in time"""
    if not config.DEBUG:
        limit_to_localhost()

    app.rq_fast.enqueue(scan_for_deauthed_users)
    return jsonify(status='ok')


@app.route('/users/unauthed', methods=['GET'])
def users_unauthed_endpoint():
    """get the list of userids that are not authenticated"""
    if not config.DEBUG:
        limit_to_localhost()
    return jsonify(user_ids=get_unauthed_users())

@app.route('/user/phone-number/blacklist', methods=['POST'])
def user_phone_number_blacklist_endpoint():
    """blacklist a number"""
    if not config.DEBUG:
        limit_to_localhost()

    try:
        payload = request.get_json(silent=True)
        phone_number = payload.get('phone-number', None)
        if phone_number is None:
            print('user_phone_number_blacklist_endpoint: user_phone: %s' % phone_number)
            raise InvalidUsage('bad-request')
    except Exception as e:
        print(e)
        raise InvalidUsage('bad-request')

    if not blacklist_phone_number(phone_number):
        raise InternalError('cant blacklist number')
    return jsonify(status='ok')


# @app.route('/user/skip_wait', methods=['POST'])
# def skip_wait_endpoint():
#     """sets the next task's timestamp to the past for the given user"""
#     limit_to_acl()
#     limit_to_password()
#
#     try:
#         payload = request.get_json(silent=True)
#         user_id = payload.get('user_id', None)
#         cat_id = payload.get('cat_id', None)
#         next_ts = payload.get('next_ts', 1)  # optional
#         if user_id is None:
#             raise InvalidUsage('bad-request')
#     except Exception as e:
#         print(e)
#         raise InvalidUsage('bad-request')
#     else:
#         store_next_task_results_ts(user_id, 'fake_task_id', next_ts, cat_id)
#
#     increment_metric('skip-wait')
#     return jsonify(status='ok')


@app.route('/user/auth/send', methods=['POST'])
def send_auth_token_api():
    """debug endpoint used to manually target clients with auth tokens"""
    if not config.DEBUG:
        limit_to_localhost()

    payload = request.get_json(silent=True)
    try:
        user_ids = payload.get('user_ids', [])
    except Exception as e:
        print(e)
        raise InvalidUsage('bad-request')

    for user_id in user_ids:
        # force send auth push
        send_push_auth_token(user_id, force_send=True)

    return jsonify(status='ok')


@app.route('/user/blacklist', methods=['POST'])
def blacklist_user_endpoint():
    """"""
    if not config.DEBUG:
        limit_to_acl()
        limit_to_password()

    try:
        payload = request.get_json(silent=True)
        user_id = payload.get('user_id', None)
        if user_id is None:
            raise InvalidUsage('bad-request')
    except Exception as e:
        print(e)
        raise InvalidUsage('bad-request')
    else:
        if blacklist_phone_by_user_id(user_id):
            return jsonify(status='ok')
        else:
            return jsonify(status='error')


@app.route('/users/migrate-restored-user', methods=['POST'])
def migrate_restored_user():
    # TODO remove me later
    if not config.DEBUG:
        limit_to_localhost()

    try:
        payload = request.get_json(silent=True)
        restored_user_id = payload.get('restored_user_id', None)
        temp_user_id = payload.get('temp_user_id', None)
    except Exception as e:
        log.error('failed to process migrate-restored-user')

    if not migrate_restored_user_data(temp_user_id, restored_user_id):
        log.error('failed to migrate restored user data from %s to %s' % (temp_user_id, restored_user_id))
        return jsonify(status='error')
    else:
        send_push_register(restored_user_id)

    return jsonify(status='ok')


@app.route('/rq/jobs/count', methods=['GET'])
def get_rq_q_length_endpoint():
    # TODO remove me later
    if not config.DEBUG:
        limit_to_localhost()

    from rq import Queue
    for queue_name in ['tippicserver-%s-fast' % config.DEPLOYMENT_ENV,'tippicserver-%s-slow' % config.DEPLOYMENT_ENV]:
        q = Queue(queue_name, connection=app.redis)
        print('there are currently %s jobs in the %s queue' % (q.count, queue_name))
        gauge_metric('rq_queue_len', q.count, 'queue_name:%s' % queue_name)
    return jsonify(status='ok')


@app.route('/users/reregister', methods=['GET'])
def reregister_users_endpoint():
    if not config.DEBUG:
        limit_to_localhost()

    app.rq_slow.enqueue(re_register_all_users)
    return jsonify(status='ok')


@app.route('/tx/total', methods=['GET'])
def total_kins_endpoint():
    if not config.DEBUG:
        limit_to_localhost()

    return jsonify(status='ok', total=get_tx_totals())


@app.route('/users/captcha/set', methods=['POST'])
def user_set_captcha_endpoint():
    if not config.DEBUG:
        limit_to_acl()
        limit_to_password()
    try:
        payload = request.get_json(silent=True)
        user_ids = payload.get('user_ids')
        should_show = payload.get('set_captcha', 0)
    except Exception as e:
        log.error('failed to process user-set-captcha')
    else:
        for user_id in user_ids:
            print('user_set_captcha_endpoint: setting user_id %s to %s' % (user_id, should_show))
            set_should_solve_captcha(user_id, should_show)

    return jsonify(status='ok')


@app.route('/system/versions/update-available-below', methods=['POST'])
def system_versions_update_available_below_endpoint():
    if not config.DEBUG:
        limit_to_acl()
        limit_to_password()

    payload = request.get_json(silent=True)
    os_type = payload.get('os_type', None)
    app_version = payload.get('version', None)
    set_update_available_below(os_type, app_version)
    return jsonify(status='ok')


@app.route('/system/versions/force-update-below', methods=['POST'])
def system_versions_force_update_below_endpoint():
    if not config.DEBUG:
        limit_to_acl()
        limit_to_password()

    payload = request.get_json(silent=True)
    os_type = payload.get('os_type', None)
    app_version = payload.get('version', None)
    set_force_update_below(os_type, app_version)
    return jsonify(status='ok')


