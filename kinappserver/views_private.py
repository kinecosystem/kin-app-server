"""
The Kin App Server private API is defined here.
"""
from uuid import UUID

from flask import request, jsonify, abort
from flask_api import status
import redis_lock
import arrow
import redis
from distutils.version import LooseVersion
from .utils import OS_ANDROID, OS_IOS, random_percent

from kinappserver.views_common import limit_to_acl, limit_to_localhost, limit_to_password, get_source_ip, extract_headers

from kinappserver import app, config, stellar, utils, ssm
from .push import send_please_upgrade_push_2, send_country_not_supported
from kinappserver.stellar import create_account, send_kin, send_kin_with_payment_service
from kinappserver.utils import InvalidUsage, InternalError, errors_to_string, increment_metric, gauge_metric, MAX_TXS_PER_USER, extract_phone_number_from_firebase_id_token,\
    sqlalchemy_pool_status, get_global_config, write_payment_data_to_cache, read_payment_data_from_cache
from kinappserver.models import create_user, update_user_token, update_user_app_version, \
    store_task_results, add_task, get_tasks_for_user, is_onboarded, \
    set_onboarded, send_push_tx_completed, send_engagement_push, \
    create_tx, get_reward_for_task, add_offer, \
    get_offers_for_user, set_offer_active, create_order, process_order, \
    create_good, list_inventory, release_unclaimed_goods, get_users_for_engagement_push, \
    list_user_transactions, get_redeemed_items, get_offer_details, get_task_details, set_delay_days,\
    add_p2p_tx, set_user_phone_number, match_phone_number_to_address, user_deactivated,\
    handle_task_results_resubmission, reject_premature_results, get_address_by_userid, send_compensated_push,\
    list_p2p_transactions_for_user_id, nuke_user_data, send_push_auth_token, ack_auth_token, is_user_authenticated, is_user_phone_verified, init_bh_creds, create_bh_offer,\
    get_task_results, get_user_config, get_user_report, get_user_tx_report, get_task_by_id, get_truex_activity, get_and_replace_next_task_memo,\
    get_next_task_memo, scan_for_deauthed_users, user_exists, send_push_register, get_user_id_by_truex_user_id, store_next_task_results_ts, is_in_acl,\
    get_email_template_by_type, get_unauthed_users, get_all_user_id_by_phone, get_backup_hints, generate_backup_questions_list, store_backup_hints, \
    validate_auth_token, restore_user_by_address, get_unenc_phone_number_by_user_id, fix_user_task_history, update_tx_ts, fix_user_completed_tasks, \
    should_block_user_by_client_version, deactivate_user, get_user_os_type, should_block_user_by_phone_prefix, delete_all_user_data, count_registrations_for_phone_number, \
    blacklist_phone_number, blacklist_phone_by_user_id, count_missing_txs, migrate_restored_user_data, re_register_all_users


@app.route('/health', methods=['GET'])
def get_health():
    """health endpoint"""
    return jsonify(status='ok')


@app.route('/user/tasks/fix', methods=['POST'])
def fix_user_tasks_endpoint():
    #TODO REMVOE THIS
    '''temp endpoit to add txs for users with nissing txs'''
    if not config.DEBUG:
        limit_to_localhost()

    payload = request.get_json(silent=True)

    user_id = payload.get('user_id', None)
    fix_user_completed_tasks(user_id)
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


@app.route('/task/delay_days', methods=['POST'])
def set_delay_days_api():
    """used to set the delay_days on all tasks - used in tests"""
    if not config.DEBUG:
        limit_to_localhost()

    payload = request.get_json(silent=True)
    try:
        delay_days = payload.get('days', None)
        if delay_days is None:
            raise InvalidUsage('missing days param')
    except Exception as e:
        print('exception: %s' % e)
        raise InvalidUsage('bad-request')

    set_delay_days(delay_days)
    print('set delay days to %s' % delay_days)
    return jsonify(status='ok')


@app.route('/offer/add', methods=['POST'])
def add_offer_api():
    """internal endpoint used to populate the server with offers"""
    if not config.DEBUG:
        limit_to_localhost()

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
        limit_to_localhost()

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


@app.route('/good/add', methods=['POST'])
def add_good_api():
    """internal endpoint used to populate the server with goods"""
    if not config.DEBUG:
        limit_to_localhost()

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
        limit_to_localhost()

    return jsonify(status='ok', inventory=list_inventory())


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

@app.route('/good/release_unclaimed', methods=['GET'])
def release_unclaimed_api():
    """endpoint used to release goods that were booked but never redeemed"""
    if not config.DEBUG:
        limit_to_localhost()

    released = release_unclaimed_goods()
    increment_metric('unclaimed_released', released)
    return jsonify(status='ok', released=released)


