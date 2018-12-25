"""
The Kin App Server private API is defined here.
"""
import traceback
from uuid import UUID
import logging as log

from flask import request, jsonify, abort


from kinappserver.views_common import limit_to_acl, limit_to_localhost, limit_to_password

from kinappserver import app, config, stellar, utils, ssm
from .push import send_please_upgrade_push_2
from kinappserver.stellar import send_kin
from kinappserver.utils import InvalidUsage, InternalError, increment_metric, gauge_metric,\
    sqlalchemy_pool_status
from kinappserver.models import add_task, add_category, send_engagement_push, \
    create_tx, add_offer, set_offer_active, create_good, list_inventory, release_unclaimed_goods, \
    get_users_for_engagement_push, list_user_transactions, get_task_details, set_delay_days, \
    get_address_by_userid, send_compensated_push, nuke_user_data, send_push_auth_token, init_bh_creds, create_bh_offer, \
    get_task_results, get_user_report, get_user_tx_report, get_user_goods_report, \
    scan_for_deauthed_users, user_exists, send_push_register, store_next_task_results_ts, \
    get_unauthed_users, get_all_user_id_by_phone, delete_all_user_data, \
    blacklist_phone_number, blacklist_phone_by_user_id, count_missing_txs, migrate_restored_user_data, \
    re_register_all_users, get_tx_totals, set_should_solve_captcha, add_task_to_completed_tasks, \
    remove_task_from_completed_tasks, switch_task_ids, delete_task, block_user_from_truex_tasks, \
    unblock_user_from_truex_tasks, set_update_available_below, set_force_update_below, \
    update_categories_extra_data, task20_migrate_tasks, add_discovery_app, set_discovery_app_active, \
    add_discovery_app_category, get_user, blacklist_enc_phone_number, is_enc_phone_number_blacklisted


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
    print(payload)
    
    try:
        offer = payload.get('offer', None)
        set_active = payload.get('set_active', False)  # optional
    except Exception as e:
        print('exception: %s' % e)
        traceback.print_exc()
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
    log.info('engage-push: will call engage_push on rq_slow with scheme:%s, dry run:%s' % (scheme, dry_run))
    app.rq_slow.enqueue_call(func=send_engagement_messages, args=(scheme, dry_run))
    #send_engagement_messages(scheme, dry_run)
    return jsonify(status='ok')


def send_engagement_messages(scheme, dry_run):
    """does the actual work related to sending engagement messages. should be called in the worker"""
    user_ids = get_users_for_engagement_push(scheme)
    log.info('engage-push: --- in send_engagement_messages')

    if dry_run:
        log.info('engage-push: engagement_api - dry_run - not sending push')
    else:
        import time
        for user_id in user_ids[utils.OS_IOS]:
            time.sleep(1)  # hack to slow down push-sending as it kills the server
            if not send_engagement_push(user_id, scheme):
                log.error('engage-push: cant push to user %s: no push token' % user_id)
        for user_id in user_ids[utils.OS_ANDROID]:
            time.sleep(1)  # hack to slow down push-sending as it kills the server
            if not send_engagement_push(user_id, scheme):
                log.error('engage-push: cant push to user %s: no push token' % user_id)


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
        log.error('cant compensate user %s - no public address' % user_id)
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
    app.rq_slow.enqueue_call(func=replenish_bh_cards, args=(True,))  # this can be a long-lasting request
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


@app.route('/user/goods/report', methods=['POST'])
def user_goods_report_endpoint():
    """returns a summary of the user's goods data"""
    limit_to_acl()
    limit_to_password()

    try:
        payload = request.get_json(silent=True)
        user_id = payload.get('user_id', None)
        user_phone = payload.get('phone', None)
        if (user_id is None and user_phone is None) or (user_id is not None and user_phone is not None):
            print('user_goods_report_endpoint: userid %s, user_phone %s' % (user_id, user_phone))
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
            print('user_goods_report_endpoint: user_id %s does not exist. aborting' % user_id)
            return jsonify(erorr='no_such_user')
        else:
            return jsonify(report=[get_user_goods_report(user_id)])

    else: # user_phone
        user_ids = get_all_user_id_by_phone(user_phone) # there may be a few users with this phone
        if not user_ids:
            print('user_goods_report_endpoint: user_phone %s does not exist. aborting' % user_phone)
            return jsonify(erorr='no_such_phone')
        else:
            return jsonify(report=[get_user_goods_report(user_id) for user_id in user_ids])


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


@app.route('/user/user-id/blacklist', methods=['POST'])
def user_ids_list_blacklist_endpoint():
    """ block a list of users by there ids"""
    if not config.DEBUG:
        limit_to_localhost()
    try:
        payload = request.get_json(silent=True)
        user_ids = payload.get('user_ids', None)

        if user_ids is None:
            print('user_ids_list_blacklist_endpoint: ids: %s' % user_ids)
            raise InvalidUsage('bad-request')
        
        blacklisted, unable_to_blacklist, already_blacklisted, no_phone_number = [],[],[],[]
        for user_id in user_ids:
            user = get_user(user_id)
            if not user.enc_phone_number:
                no_phone_number.append(user_id)

            elif is_enc_phone_number_blacklisted(user.enc_phone_number):
                already_blacklisted.append(user_id)

            elif not blacklist_enc_phone_number(user.enc_phone_number):
                unable_to_blacklist.append(user_id)  # for later retry
        
            else:
                blacklisted.append(user_id)

        return jsonify(blacklisted=blacklisted,already_blacklisted=already_blacklisted, unable_to_blacklist=unable_to_blacklist)

    except Exception as e:
        print(e)
        raise InvalidUsage('bad-request')


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
        cat_id = payload.get('cat_id', None)
        next_ts = payload.get('next_ts', 1)  # optional
        if user_id is None:
            raise InvalidUsage('bad-request')
    except Exception as e:
        print(e)
        raise InvalidUsage('bad-request')
    else:
        store_next_task_results_ts(user_id, 'fake_task_id', next_ts, cat_id)

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