@app.route('/engagement/send', methods=['POST'])
def send_engagement_api():
    """endpoint used to send engagement push notifications to users by scheme. password protected"""
    if not config.DEBUG:
        limit_to_localhost()

    payload = request.get_json(silent=True)
    scheme = payload.get('scheme')
    if scheme is None:
        raise InvalidUsage('invalid param')
    dry_run = payload.get('dryrun', 'True') == 'True'
    app.rq_slow.enqueue_call(func=send_engagement_messages, args=(scheme, dry_run))
    return jsonify(status='ok')


def send_engagement_messages(scheme, dry_run):
    """does the actual work related to sending engagement messages. should be called in the worker"""
    user_ids = get_users_for_engagement_push(scheme)
    print('gathered user_ids: %s' % user_ids)
    print('gathered %d ios user_ids and %d gcm user_ids for scheme: %s, dry-run:%s' % (len(user_ids[utils.OS_IOS]), len(user_ids[utils.OS_ANDROID]), scheme, dry_run))

    if dry_run:
        print('send_engagement_api - dry_run - not sending push')
    else:
        print('sending push ios %d tokens' % len(user_ids[utils.OS_IOS]))
        import time
        for user_id in user_ids[utils.OS_IOS]:
            time.sleep(1)  # hack to slow down push-sending as it kills the server
            send_engagement_push(user_id, scheme)
        print('sending push android %d tokens' % len(user_ids[utils.OS_ANDROID]))
        for user_id in user_ids[utils.OS_ANDROID]:
            time.sleep(1)  # hack to slow down push-sending as it kills the server
            send_engagement_push(user_id, scheme)


@app.route('/user/compensate', methods=['POST'])
def compensate_user_api():
    """internal endpoint used to manually compensate users for missing txs"""
    if not config.DEBUG:
        limit_to_localhost()

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
        increment_metric('manual-compensation')

        return jsonify(status='ok', tx_hash=tx_hash)


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


@app.route('/blackhawk/creds/init', methods=['POST'])
def init_bh_creds_api():
    """internal endpoint used to init blackhawk credentials"""
    if not config.DEBUG:
        limit_to_localhost()

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
        limit_to_localhost()

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
    """asynchronously reports a metric with bh's account balance"""
    if not config.DEBUG:
        limit_to_localhost()

    if not config.BLACKHAWK_PURCHASES_ENABLED:
        print('blackhawk purchases disabled by config. ignoring cron')
        return jsonify(status='ok')

    from .blackhawk import get_account_balance
    balance = get_account_balance()
    print('bh account balance:%s' % balance)
    gauge_metric('bh-account-balance', balance)
    return jsonify(status='ok')


@app.route('/blackhawk/cards/replenish', methods=['POST'])
def replenish_bh_cards_endpoint():
    """asynchronously buy additional cards from blackhawk if below threshold"""
    if not config.DEBUG:
        limit_to_localhost()

    if not config.BLACKHAWK_PURCHASES_ENABLED:
        print('blackhawk purchases disabled by config. ignoring cron')
        return jsonify(status='ok')

    # buys cards if needed
    from .blackhawk import replenish_bh_cards
    app.rq_fast.enqueue_call(func=replenish_bh_cards, args=(True,))
    return jsonify(status='ok')


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
        print('cant generate tx report for user_id: %s ' % user_id)
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
        print('cant generate report for user_id: %s ' % user_id)
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


@app.route('/user/skip_wait', methods=['POST'])
def skip_wait_endpoint():
    """sets the next task's timestamp to the past for the given user"""
    limit_to_acl()
    limit_to_password()

    try:
        payload = request.get_json(silent=True)
        user_id = payload.get('user_id', None)
        next_ts = payload.get('next_ts', 1)  # optional
        if user_id is None:
            raise InvalidUsage('bad-request')
    except Exception as e:
        print(e)
        raise InvalidUsage('bad-request')
    else:
        store_next_task_results_ts(user_id, next_ts)

    increment_metric('skip-wait')
    return jsonify(status='ok')


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


@app.route('/task/add', methods=['POST'])
def add_task_api():
    """used to add tasks to the db"""
    if not config.DEBUG:
        limit_to_localhost()

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


@app.route('/task/results', methods=['POST'])
def post_task_results_endpoint():
    """an endpoint that can be used to return task results for bi"""
    limit_to_acl()
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


@app.route('/users/missing-txs', methods=['GET'])
def get_missing_txs_endpoint():
    if not config.DEBUG:
        limit_to_localhost()
    app.rq_slow.enqueue(count_missing_txs)
    return jsonify(status='ok')


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
        print('failed to process migrate-restored-user')

    if not migrate_restored_user_data(temp_user_id, restored_user_id):
        print('failed to migrate restored user data from %s to %s' % (temp_user_id, restored_user_id))
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
    for queue_name in ['kinappserver-%s' % config.DEPLOYMENT_ENV]:
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