@app.route('/category/add', methods=['POST'])
def add_category_endpoint():
    """used to add categories to the db"""
    if not config.DEBUG:
        limit_to_localhost()

    payload = request.get_json(silent=True)

    try:
        task = payload.get('category', None)
    except Exception as e:
        print('exception: %s' % e)
        raise InvalidUsage('bad-request')
    if add_category(task):
        return jsonify(status='ok')
    else:
        raise InvalidUsage('failed to add category')


@app.route('/task/add', methods=['POST'])
def add_task_endpoint():
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

@app.route('/task/delete', methods=['POST'])
def delete_task_endpoint():
    """used to delete task from the db"""
    if not config.DEBUG:
        limit_to_localhost()

    payload = request.get_json(silent=True)
    try:
        task_id = payload.get('task_id', None)

    except Exception as e:
        print('exception: %s' % e)
        raise InvalidUsage('bad-request')
    delete_task(task_id)
    return jsonify(status='ok')


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
    app.rq_slow.enqueue_call(func=count_missing_txs, args=())
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
    for queue_name in ['kinappserver-%s-fast' % config.DEPLOYMENT_ENV,'kinappserver-%s-slow' % config.DEPLOYMENT_ENV]:
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


@app.route('/user/completed_tasks/add', methods=['POST'])
def add_task_to_completed_tasks_endpoint():
    if not config.DEBUG:
        limit_to_acl()
        limit_to_password()

    payload = request.get_json(silent=True)
    user_id = payload.get('user_id', None)
    task_id = payload.get('task_id', None)

    add_task_to_completed_tasks(user_id, task_id)

    return jsonify(status='ok')


@app.route('/user/completed_tasks/remove', methods=['POST'])
def remove_task_from_completed_tasks_endpoint():
    if not config.DEBUG:
        limit_to_acl()
        limit_to_password()

    payload = request.get_json(silent=True)
    user_id = payload.get('user_id', None)
    task_id = payload.get('task_id', None)

    remove_task_from_completed_tasks(user_id, task_id)

    return jsonify(status='ok')


@app.route('/tasks/switch_ids', methods=['POST'])
def switch_task_ids_endpoint():
    if not config.DEBUG:
        limit_to_acl()
        limit_to_password()

    payload = request.get_json(silent=True)
    task_id1 = payload.get('task_id1', None)
    task_id2 = payload.get('task_id2', None)

    switch_task_ids(task_id1, task_id2)

    return jsonify(status='ok')


@app.route('/user/truex/block', methods=['POST'])
def block_user_from_truex_task_endpoint():
    if not config.DEBUG:
        limit_to_acl()
        limit_to_password()

    payload = request.get_json(silent=True)
    user_id = payload.get('user_id', None)
    block_user_from_truex_tasks(user_id)
    return jsonify(status='ok')


@app.route('/user/truex/unblock', methods=['POST'])
def unblock_user_from_truex_task_endpoint():
    if not config.DEBUG:
        limit_to_acl()
        limit_to_password()

    payload = request.get_json(silent=True)
    user_id = payload.get('user_id', None)
    unblock_user_from_truex_tasks(user_id)
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


@app.route('/system/categories/update-extra-data', methods=['POST'])
def update_extra_data_endpoint():
    if not config.DEBUG:
        limit_to_acl()
        limit_to_password()

    payload = request.get_json(silent=True)
    categories_extra_data = payload.get('categories_extra_data')
    update_categories_extra_data(categories_extra_data)
    return jsonify(status='ok')


@app.route('/task/migrate', methods=['POST'])
def migrate_tasks_to_task20():
    if not config.DEBUG:
        limit_to_acl()
        limit_to_password()

    task20_migrate_tasks()
    return jsonify(status='ok')


@app.route('/app_discovery/add_category', methods=['POST'])
def add_discovery_app_category_api():
    """ add a discovery app category to the db"""
    if not config.DEBUG:
        limit_to_localhost()

    payload = request.get_json(silent=True)
    try:
        discovery_app_category = payload.get('discovery_app_category', None)
    except Exception as e:
        print('exception: %s' % e)
        raise InvalidUsage('bad-request')
    if add_discovery_app_category(discovery_app_category):
        return jsonify(status='ok')
    else:
        raise InvalidUsage('failed to add discovery app')


@app.route('/app_discovery/is_active', methods=['POST'])
def set_active_app_discovery_api():
    """ enable/ disable discovery app"""
    if not config.DEBUG:
        limit_to_localhost()
    payload = request.get_json(silent=True)
    try:
        app_id = payload.get('app_id', None)
        set_active = payload.get('set_active', False)  # optional
    except Exception as e:
        print('exception: %s' % e)
        raise InvalidUsage('bad-request')
    if set_discovery_app_active(app_id, set_active):
        return jsonify(status='ok')
    else:
        raise InvalidUsage('failed to activate discovery app')


@app.route('/app_discovery/add_discovery_app', methods=['POST'])
def add_discovery_app_api():
    """ internal endpoint used to populate the server with discovery apps"""
    if not config.DEBUG:
        limit_to_localhost()

    payload = request.get_json(silent=True)
    try:
        discovery_app = payload.get('discovery_app', None)
        set_active = payload.get('set_active', False)  # optional
    except Exception as e:
        print('exception: %s' % e)
        raise InvalidUsage('bad-request')
    if add_discovery_app(discovery_app, set_active):
        return jsonify(status='ok')
    else:
        raise InvalidUsage('failed to add discovery app')
