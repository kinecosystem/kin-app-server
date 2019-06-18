"""The User model"""
from sqlalchemy_utils import UUIDType
from sqlalchemy.dialects.postgresql import INET
import logging as log

from kinappserver import db, config, app
from kinappserver.utils import InvalidUsage, OS_IOS, OS_ANDROID, parse_phone_number, increment_metric, gauge_metric, get_global_config, generate_order_id, OS_ANDROID, OS_IOS, commit_json_changed_to_orm
from kinappserver.push import push_send_gcm, push_send_apns, engagement_payload_apns, engagement_payload_gcm, compensated_payload_apns, compensated_payload_gcm, send_country_IS_supported
from uuid import uuid4, UUID
from .push_auth_token import get_token_obj_by_user_id, should_send_auth_token, set_send_date
import arrow
import json
from distutils.version import LooseVersion
from .backup import get_user_backup_hints_by_enc_phone
from time import sleep

DEFAULT_TIME_ZONE = -4
KINIT_IOS_PACKAGE_ID_PROD = 'org.kinecosystem.kinit'  # AKA bundle id
DEVICE_MODEL_MAX_SIZE = 40


class User(db.Model):
    """
    the user model
    """
    sid = db.Column(db.Integer(), db.Sequence('sid', start=1, increment=1), primary_key=False)
    user_id = db.Column(UUIDType(binary=False), primary_key=True, nullable=False)
    os_type = db.Column(db.String(10), primary_key=False, nullable=False)
    device_model = db.Column(db.String(DEVICE_MODEL_MAX_SIZE), primary_key=False, nullable=False)
    push_token = db.Column(db.String(200), primary_key=False, nullable=True)
    time_zone = db.Column(db.Integer(), primary_key=False, nullable=False)
    device_id = db.Column(db.String(40), primary_key=False, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now())
    onboarded = db.Column(db.Boolean, unique=False, default=False)
    public_address = db.Column(db.String(60), primary_key=False, unique=True, nullable=True)
    enc_phone_number = db.Column(db.String(200), primary_key=False, nullable=True)
    deactivated = db.Column(db.Boolean, unique=False, default=False)
    auth_token = db.Column(UUIDType(binary=False), primary_key=False, nullable=True)
    package_id = db.Column(db.String(60), primary_key=False, nullable=True)
    screen_w = db.Column(db.String(20), primary_key=False, nullable=True)
    screen_h = db.Column(db.String(20), primary_key=False, nullable=True)
    screen_d = db.Column(db.String(20), primary_key=False, nullable=True)
    user_agent = db.Column(db.String(200), primary_key=False, nullable=True)  # optional, and filled via get_truex_activity
    truex_user_id = db.Column(UUIDType(binary=False), primary_key=False, nullable=True)

    def __repr__(self):
        return '<sid: %s, user_id: %s, os_type: %s, device_model: %s, push_token: %s, time_zone: %s, device_id: %s,' \
               ' onboarded: %s, public_address: %s, enc_phone_number: %s, package_id: %s, screen_w: %s, screen_h: %s,' \
               ' screen_d: %s, user_agent: %s, deactivated: %s, truex_user_id: %s>' % (self.sid, self.user_id, self.os_type, self.device_model, self.push_token, self.time_zone,
                                                                                           self.device_id, self.onboarded, self.public_address, self.enc_phone_number, self.package_id,
                                                                                self.screen_w, self.screen_h, self.screen_d, self.user_agent, self.deactivated, self.truex_user_id)


def get_user(user_id):
    user = User.query.filter_by(user_id=user_id).first()
    if not user:
        raise InvalidUsage('no such user_id')
    return user


def deactivate_user(user_id):
    """deactivate user by userid"""
    user = get_user(user_id)
    user.deactivated = True
    db.session.add(user)
    db.session.commit()


def user_deactivated(user_id):
    """returns true if the user_id is deactivated"""
    # TODO cacahe the results?
    try:
        user = get_user(user_id)
    except Exception as e:
        return False
    else:
        return user.deactivated


def user_exists(user_id):
    user = User.query.filter_by(user_id=user_id).first()
    return True if user else False


def is_onboarded(user_id):
    """returns whether the user has an account or None if there's no such user."""
    try:
        return User.query.filter_by(user_id=user_id).first().onboarded
    except Exception as e:
        print(e)
        return None


def set_onboarded(user_id, onboarded, public_address):
    """set the onbarded field of the user in the db"""
    user = get_user(user_id)
    user.onboarded = onboarded
    user.public_address = public_address
    db.session.add(user)
    db.session.commit()


def create_user(user_id, os_type, device_model, push_token, time_zone, device_id, app_ver, screen_w, screen_h, screen_d, package_id):
    """create a new user and commit to the database. should only fail if the user_id is duplicate"""

    def parse_timezone(tz):
        """convert -02:00 to -2 or set reasonable default"""
        try:
            return int(tz[:(tz.find(':'))])
        except Exception as e:
            log.error('failed to parse timezone: %s. using default. e: %s' % (tz, e))
            return int(DEFAULT_TIME_ZONE)

    is_new_user = False
    try:
        user = get_user(user_id)
        log.info('user %s already exists, updating data' % user_id)
    except Exception as e:
        user = User()
        is_new_user = True

    user.user_id = user_id
    user.os_type = os_type
    user.device_model = device_model[:DEVICE_MODEL_MAX_SIZE]
    user.push_token = push_token if push_token is not None else user.push_token
    user.time_zone = parse_timezone(time_zone)
    user.device_id = device_id
    user.auth_token = uuid4() if not user.auth_token else user.auth_token
    user.screen_h = screen_h
    user.screen_w = screen_w
    user.screen_d = screen_d
    user.package_id = package_id
    user.truex_user_id = uuid4() if not user.truex_user_id else user.truex_user_id
    db.session.add(user)
    db.session.commit()

    if is_new_user:
        user_app_data = UserAppData()
        user_app_data.user_id = user_id
        user_app_data.completed_tasks = '[]'
        user_app_data.completed_tasks_dict = {}
        user_app_data.app_ver = app_ver
        user_app_data.next_task_ts = arrow.utcnow().timestamp
        user_app_data.next_task_ts_dict = {}
        user_app_data.next_task_memo = generate_order_id()
        user_app_data.next_task_memo_dict = {}
        user_app_data.app_ver = app_ver
        db.session.add(user_app_data)
        db.session.commit()

        # get/create an auth token for this user
        get_token_obj_by_user_id(user_id)
    else:
        increment_metric('reregister')

    return is_new_user


def get_truex_user_id(user_id):
    """gets/create the truex user_id"""
    user = get_user(user_id)
    truex_user_id = user.truex_user_id
    if not truex_user_id:
        user.truex_user_id = uuid4()
        db.session.add(user)
        db.session.commit()

    return truex_user_id


def get_user_id_by_truex_user_id(truex_user_id):
    """return the user_id for the given truex user id"""
    try:
        user = User.query.filter_by(truex_user_id=truex_user_id).first()
        if user is None:
            return None
        else:
            return user.user_id
    except Exception as e:
        log.error('cant get user_id by truex_user_id. Exception: %s' % e)
        raise


def update_user_token(user_id, push_token):
    """updates the user's token with a new one"""
    user = get_user(user_id)
    user.push_token = push_token
    db.session.add(user)
    db.session.commit()


def list_all_users():
    """returns a dict of all the whitelisted users and their PAs (if available)"""
    response = {}
    users = User.query.order_by(User.user_id).all()
    for user in users:
        response[str(user.user_id)] = {'sid': user.sid, 'os': user.os_type, 'push_token': user.push_token,
                                       'time_zone': user.time_zone, 'device_id': user.device_id, 'device_model': user.device_model, 'onboarded': user.onboarded,
                                       'enc_phone_number': user.enc_phone_number, 'auth_token': user.auth_token, 'deactivated': user.deactivated}
    return response


class UserAppData(db.Model):
    """
    the user app data model tracks the version of the app installed @ the client
    """
    user_id = db.Column('user_id', UUIDType(binary=False), db.ForeignKey("user.user_id"), primary_key=True, nullable=False)
    app_ver = db.Column(db.String(40), primary_key=False, nullable=False)
    update_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now())
    completed_tasks = db.Column(db.JSON)
    completed_tasks_dict = db.Column(db.JSON)
    next_task_ts = db.Column(db.String(40), primary_key=False, nullable=True)  # the ts for th next task, can be None
    next_task_ts_dict = db.Column(db.JSON)
    next_task_memo = db.Column(db.String(len(generate_order_id())), primary_key=False, nullable=True)  # the memo for the user's next task.
    next_task_memo_dict = db.Column(db.JSON)
    ip_address = db.Column(INET) # the user's last known ip
    ip_address = db.Column(INET)  # the user's last known ip
    country_iso_code = db.Column(db.String(10))  # country iso code based on last ip
    captcha_history = db.Column(db.JSON)
    should_solve_captcha_ternary = db.Column(db.Integer, unique=False, default=0, nullable=False)  # -1 = no captcha, 0 = show captcha on next task, 1 = captcha required

def create_ticket(name,email, category, sub_category, description,user_id, platform,version, debug):
    from kinappserver import config
    import requests,json

    user,pwd = config.ZENDESK_API_TOKEN.split(':')
    headers = { 'Content-Type': 'application/json'}
    subject = "DEBUG_" + category if debug.lower() == 'true' else category
    data = '{ "request": { "requester": { "name": "%s", "email": "%s" }, "tags": [ "%s", "%s" ], "subject": "%s", "comment": { "body": "%s\\n user_id: %s\\n  platform: %s\\n version: %s"}}}' % (name, email, category,sub_category, subject, repr(description),user_id, platform,version)
    response = requests.post('https://kinitsupport.zendesk.com/api/v2/requests.json', headers=headers, data=data, auth=(user, pwd))
    log.debug(response.status_code)
    if response.status_code == 201:
        return True
    return False


def update_user_app_version(user_id, app_ver):
    """update the user app version"""
    try:
        userAppData = UserAppData.query.filter_by(user_id=user_id).first()
        userAppData.app_ver = app_ver
        db.session.add(userAppData)
        db.session.commit()
    except Exception as e:
        print(e)
        raise InvalidUsage('cant set user app data')


def get_user_inapp_balance(user_id):
    spend = db.engine.execute("select sum(amount) as total from public.transaction where user_id ='%s' and incoming_tx = true;" % user_id).first()['total'] or 0
    income = db.engine.execute("select sum(amount) as total from public.transaction where user_id ='%s' and incoming_tx = false;" % user_id).first()['total'] or 0
    return income - spend


def set_should_solve_captcha(user_id, value=0):
    """sets the should solve captcha. note that client version isn't checked here

    normally, you would set this value to zero, to show captcha on the next (not current) task.
    setting it to 1 might cause a (temporary) client error, when the client attempts to submit
    a (stale) task w/o a captcha, although one is required. it'll be fine on the next attempt.
    """
    try:

        userAppData = UserAppData.query.filter_by(user_id=user_id).first()
        userAppData.should_solve_captcha_ternary = value
        db.session.add(userAppData)
        db.session.commit()
    except Exception as e:
        print(e)
        raise InvalidUsage('cant set user should_solve_captcha_ternary')
    else:
        return True


def autoswitch_captcha(user_id):
    """promotes user's captcha state from 0 to 1, iff it was 0"""
    statement = '''update public.user_app_data set should_solve_captcha_ternary = 1 where public.user_app_data.user_id = '%s' and public.user_app_data.should_solve_captcha_ternary = 0;'''
    db.engine.execute(statement % user_id)



def should_pass_captcha(user_id):
    """returns True iff the client must pass captcha test. older clients are auto-exempt"""

    user_app_data = UserAppData.query.filter_by(user_id=user_id).one()
    client_version = user_app_data.app_ver
    ternary = user_app_data.should_solve_captcha_ternary
    os_type = get_user_os_type(user_id)

    if os_type == OS_ANDROID and LooseVersion(client_version) < LooseVersion(config.CAPTCHA_MIN_CLIENT_VERSION_ANDROID):
        return False
    if os_type == OS_IOS:  # all ios clients are exempt
        return False

    if ternary is not None and ternary > 0:
        return True
    return False


def captcha_solved(user_id):
    """lower the captcha flag for this user and add it to the history"""
    try:
        userAppData = UserAppData.query.filter_by(user_id=user_id).first()
        now = arrow.utcnow().timestamp
        if userAppData.should_solve_captcha_ternary < 1:
            log.info('captcha_solved: user %s doesnt need to solve captcha' % user_id)
            return

        userAppData.should_solve_captcha_ternary = -1 # reset back to -1 (doesn't need to pass captcha)

        # save previous hints
        if userAppData.captcha_history is None:
            userAppData.captcha_history = [{'date': now, 'app_ver': userAppData.app_ver}]
        else:
            userAppData.captcha_history.append({'date': now, 'app_ver ': userAppData.app_ver})
        log.info('writing to captcha history: %s' % userAppData.captcha_history)
        commit_json_changed_to_orm(userAppData, ['captcha_history'])

    except Exception as e:
        log.error('failed to mark captcha solved for user_id %s. e:%s' % (user_id, e))


def do_captcha_stuff(user_id):
    autoswitch_captcha(user_id)
    automatically_raise_captcha_flag(user_id)


def automatically_raise_captcha_flag(user_id):
    """this function will raise ths given user_id's captcha flag if the time is right.
    ATM we're selecting users by random with 20% chance and cooldown.
    TODO for task2.0, figure out WHEN is the right time to do this
    """
    if not config.CAPTCHA_AUTO_RAISE:
        return

    os_type = get_user_os_type(user_id)
    if os_type == OS_IOS:
        # print('not raising captcha for ios device %s' % user_id)
        return

    # get the user's current task
    # and also the captcha status and history - all are in the user_app_data
    uad = get_user_app_data(user_id)
    if uad.should_solve_captcha_ternary != -1:
        # log.info('raise_captcha_if_needed: user %s captcha flag already at %s. doing nothing' % (user_id, uad.should_solve_captcha_ternary))
        return

    # every time a user completed X tasks mod CAPTCHA_TASK_MODULO == 0, but never twice in the same <configurable time>
    if count_completed_tasks(user_id) % config.CAPTCHA_TASK_MODULO == 0:
        # ensure the last captcha wasnt solved today
        now = arrow.utcnow()
        recent_captcha = 0 if uad.captcha_history is None else max([item['date'] for item in uad.captcha_history])
        print(recent_captcha)
        last_captcha_secs_ago = (now - arrow.get(recent_captcha)).total_seconds()
        if last_captcha_secs_ago > config.CAPTCHA_SAFETY_COOLDOWN_SECS:
            # more than a day ago, so raise:
            log.info('raise_captcha_if_needed:  user %s, last captcha was %s secs ago, so raising flag' % (user_id, last_captcha_secs_ago))
            set_should_solve_captcha(user_id)
        # else:
        #    log.info('raise_captcha_if_needed: user %s, current task_id = %s, last captcha was %s secs ago, so not raising flag' % (user_id, max_task, last_captcha_secs_ago))


def update_ip_address(user_id, ip_address):
    try:
        userAppData = UserAppData.query.filter_by(user_id=user_id).first()
        if userAppData.ip_address == ip_address:
            # nothing to update
            return

        userAppData.ip_address = ip_address
        try:
            userAppData.country_iso_code = app.geoip_reader.get(ip_address)['country']['iso_code']
        except Exception as e:
            log.error('could not calc country iso code for %s' % ip_address)
        db.session.add(userAppData)
        db.session.commit()
    except Exception as e:
        log.error('update_ip_address: e: %s' % e)
        raise InvalidUsage('cant set user ip address')
    else:
        log.info('updated user %s ip to %s' % (user_id, ip_address))


def get_user_country_code(user_id):
    return UserAppData.query.filter_by(user_id=user_id).one().country_iso_code  # can be null


def get_next_task_memo(user_id, cat_id):
    """returns the next memo for this user and cat_id"""
    try:
        user_app_data = UserAppData.query.filter_by(user_id=user_id).first()
        next_memo = user_app_data.next_task_memo_dict.get(cat_id, None)
        if next_memo is None:  # set a value
            return generate_and_save_next_task_memo(user_app_data, cat_id)
    except Exception as e:
        raise InvalidUsage('cant get next memo. exception:%s' % e)
    else:
        return next_memo


def migrate_next_task_memo(user_id):
    """return the memo for this user and replace it with another"""
    try:
        memo = None
        user_app_data = UserAppData.query.filter_by(user_id=user_id).first()
        user_app_data.next_task_memo_dict = {}
        db.session.add(user_app_data)
        db.session.commit()
    except Exception as e:
        print(e)
        raise InvalidUsage('migration: cant reset next memo for %s' % user_id)

    return memo


def get_and_replace_next_task_memo(user_id, task_id, cat_id=None):
    """return the memo for this user and replace it with another"""
    try:
        memo = None
        user_app_data = UserAppData.query.filter_by(user_id=user_id).first()
        from .task2 import get_cat_id_for_task_id
        cat_id = cat_id if cat_id else get_cat_id_for_task_id(task_id)
        if user_app_data.next_task_memo_dict[cat_id]:
            memo = user_app_data.next_task_memo_dict[cat_id]
            # if for some reason we still have a memo that includes the app id
            # we should remove it because the sdk adds the app id
            if memo.startswith('1-kit-'):
                log.info("removing 1-kit- from memo:%s for user:%s, task:%s, cat_id:%s " % (memo, user_id, task_id, cat_id))
                memo = memo[6:]

        generate_and_save_next_task_memo(user_app_data, cat_id)

    except Exception as e:
        print(e)
        raise InvalidUsage('cant set next memo')

    return memo


def generate_and_save_next_task_memo(user_app_data, cat_id):
    """generate a new memo and save it"""
    next_memo = generate_order_id()
    user_app_data.next_task_memo_dict[cat_id] = next_memo
    commit_json_changed_to_orm(user_app_data, ['next_task_memo_dict'])
    return next_memo


def list_all_users_app_data():
    """returns a dict of all the user-app-data"""
    response = {}
    users = UserAppData.query.order_by(UserAppData.user_id).all()
    for user in users:
        response[user.user_id] = {'user_id': user.user_id,  'app_ver': user.app_ver, 'update': user.update_at, 'completed_tasks': user.completed_tasks_dict}
    return response


def get_user_app_data(user_id):
    user_app_data = UserAppData.query.filter_by(user_id=user_id).first()
    if not user_app_data:
        raise InvalidUsage('no such user_id')
    return user_app_data


def get_user_tz(user_id):
    """return the user timezone"""
    return User.query.filter_by(user_id=user_id).one().time_zone


def get_user_os_type(user_id):
    """return the user os_type"""
    return User.query.filter_by(user_id=user_id).one().os_type


def package_id_to_push_env(package_id):
    if package_id == KINIT_IOS_PACKAGE_ID_PROD:
        # only ios clients use prod atm
        return 'prod'
    return 'beta'


def get_user_push_data(user_id):
    """returns the os_type, token and push_env for the given user_id"""
    try:
        user = User.query.filter_by(user_id=user_id).first()
    except Exception as e:
        log.error('Error: could not get push data for user %s' % user_id)
        return None, None, None
    else:
        if user.os_type == OS_IOS:
            push_env = package_id_to_push_env(user.package_id)
        else:
            push_env = 'beta'  # android dont send package id and only support 'beta'
        return user.os_type, user.push_token, push_env


def send_push_tx_completed(user_id, tx_hash, amount, task_id, memo):
    """send a message indicating that the tx has been successfully completed"""
    os_type, token, push_env = get_user_push_data(user_id)
    if token is None:
        log.error('cant push to user %s: no push token' % user_id)
        return False
    if os_type == OS_IOS:
        from kinappserver.push import tx_completed_push_apns, generate_push_id
        push_send_apns(token, tx_completed_push_apns(generate_push_id(), str(tx_hash), str(user_id), str(task_id), int(amount), str(memo)), push_env)
    else:
        from kinappserver.push import gcm_payload, generate_push_id
        payload = gcm_payload('tx_completed', generate_push_id(), {'type': 'tx_completed', 'user_id': user_id, 'tx_hash': tx_hash, 'kin': amount, 'task_id': task_id})
        push_send_gcm(token, payload, push_env)
    return True


def send_push_auth_token(user_id, force_send=False):
    """send an auth token that the client should ack"""
    from .push_auth_token import get_token_by_user_id
    if not force_send and not should_send_auth_token(user_id):
        return True
    os_type, token, push_env = get_user_push_data(user_id)
    auth_token = get_token_by_user_id(user_id)
    if token is None:
        log.error('cant push to user %s: no push token' % user_id)
        return False
    if os_type == OS_IOS:
        from kinappserver.push import auth_push_apns, generate_push_id
        push_send_apns(token, auth_push_apns(generate_push_id(), str(auth_token), str(user_id)), push_env)
        push_send_apns(token, auth_push_apns(generate_push_id(), str(auth_token), str(user_id)), push_env) # send twice?
        log.info('sent apns auth token to user %s' % user_id)
    else:
        from kinappserver.push import gcm_payload, generate_push_id
        payload = gcm_payload('auth_token', generate_push_id(), {'type': 'auth_token', 'user_id': str(user_id), 'token': str(auth_token)})
        push_send_gcm(token, payload, push_env)
        log.info('sent gcm auth token to user %s' % user_id)

    if not set_send_date(user_id):
        log.error('could not set the send-date for auth-token for user_id: %s' % user_id)

    increment_metric('auth-token-sent')

    return True


def send_push_register(user_id):
    """send a message indicating that the client should re-register"""
    os_type, token, push_env = get_user_push_data(user_id)
    if token is None:
        log.error('cant push to user %s: no push token' % user_id)
        return False
    if os_type == OS_IOS:
        from kinappserver.push import register_push_apns, generate_push_id
        push_send_apns(token, register_push_apns(generate_push_id()), push_env)
        log.info('sent apns register to user %s' % user_id)
    else:
        from kinappserver.push import gcm_payload, generate_push_id
        payload = gcm_payload('register', generate_push_id(), {'type': 'register'})
        push_send_gcm(token, payload, push_env)
        log.info('sent gcm register to user %s' % user_id)

    increment_metric('register-push-sent')

    return True


def send_engagement_push(user_id, push_type):
    """sends an engagement push message to the user with the given user_id"""
    os_type, token, push_env = get_user_push_data(user_id)

    if token is None:
        return False

    if os_type == OS_IOS:
        push_send_apns(token, engagement_payload_apns(push_type), push_env)
    else:
        push_send_gcm(token, engagement_payload_gcm(push_type), push_env)

    increment_metric('sent_eng_push_%s' % push_type)
    return True


def send_compensated_push(user_id, amount, task_title):

    os_type, token, push_env = get_user_push_data(user_id)

    if token is None:
        log.error('cant push to user %s: no push token' % user_id)
        return False

    if os_type == OS_IOS:
        push_send_apns(token, compensated_payload_apns(amount, task_title), push_env)
    else:
        push_send_gcm(token, compensated_payload_gcm(amount, task_title), push_env)
    return True


def store_next_task_results_ts(user_id, task_id, timestamp_str, cat_id=None):
    """stores the given ts for the given user and task_id for later retrieval

    if cat_id is given, ignore the task_id.
    """
    try:
        if cat_id is None:
            from .task2 import get_cat_id_for_task_id
            cat_id = get_cat_id_for_task_id(task_id)

        # stored as string, can be None
        user_app_data = UserAppData.query.filter_by(user_id=user_id).first()
        user_app_data.next_task_ts_dict[cat_id] = timestamp_str
        db.session.add(user_app_data)

        commit_json_changed_to_orm(user_app_data, ['next_task_ts_dict'])
    except Exception as e:
        raise InvalidUsage('cant set task result ts. e:%s' % e)


def get_next_task_results_ts(user_id, cat_id):
    """return the task_result_ts field for the given user and task category"""
    try:
        user_app_data = UserAppData.query.filter_by(user_id=user_id).first()
        if user_app_data is None or user_app_data.next_task_ts_dict is None:
            return 0
        return user_app_data.next_task_ts_dict.get(cat_id, 0)  # can be None
    except Exception as e:
        log.error('cant get task result ts. e: %s' % e)
        raise InvalidUsage('cant get task result ts')


def get_users_for_engagement_push(scheme):
    """get user_ids for an engagement scheme"""
    from datetime import datetime, timedelta
    from .task2 import count_immediate_tasks
    import time
    start = time.time()

    user_ids = {OS_IOS: [], OS_ANDROID: []}

    if scheme not in ['engage-recent', 'engage-old']:
        # get all user_ids that have active tasks and
        # if scheme == 'engage-recent':
        #     - did not log in today and
        #     - last login was sometimes in the last 4 days
        #     - or they logged in exactly a week ago
        # if scheme = 'engage-old':
        #     - have not logged in, in the last 2 weeks
        log.info('engage-push: invalid scheme:%s' % scheme)
        raise InvalidUsage('invalid scheme: %s' % scheme)

    datetime_today = datetime.today()
    today = datetime.date(datetime_today)
    log.info('engage-push: in get_users_for_engagement_push with scheme %s, current date: %s' % (scheme, datetime_today))
    four_days_ago = datetime.date(datetime_today+ timedelta(days=-4))
    seven_days_ago = datetime.date(datetime_today + timedelta(days=-7))
    fourteen_days_ago = datetime.date(datetime_today) + timedelta(days=-14)
    skipped_users = dict(blacklist=[], country=[], active_today=[], not_active_recently=[], active_in_last_two_weeks=[],
                         no_active_task=[], old_version=[])

    results = db.engine.execute(
        "select public.user.user_id as user_id, public.user.os_type as os_type, user_app_data.app_ver as app_ver, "
        "user_app_data.update_at as last_updated, public.user.push_token as push_token from public.user inner "
        "join user_app_data on public.user.user_id = user_app_data.user_id where public.user.deactivated = \'f\' "
        "and public.user.push_token != \'\';")
    all_pushable_users = results.fetchall()
    end = time.time()
    diff = end - start
    log.info("engage-push: num of users to process %d, query took : %s" % (len(all_pushable_users), diff))
    for user in all_pushable_users:
        try:
            from .blacklisted_phone_numbers import is_userid_blacklisted

            if user.os_type == OS_ANDROID and LooseVersion(user.app_ver) <= LooseVersion("1.4.0"):
                skipped_users['old_version'].append(user.user_id)
                continue
            elif user.os_type == OS_IOS and LooseVersion(user.app_ver) <= LooseVersion("1.2.1"):
                skipped_users['old_version'].append(user.user_id)
                continue
            elif is_userid_blacklisted(user.user_id):
                skipped_users['blacklist'].append(user.user_id)
                continue
            elif should_block_user_by_country_code(user.user_id):
                skipped_users['country'].append(user.user_id)
                continue

            last_active_date = datetime.date(user.last_updated)

            if today == last_active_date:
                skipped_users['active_today'].append(user.user_id)
                continue
            elif scheme == 'engage-recent' and four_days_ago > last_active_date != seven_days_ago:
                skipped_users['not_active_recently'].append(user.user_id)
                continue
            elif scheme == 'engage-old' and fourteen_days_ago >= last_active_date:
                skipped_users['active_in_last_two_weeks'].append(user.user_id)
                continue

            immediate_tasks = count_immediate_tasks(user.user_id, None, False)

            if sum(int(item) for item in immediate_tasks.keys()) == 0:
                skipped_users['no_active_task'].append(user.user_id)
                continue

            if user.os_type == OS_IOS:
                user_ids[OS_IOS].append(user.user_id)
            else:
                user_ids[OS_ANDROID].append(user.user_id)

        except Exception as e:
            log.error('engage-push: caught exception trying to calculate push for user %s. e:%s' % (user.user_id, e))
            continue

    now = arrow.utcnow().shift(seconds=60).timestamp  # add a small time shift to account for calculation time

    log.info("engage-push: schema %s, time: %s - %s. Finished processing users. Here is the summary: ----------------"
             % (scheme, now, datetime_today))
    log.info("engage-push: skipped sending push notifications to"
             "\nengage-push:   %d old versions"
             "\nengage-push:   %d blacklisted users"
             "\nengage-push:   %d country blocked users"
             "\nengage-push:   %d active today"
             "\nengage-push:   %d last time active more than 4 days ago and not exactly week ago"
             "\nengage-push:   %d last time active was in the last 2 weeks"
             "\nengage-push:   %d no active task"
             % (len(skipped_users['old_version']),
                len(skipped_users['blacklist']),
                len(skipped_users['country']),
                len(skipped_users['active_today']),
                len(skipped_users['not_active_recently']),
                len(skipped_users['active_in_last_two_weeks']),
                len(skipped_users['no_active_task'])))
    log.info("engage-push: will send push notifications to %d android users, %d ios users"
             % (len(user_ids[OS_ANDROID]), len(user_ids[OS_IOS])))
    log.info("engage-push: will send to the following user_ids: %s" % user_ids)
    end = time.time()
    log.info("engage-push: %s total time it took: %s", now, end - start)
    log.info("------------------------------------------------------------------------ ")
    return user_ids


def get_userid_by_address(address):
    """return the userid associated with the given address or return None"""
    try:
        user = User.query.filter_by(public_address=address).first()
        if user is None:
            return None
        else:
            return user.user_id  # can be None
    except Exception as e:
        log.error('cant get user userid by address. Exception: %s' % e)
        raise


def get_address_by_userid(user_id):
    """return the address associated with the given user_id or return None"""
    try:
        user = User.query.filter_by(user_id=user_id).first()
        if user is None:
            return None
        else:
            return user.public_address  # can be None
    except Exception as e:
        log.error('cant get address by user_id. Exception: %s' % e)
        raise


def set_user_phone_number(user_id, number):
    """sets a phone number to the user's entry"""
    try:
        user = get_user(user_id)
        encrypted_number = app.encryption.encrypt(number)
        # allow (and ignore) re-submissions of the SAME number, but reject new numbers
        if user.enc_phone_number is not None:
            if user.enc_phone_number == encrypted_number:
                return  # all good, do nothing
            else:
                log.error('refusing to overwrite phone number for user_id %s' % user_id)
                raise InvalidUsage('trying to overwrite an existing phone number with a different one')
        else:
            user.enc_phone_number = encrypted_number
            db.session.add(user)
            db.session.commit()

        # does this number belong to another user? if so, de-activate the old user.
        deactivate_by_enc_phone_number(encrypted_number, user_id)

    except Exception as e:
        log.error('cant add phone number %s to user_id: %s. Exception: %s' % (number, user_id, e))
        raise


def get_active_user_id_by_phone(phone_number):
    try:
        encrypted_phone_number = app.encryption.encrypt(phone_number)
        user = User.query.filter_by(enc_phone_number=encrypted_phone_number).filter_by(deactivated=False).first()
        if user is None:
            return None
        else:
            return user.user_id  # can be None
    except Exception as e:
        log.error('cant get user address by phone. Exception: %s' % e)
        raise


def get_active_user_id_by_enc_phone(enc_phone_number):
    try:
        user = User.query.filter_by(enc_phone_number=enc_phone_number).filter_by(deactivated=False).first()
        if user is None:
            return None
        else:
            return user.user_id  # can be None
    except Exception as e:
        log.error('cant get active user_id by enc phone. Exception: %s' % e)
        raise


def get_user_ids_by_enc_phone(enc_phone_number):
    try:
        users = User.query.filter_by(enc_phone_number=enc_phone_number).all()
        return [user.user_id for user in users]
    except Exception as e:
        log.error('cant get user_ids by enc phone. Exception: %s' % e)
        raise


def get_unenc_phone_number_by_user_id(user_id):
    """return the un-enc phone number for the given userid"""
    #TODO get rid of this once migration to payment service is done
    try:
        return app.encryption.decrypt(get_enc_phone_number_by_user_id(user_id))
    except Exception as e:
        return None


def get_enc_phone_number_by_user_id(user_id):
    try:
        user = User.query.filter_by(user_id=user_id).first()
        if user is None:
            return None
        else:
            return user.enc_phone_number  # can be None
    except Exception as e:
        log.error('cant get user phone by user_id. Exception: %s' % e)
        raise


def is_user_phone_verified(user_id):
    """return true iff the user passed phone-verification"""
    return get_enc_phone_number_by_user_id(user_id) is not None


def get_all_user_id_by_phone(phone_number):
    try:
        encrypted_number = app.encryption.encrypt(phone_number)
        users = User.query.filter_by(enc_phone_number=encrypted_number).all()
        return [user.user_id for user in users]
    except Exception as e:
        log.error('cant get user(s) address by phone. Exception: %s' % e)
        raise


def match_phone_number_to_address(phone_number, sender_user_id):
    """get the address associated with this phone number"""
    # get the sender's un-enc phone number by the userid:
    sender_enc_phone_number = get_enc_phone_number_by_user_id(sender_user_id)
    if not sender_enc_phone_number:
        # should never happen while phone v. is active
        log.error('should never happen: cant get user\'s phone number. user_id: %s' % sender_user_id)

    sender_unenc_phone_number = app.encryption.decrypt(sender_enc_phone_number)
    enc_phone_num_1 = app.encryption.encrypt(parse_phone_number(phone_number, sender_unenc_phone_number))
    parsed_address = get_address_by_enc_phone_number(enc_phone_num_1)

    if parsed_address is None:
        # special handling for Israeli numbers: perhaps the number was stored in the db with a leading zero.
        # in the db: +9720527702891
        # from the client: 0527702891
        enc_phone_num_2 = app.encryption.encrypt('+972' + phone_number)
        parsed_address = get_address_by_enc_phone_number(enc_phone_num_2)
        if parsed_address:
            log.info('match_phone_number_to_address: applied special israeli-number logic to parse number: %s' % enc_phone_num_2)

    return parsed_address


def get_address_by_enc_phone_number(enc_phone_number):
    try:
        user = User.query.filter(User.enc_phone_number==enc_phone_number).filter_by(deactivated=False).first()
        if user is None:
            log.error('cant find user for encrypted phone number: %s' % enc_phone_number)
            return None
        else:
            return user.public_address  # can be None
    except Exception as e:
        log.error('cant get user address by phone. Exception: %s' % e)
        raise


def deactivate_by_enc_phone_number(enc_phone_number, new_user_id, activate_user=False):
    """deactivate any active user with the given phone number except the one with user_id

    this function deactivates the previous active user with the given phone number AND
    also duplicates his history into the new user.
    """
    new_user_id = str(new_user_id)

    if activate_user: # used in backup-restore
        log.info('activating user %s prior to deactivating all other user_ids' % new_user_id)
        db.engine.execute("update public.user set deactivated=false where user_id='%s'" % new_user_id)
    try:
        # find candidates to de-activate (except user_id)
        users = User.query.filter(User.enc_phone_number == enc_phone_number).filter(User.user_id != new_user_id).filter(User.deactivated == False).all()
        if users is []:
            return None  # nothing to do
        else:
            user_ids_to_deactivate = [user.user_id for user in users]
            log.info('deactivating user_ids: %s:' % user_ids_to_deactivate)
            # there should only ever be 1 at most, so log warning
            if len(user_ids_to_deactivate) > 1:
                log.warning('warning: too many user_ids to deactivate were found: %s' % user_ids_to_deactivate)

            for user_id_to_deactivate in user_ids_to_deactivate:
                # deactivate and copy task_history and next_task_ts
                db.engine.execute("update public.user set deactivated=true where enc_phone_number='%s' and user_id='%s'" % (enc_phone_number, user_id_to_deactivate))

                completed_tasks_query = "update user_app_data set completed_tasks_dict = Q.col1, next_task_ts_dict = Q.col2 from (select completed_tasks_dict as col1, next_task_ts_dict as col2 from user_app_data where user_id='%s') as Q where user_app_data.user_id = '%s'" % (user_id_to_deactivate, UUID(new_user_id))
                db.engine.execute(completed_tasks_query)

                # also delete the new user's history and plant the old user's history instead
                db.engine.execute("delete from public.user_task_results where user_id='%s'" % UUID(new_user_id))
                db.engine.execute("update public.user_task_results set user_id='%s' where user_id='%s'" % (UUID(new_user_id), user_id_to_deactivate))

    except Exception as e:
        log.error('cant deactivate_by_phone_number. Exception: %s' % e)
        raise


def get_associated_user_ids(user_id):
    """get a list of all the user_ids associated with the given user_id through phone-identification.
    the list also includes the original user_id.
    """
    user = get_user(user_id)
    if user.enc_phone_number is None:
        return [user_id]
    else:
        users = User.query.filter(User.enc_phone_number == user.enc_phone_number).all()
        return [str(user.user_id) for user in users]


def nuke_user_data(phone_number, nuke_all=False):
    """nuke user's data by phone number. by default only nuke the active user"""
    # find the active user with this number:
    if nuke_all:
        log.info('nuking all users with the phone number: %s' % phone_number)
        user_ids = get_all_user_id_by_phone(phone_number)
    else:
        # only the active user
        log.info('nuking the active user with the phone number: %s' % phone_number)
        user_ids = [get_active_user_id_by_phone(phone_number)]
    for user_id in user_ids:
        db.engine.execute("delete from good where tx_hash in (select tx_hash from transaction where user_id='%s')" % user_id)
        db.engine.execute("delete from public.transaction where user_id='%s'" % user_id)
        db.engine.execute("delete from public.user_task_results where user_id='%s'" % user_id)
        db.engine.execute('''update public.user_app_data set completed_tasks_dict='{}'::json where user_id=\'%s\'''' % user_id)
        db.engine.execute('''update public.user_app_data set next_task_memo_dict='{}'::json where user_id=\'%s\'''' % user_id)
        db.engine.execute('''update public.user_app_data set next_task_ts_dict='{}'::json where user_id=\'%s\'''' % user_id)

    # also erase the backup hints for the phone
    db.engine.execute("delete from phone_backup_hints where enc_phone_number='%s'" % app.encryption.encrypt(phone_number))

    return user_ids if len(user_ids) > 0 else None


def get_user_config(user_id):
    """return the user-specific config based on the global config"""
    os_type = get_user_os_type(user_id)
    global_config = get_global_config(os_type)
    user_app_data = get_user_app_data(user_id)

    # customize the p2p tx flag
    if config.P2P_TRANSFERS_ENABLED:

        if not user_app_data:
            log.warning('could not customize user config. disabling p2p txs for this user')
            global_config['p2p_enabled'] = False
        elif len(user_app_data.completed_tasks_dict.values()) < config.P2P_MIN_TASKS:
            global_config['p2p_enabled'] = False

    # turn off phone verification for older clients:
    disable_phone_verification = False
    disable_backup_nag = False
    if os_type == OS_ANDROID and LooseVersion(user_app_data.app_ver) <= LooseVersion(config.BLOCK_ONBOARDING_ANDROID_VERSION):
        disable_phone_verification = True
        disable_backup_nag = True
    elif os_type == OS_IOS and LooseVersion(user_app_data.app_ver) <= LooseVersion(config.BLOCK_ONBOARDING_IOS_VERSION):
        disable_phone_verification = True
        disable_backup_nag = True

    from .system_config import should_force_update, is_update_available
    if should_force_update(os_type, user_app_data.app_ver):
        global_config['force_update'] = True

    if is_update_available(os_type, user_app_data.app_ver):
        global_config['is_update_available'] = True

    if disable_phone_verification:
        log.info('disabling phone verification for userid %s' % user_id)
        global_config['phone_verification_enabled'] = False

    if disable_backup_nag:
        log.info('disabling backup nag for userid %s' % user_id)
        global_config['backup_nag'] = False


    log.info('user config for %s: %s' % (user_id, global_config))

    return global_config


def get_user_report(user_id):
    """return a json with all the interesting user-data"""
    log.info('getting user report for %s' % user_id)
    user_report = {}
    try:
        user = get_user(user_id)
        user_app_data = get_user_app_data(user_id)
        from .push_auth_token import get_token_by_user_id
        push_token_entry = get_token_obj_by_user_id(user_id)

        user_report['user_id'] = str(user.user_id)
        user_report['user_id_upper'] = str(user.user_id).upper()
        user_report['os'] = user.os_type
        user_report['app_ver'] = user_app_data.app_ver
        user_report['device_model'] = user.device_model
        user_report['phone_number'] = app.encryption.decrypt(user.enc_phone_number) if user.enc_phone_number else ''
        user_report['push_token'] = user.push_token
        user_report['time_zone'] = user.time_zone
        user_report['device_id'] = user.device_id
        user_report['created_at'] = user.created_at
        user_report['onboarded'] = str(user.onboarded)
        user_report['public_address'] = user.public_address
        user_report['deactivated'] = str(user.deactivated)
        user_report['completed_tasks'] = user_app_data.completed_tasks_dict
        user_report['next_task_ts'] = user_app_data.next_task_ts_dict
        user_report['next_task_memo'] = user_app_data.next_task_memo_dict
        user_report['last_app_launch'] = user_app_data.update_at
        user_report['ip_addr'] = user_app_data.ip_address
        user_report['country_iso_code'] = user_app_data.country_iso_code
        user_report['auth_token'] = {}
        user_report['auth_token']['sent_date'] = str(push_token_entry.send_date)
        user_report['auth_token']['ack_date'] = str(push_token_entry.ack_date)
        user_report['auth_token']['authenticated'] = str(push_token_entry.authenticated)
        user_report['auth_token']['token'] = str(push_token_entry.auth_token)
        user_report['package_id'] = str(user.package_id)
        user_report['screen_w'] = user.screen_w
        user_report['screen_h'] = user.screen_h
        user_report['screen_d'] = user.screen_d
        user_report['user_agent'] = user.user_agent
        user_report['truex_user_id'] = user.truex_user_id
        user_report['captcha_data'] = {}
        user_report['captcha_data']['should_solve_captcha'] = user_app_data.should_solve_captcha_ternary
        user_report['captcha_data']['history'] = user_app_data.captcha_history

        if user.enc_phone_number:
            ubh = get_user_backup_hints_by_enc_phone(user.enc_phone_number)
            if ubh:
                user_report['backup'] = {}
                user_report['backup']['hints'] = ubh.hints
                user_report['backup']['updated_at'] = ubh.updated_at

    except Exception as e:
        log.error('caught exception in get_user_report:%s' % e)
    return user_report


def get_unauthed_users():
    l = []
    results = db.engine.execute("select * from public.user, push_auth_token where public.user.user_id=push_auth_token.user_id and push_auth_token.authenticated=false and push_auth_token.send_date is not null and public.user.deactivated=false and public.user.enc_phone_number is not null;")
    res = results.fetchall()
    for item in res:
        l.append(str(item.user_id))

    return l


def restore_user_by_address(current_user_id, address):
    """given the user_id and the address, restore the device associated with this phone number to the given address"""

    # 1. find the phone number associated with this user_id
    #    and ensure the phone number has hints: deny restore from numbers with no hints.
    curr_enc_phone_number = get_enc_phone_number_by_user_id(current_user_id)
    if not curr_enc_phone_number:
        log.error('restore_user_by_address: cant find enc_phone_number for current user_id %s. aborting' % current_user_id)
        return None
    try:
        from .backup import get_user_backup_hints_by_enc_phone
        hints = get_user_backup_hints_by_enc_phone(curr_enc_phone_number)
    except Exception as e:
        log.error('cant get hints for enc_phone_number %s. e:%s' % (curr_enc_phone_number, e))
        return None
    else:
        if hints == []:
            log.error('no hints found for enc_phone_number %s. aborting' % curr_enc_phone_number)
            return None
        # else - found hints, okay to continue with the restore

    # 2. find the original user_id from the given address
    original_user_id = get_userid_by_address(address)
    if not original_user_id:
        log.error('restore_user_by_address: cant find the original user_id for the given address. aborting')
        return None

    # ensure the user_id actually belongs to the same phone number as the current user_id
    original_enc_phone_number = get_enc_phone_number_by_user_id(original_user_id)
    if not original_enc_phone_number or (original_enc_phone_number != curr_enc_phone_number):
        log.info('restore_user_by_address: phone number mismatch. current=%s, original=%s' % (curr_enc_phone_number, original_enc_phone_number))
        return None

    # 3. activate the original user, deactivate the current one and
    # 4. copy the tasks from the current_user_id back onto the original user_id
    deactivate_by_enc_phone_number(curr_enc_phone_number, original_user_id, True)

    # copy the (potentially new device data and new push token to the old user)
    if not migrate_restored_user_data(current_user_id, original_user_id):
        log.error('restore_user_by_address: failed to migrate device-specific data from the temp user_id %s to the restored user-id %s' % (current_user_id, original_user_id))

    # 5. return the (now active) original user_id.
    log.info('restore_user_by_address: successfully restored the original user_id: %s' % original_user_id)
    return original_user_id


def migrate_restored_user_data(temp_user_id, restored_user_id):
    """copy some of the fresher, device-related fields into a restored user"""
    try:
        temp_user = get_user(temp_user_id)
        restored_user = get_user(restored_user_id)

        temp_user_app_data = get_user_app_data(temp_user_id)
        restored_user_app_data = get_user_app_data(restored_user_id)

        restored_user.os_type = temp_user.os_type
        restored_user.device_model = temp_user.device_model
        restored_user.push_token = temp_user.push_token
        restored_user.time_zone = temp_user.time_zone
        restored_user.device_id = temp_user.device_id
        restored_user.auth_token = temp_user.auth_token
        restored_user.package_id = temp_user.package_id
        restored_user.screen_w = temp_user.screen_w
        restored_user.screen_h = temp_user.screen_h
        restored_user.screen_d = temp_user.screen_d
        restored_user.user_agent = temp_user.user_agent

        restored_user_app_data.app_ver = temp_user_app_data.app_ver
        restored_user_app_data.ip_address = temp_user_app_data.ip_address
        restored_user_app_data.app_ver = temp_user_app_data.app_ver
        restored_user_app_data.country_iso_code = temp_user_app_data.country_iso_code

        db.session.add(restored_user)
        db.session.add(restored_user_app_data)
        db.session.commit()
    except Exception as e:
        log.error('failed to migrate resteod used data. e=%s' % e)
        return False
    else:
        return True


def should_block_user_by_client_version(user_id):
    """determines whether this user_id should be blocked based on the client version"""
    from distutils.version import LooseVersion
    try:
        os_type = get_user_os_type(user_id)
        client_version = get_user_app_data(user_id).app_ver
    except Exception as e:
        log.error('should_block_user_by_client_version: cant get os_type/client version for user_id %s' % user_id)
        return False
    else:
        if os_type == OS_ANDROID:
            if LooseVersion(client_version) <= LooseVersion(config.BLOCK_ONBOARDING_ANDROID_VERSION):
                log.info('should block android version (%s), config: %s' % (client_version, config.BLOCK_ONBOARDING_ANDROID_VERSION))
                return True
        else: # OS_IOS
            if LooseVersion(client_version) <= LooseVersion(config.BLOCK_ONBOARDING_IOS_VERSION):
                log.info('should block ios version (%s), config: %s' % (client_version, config.BLOCK_ONBOARDING_IOS_VERSION))
                return True
    return False


def should_block_user_by_phone_prefix(user_id):
    """determines whether to block a user by her phone prefix"""
    try:
        phone_number = get_unenc_phone_number_by_user_id(user_id)
        for prefix in app.blocked_phone_prefixes:
            if phone_number.find(prefix) == 0:
                log.info('should_block_user_by_phone_prefix: should block user_id %s with phone number %s' % (user_id, phone_number))
                return True
    except Exception as e:
        log.error('should_block_user_by_phone_prefix for userid %s: caught exception: %s' % (user_id, e))
    return False


def should_allow_user_by_phone_prefix(user_id):
    """determines whether to allow a user based on her phone prefix"""
    try:
        phone_number = get_unenc_phone_number_by_user_id(user_id)
        if not phone_number:
            log.info('should_allow_user_by_phone_prefix - no phone number. allowing user')
            return True

        for prefix in app.allowed_phone_prefixes:
            if phone_number.find(prefix) == 0:
                return True
    except Exception as e:
        log.error('should_allow_user_by_phone_prefix for userid %s: caught exception: %s' % (user_id, e))

    log.info('should_allow_user_by_phone_prefix: not allowing user_id %s with phone number %s' % (user_id, phone_number))
    return False


def should_block_user_by_country_code(user_id):
    """determines whether to block users by their country code"""
    try:
        country_code = get_user_country_code(user_id)
        if country_code in app.blocked_country_codes:
            log.info('should_block_user_by_country_code: should block user_id %s with country_code %s' % (user_id, country_code))
            return True
    except Exception as e:
        log.error('should_block_user_by_country_code for userid %s: caught exception %s' % (user_id, e))
        return False


def delete_all_user_data(user_id, are_u_sure=False):
    """delete all user data from the db. this erases all the users associated with the same phone number"""
    log.info('preparing to delete all info related to user_id %s' % user_id)

    delete_user_goods = '''delete from good where good.order_id in (select tx_info->>'memo' as order_id from transaction where user_id='%s');'''
    delete_user_transactions = '''delete from transaction where user_id='%s';'''
    delete_user_orders = '''delete from public.order where user_id='%s';'''
    delete_p2p_txs_sent = '''delete from p2_p_transaction where sender_user_id='%s';'''
    delete_p2p_txs_received = '''delete from p2_p_transaction where receiver_user_id='%s';'''
    delete_phone_backup_hints = '''delete from phone_backup_hints where enc_phone_number in (select enc_phone_number from public.user where user_id='%s');'''
    delete_task_results = '''delete from public.user_task_results where user_id='%s';'''
    delete_auth_token = '''delete from public.push_auth_token where user_id='%s';'''
    delete_app_data = '''delete from public.user_app_data where user_id='%s';'''
    delete_user = '''delete from public.user where user_id='%s';'''

    # get all the user_ids associated with this user's phone number:
    enc_phone = get_enc_phone_number_by_user_id(user_id)
    if not enc_phone:
        log.error('refusing to delete data for user with no phone number')
        return
    uids = get_user_ids_by_enc_phone(enc_phone)
    log.info('WARNING: will delete all data of the following %s user_ids: %s' % (len(uids), uids))
    if not are_u_sure:
        log.error('refusing to delete users. if youre sure, send with force flag')
        return

    for uid in uids:
        log.info('deleting all data related to user_id %s' % uid)
        log.info('deleting goods...')
        db.engine.execute(delete_user_goods % uid)
        log.info('deleting orders...')
        db.engine.execute(delete_user_orders % uid)
        log.info('deleting txs...')
        db.engine.execute(delete_user_transactions % uid)
        log.info('deleting p2p txs...')
        db.engine.execute(delete_p2p_txs_sent % uid)
        db.engine.execute(delete_p2p_txs_received % uid)
        log.info('deleting backup hints...')
        db.engine.execute(delete_phone_backup_hints % uid)
        log.info('deleting task results...')
        db.engine.execute(delete_task_results % uid)
        log.info('deleting auth tokens...')
        db.engine.execute(delete_auth_token % uid)
        log.info('deleting user data...')
        db.engine.execute(delete_app_data % uid)
        db.engine.execute(delete_user % uid)
        log.info('done with user_id: %s' % uid)


def count_registrations_for_phone_number(phone_number):
    """returns the number of registrations for the given unenc phone number"""
    enc_phone_number = app.encryption.encrypt(phone_number)
    count_users_with_enc_phone_number = '''select count(*) from public.user where enc_phone_number='%s';'''
    count = db.engine.execute(count_users_with_enc_phone_number % enc_phone_number).scalar()
    return count if count else 0


def count_missing_txs():
    """counts the number of users with missing txs in their data == users we owe money to"""
    from datetime import datetime
    todays_date = str(datetime.today()).split(' ')[0] + '%%'  # convert to sql date format with LIKE '2018-10-12%', double the '%' sign for escaping.
    sql_stmt = '''SELECT count(*) FROM user_task_results u left join transaction t on u.user_id = t.user_id where t.tx_hash is null  and u.update_at::varchar LIKE '%s';''' % todays_date
    missing_txs_today = db.engine.execute(sql_stmt)
    missing_txs_today = missing_txs_today.scalar()
    log.info('missing txs today: %s' % missing_txs_today)
    gauge_metric('missing-txs', missing_txs_today)

def re_register_all_users():
    """sends a push message to all users with a phone"""
    all_phoned_users = User.query.filter(User.enc_phone_number != None).filter(User.deactivated == False).all()
    log.info('sending register to %s users' % len(all_phoned_users))
    counter = 0
    for user in all_phoned_users:

        if user.os_type != OS_ANDROID:
            log.info('skipping user with ios client')
            continue
        user_app_data = get_user_app_data(user.user_id)
        from distutils.version import LooseVersion
        if user_app_data.app_ver is None or LooseVersion(user_app_data.app_ver) < LooseVersion('1.2.1'):
            log.info('skipping user with client ver %s' % user_app_data.app_ver)

        sleep(0.5)  # lets not choke the server. this can really hurt us if done too fast.
        send_push_register(user.user_id)
        counter = counter + 1


# TODO cache this
def get_personalized_categories_header_message(user_id, message_type='default'):
    """returns a user-specific message to be shown in the categories page"""
    # nothing to personalize yet - just return the text from the db.
    from .system_config import get_categories_extra_data
    return get_categories_extra_data()[message_type] # either 'default' or 'no_tasks'


def task20_migrate_user_to_tasks2(user_id):
    """this function migrates user data from tasks1.0 to tasks2.0

    a user can only migrate once.

    Specifically: the user completed_tasks, next_task_ts and next_task_memo must be reformed.
    - previously completed tasks must be kept, but mapped into their category
    - for each category, the next_ts must be set to the beginning of the epoch
    - a next memo must be calculated for each category
    """
    from .category import get_all_cat_ids
    all_cat_ids = get_all_cat_ids()
    uad = get_user_app_data(user_id)

    if uad.completed_tasks_dict:
        if '0' in uad.completed_tasks_dict.keys():
            log.info('task20_migrate_user_to_tasks2: user %s was already migrated' % user_id)
            return

    # create a dict of arrays (for all currently existing categories)
    new_completed_tasks_dict = {}
    for cat_id in all_cat_ids:
        new_completed_tasks_dict[cat_id] = []

    # populate the dict with previously solved tasks
    print('task20_migrate_user_to_tasks2: task 1.0 tasks list for user_id: %s: %s' % (user_id, uad.completed_tasks))
    completed_tasks = json.loads(uad.completed_tasks)
    tasks20_task_ids_list = tasks20_get_tasks_dict().keys()
    for task_id in completed_tasks:
        if task_id in tasks20_task_ids_list:  # some tasks were not migrated to tasks2.0 - just ignore them
            new_completed_tasks_dict[tasks20_task_id_to_category_id(task_id)].append(task_id)
    uad.completed_tasks_dict = new_completed_tasks_dict

    # create and populate dicts for memos and ts's
    epoch_start = arrow.get('0').timestamp
    next_task_ts_dict = {}
    next_task_memo_dict = {}
    for cat_id in all_cat_ids:
        next_task_ts_dict[cat_id] = epoch_start
        next_task_memo_dict[cat_id] = generate_order_id()
    uad.next_task_ts_dict = next_task_ts_dict
    uad.next_task_memo_dict = next_task_memo_dict

    commit_json_changed_to_orm(uad, ['completed_tasks_dict', 'next_task_ts_dict', 'next_task_memo_dict'])

    log.info('migrated user_id %s to tasks2.0: tasks: %s, ts: %s, memo: %s' % (user_id, uad.completed_tasks_dict , uad.next_task_ts_dict, uad.next_task_memo_dict))


def tasks20_task_id_to_category_id(task_id):
    """this function maps task_ids to their category_id, for migration (only)"""
    #TODO map tasks to categories here
    return tasks20_get_tasks_dict()[task_id]['cat_id']


def add_task_to_completed_tasks1(user_id, task_id):
    """DEBUG - to be used only for task2.0 migration tests. remove afterwards"""
    user_app_data = get_user_app_data(user_id)
    completed_tasks = json.loads(user_app_data.completed_tasks)

    if task_id in completed_tasks:
        log.info('task_id %s already in completed_tasks for user_id %s - ignoring' % (task_id, user_id))
    else:
        completed_tasks.append(task_id)
        user_app_data.completed_tasks = json.dumps(completed_tasks)
        db.session.add(user_app_data)
        db.session.commit()
        log.info('user %s tasks 1.0 completed tasks: %s' % (user_id ,completed_tasks))
    return True


def count_completed_tasks(user_id):
    total_completed_tasks = 0
    user_app_data = get_user_app_data(user_id)
    for tasks_in_categories in user_app_data.completed_tasks_dict.values():
        total_completed_tasks = total_completed_tasks + len(tasks_in_categories)
    return total_completed_tasks


# this is the data we got from Sarit regarding tasks migration. remove this once migration is completed
def tasks20_get_tasks_dict():
    """this function returns a dict with all the tasks2.0 migration

    note that some tasks may be missing - these are simply not migrated
    """
    tasks_migration_array = [
    {
      "task_id": "151",
      "catgory": "0",
      "position": 0,
      "delay_days": 1
    },
    {
      "task_id": "152",
      "catgory": "0",
      "position": 1,
      "delay_days": 1
    },
    {
      "task_id": "159",
      "catgory": "0",
      "position": 2,
      "delay_days": 1
    },
    {
      "task_id": "163",
      "catgory": "0",
      "position": 3,
      "delay_days": 1
    },
    {
      "task_id": "164",
      "catgory": "0",
      "position": 4,
      "delay_days": 1
    },
    {
      "task_id": "168",
      "catgory": "0",
      "position": 5,
      "delay_days": 1
    },
    {
      "task_id": "173",
      "catgory": "0",
      "position": 6,
      "delay_days": 1
    },
    {
      "task_id": "178",
      "catgory": "0",
      "position": 7,
      "delay_days": 1
    },
    {
      "task_id": "182",
      "catgory": "0",
      "position": 8,
      "delay_days": 1
    },
    {
      "task_id": "188",
      "catgory": "0",
      "position": 9,
      "delay_days": 1
    },
    {
      "task_id": "77",
      "catgory": "0",
      "position": 10,
      "delay_days": 1
    },
    {
      "task_id": "193",
      "catgory": "0",
      "position": 11,
      "delay_days": 1
    },
    {
      "task_id": "194",
      "catgory": "0",
      "position": 12,
      "delay_days": 1
    },
    {
      "task_id": "3",
      "catgory": "1",
      "position": 0,
      "delay_days": 1
    },
    {
      "task_id": "4",
      "catgory": "1",
      "position": 1,
      "delay_days": 1
    },
    {
      "task_id": "5",
      "catgory": "1",
      "position": 2,
      "delay_days": 1
    },
    {
      "task_id": "6",
      "catgory": "1",
      "position": 3,
      "delay_days": 1
    },
    {
      "task_id": "7",
      "catgory": "1",
      "position": 4,
      "delay_days": 1
    },
    {
      "task_id": "13",
      "catgory": "1",
      "position": 5,
      "delay_days": 1
    },
    {
      "task_id": "16",
      "catgory": "1",
      "position": 6,
      "delay_days": 1
    },
    {
      "task_id": "17",
      "catgory": "1",
      "position": 7,
      "delay_days": 1
    },
    {
      "task_id": "18",
      "catgory": "1",
      "position": 8,
      "delay_days": 1
    },
    {
      "task_id": "21",
      "catgory": "1",
      "position": 9,
      "delay_days": 1
    },
    {
      "task_id": "22",
      "catgory": "1",
      "position": 10,
      "delay_days": 1
    },
    {
      "task_id": "23",
      "catgory": "1",
      "position": 11,
      "delay_days": 1
    },
    {
      "task_id": "29",
      "catgory": "1",
      "position": 12,
      "delay_days": 1
    },
    {
      "task_id": "31",
      "catgory": "1",
      "position": 13,
      "delay_days": 1
    },
    {
      "task_id": "34",
      "catgory": "1",
      "position": 14,
      "delay_days": 1
    },
    {
      "task_id": "36",
      "catgory": "1",
      "position": 15,
      "delay_days": 1
    },
    {
      "task_id": "44",
      "catgory": "1",
      "position": 16,
      "delay_days": 1
    },
    {
      "task_id": "52",
      "catgory": "1",
      "position": 17,
      "delay_days": 1
    },
    {
      "task_id": "56",
      "catgory": "1",
      "position": 18,
      "delay_days": 1
    },
    {
      "task_id": "62",
      "catgory": "1",
      "position": 19,
      "delay_days": 1
    },
    {
      "task_id": "63",
      "catgory": "1",
      "position": 20,
      "delay_days": 1
    },
    {
      "task_id": "64",
      "catgory": "1",
      "position": 21,
      "delay_days": 1
    },
    {
      "task_id": "73",
      "catgory": "1",
      "position": 22,
      "delay_days": 1
    },
    {
      "task_id": "74",
      "catgory": "1",
      "position": 23,
      "delay_days": 1
    },
    {
      "task_id": "76",
      "catgory": "1",
      "position": 24,
      "delay_days": 1
    },
    {
      "task_id": "81",
      "catgory": "1",
      "position": 25,
      "delay_days": 1
    },
    {
      "task_id": "122",
      "catgory": "1",
      "position": 26,
      "delay_days": 1
    },
    {
      "task_id": "125",
      "catgory": "1",
      "position": 27,
      "delay_days": 1
    },
    {
      "task_id": "126",
      "catgory": "1",
      "position": 28,
      "delay_days": 0
    },
    {
      "task_id": "127",
      "catgory": "1",
      "position": 29,
      "delay_days": 1
    },
    {
      "task_id": "131",
      "catgory": "1",
      "position": 30,
      "delay_days": 0
    },
    {
      "task_id": "133",
      "catgory": "1",
      "position": 31,
      "delay_days": 1
    },
    {
      "task_id": "134",
      "catgory": "1",
      "position": 32,
      "delay_days": 0
    },
    {
      "task_id": "135",
      "catgory": "1",
      "position": 33,
      "delay_days": 1
    },
    {
      "task_id": "138",
      "catgory": "1",
      "position": 34,
      "delay_days": 0
    },
    {
      "task_id": "139",
      "catgory": "1",
      "position": 35,
      "delay_days": 1
    },
    {
      "task_id": "140",
      "catgory": "1",
      "position": 36,
      "delay_days": 0
    },
    {
      "task_id": "141",
      "catgory": "1",
      "position": 37,
      "delay_days": 1
    },
    {
      "task_id": "143",
      "catgory": "1",
      "position": 38,
      "delay_days": 0
    },
    {
      "task_id": "144",
      "catgory": "1",
      "position": 39,
      "delay_days": 1
    },
    {
      "task_id": "145",
      "catgory": "1",
      "position": 40,
      "delay_days": 0
    },
    {
      "task_id": "147",
      "catgory": "1",
      "position": 41,
      "delay_days": 1
    },
    {
      "task_id": "148",
      "catgory": "1",
      "position": 42,
      "delay_days": 0
    },
    {
      "task_id": "149",
      "catgory": "1",
      "position": 43,
      "delay_days": 1
    },
    {
      "task_id": "153",
      "catgory": "1",
      "position": 44,
      "delay_days": 0
    },
    {
      "task_id": "154",
      "catgory": "1",
      "position": 45,
      "delay_days": 1
    },
    {
      "task_id": "155",
      "catgory": "1",
      "position": 46,
      "delay_days": 0
    },
    {
      "task_id": "136",
      "catgory": "1",
      "position": 47,
      "delay_days": 1
    },
    {
      "task_id": "157",
      "catgory": "1",
      "position": 48,
      "delay_days": 1
    },
    {
      "task_id": "158",
      "catgory": "1",
      "position": 49,
      "delay_days": 0
    },
    {
      "task_id": "161",
      "catgory": "1",
      "position": 50,
      "delay_days": 1
    },
    {
      "task_id": "162",
      "catgory": "1",
      "position": 51,
      "delay_days": 0
    },
    {
      "task_id": "166",
      "catgory": "1",
      "position": 52,
      "delay_days": 1
    },
    {
      "task_id": "167",
      "catgory": "1",
      "position": 53,
      "delay_days": 0
    },
    {
      "task_id": "169",
      "catgory": "1",
      "position": 54,
      "delay_days": 1
    },
    {
      "task_id": "170",
      "catgory": "1",
      "position": 55,
      "delay_days": 0
    },
    {
      "task_id": "171",
      "catgory": "1",
      "position": 56,
      "delay_days": 1
    },
    {
      "task_id": "174",
      "catgory": "1",
      "position": 57,
      "delay_days": 0
    },
    {
      "task_id": "175",
      "catgory": "1",
      "position": 58,
      "delay_days": 1
    },
    {
      "task_id": "176",
      "catgory": "1",
      "position": 59,
      "delay_days": 0
    },
    {
      "task_id": "179",
      "catgory": "1",
      "position": 60,
      "delay_days": 1
    },
    {
      "task_id": "180",
      "catgory": "1",
      "position": 61,
      "delay_days": 0
    },
    {
      "task_id": "181",
      "catgory": "1",
      "position": 62,
      "delay_days": 1
    },
    {
      "task_id": "185",
      "catgory": "1",
      "position": 63,
      "delay_days": 0
    },
    {
      "task_id": "186",
      "catgory": "1",
      "position": 64,
      "delay_days": 1
    },
    {
      "task_id": "187",
      "catgory": "1",
      "position": 65,
      "delay_days": 0
    },
    {
      "task_id": "190",
      "catgory": "1",
      "position": 66,
      "delay_days": 1
    },
    {
      "task_id": "191",
      "catgory": "1",
      "position": 67,
      "delay_days": 0
    },
    {
      "task_id": "192",
      "catgory": "1",
      "position": 68,
      "delay_days": 1
    },
    {
      "task_id": "88",
      "catgory": "2",
      "position": 0,
      "delay_days": 1
    },
    {
      "task_id": "92",
      "catgory": "2",
      "position": 1,
      "delay_days": 1
    },
    {
      "task_id": "97",
      "catgory": "2",
      "position": 2,
      "delay_days": 1
    },
    {
      "task_id": "101",
      "catgory": "2",
      "position": 3,
      "delay_days": 1
    },
    {
      "task_id": "105",
      "catgory": "2",
      "position": 4,
      "delay_days": 1
    },
    {
      "task_id": "110",
      "catgory": "2",
      "position": 5,
      "delay_days": 1
    },
    {
      "task_id": "113",
      "catgory": "2",
      "position": 6,
      "delay_days": 1
    },
    {
      "task_id": "117",
      "catgory": "2",
      "position": 7,
      "delay_days": 1
    },
    {
      "task_id": "119",
      "catgory": "2",
      "position": 8,
      "delay_days": 1
    },
    {
      "task_id": "121",
      "catgory": "2",
      "position": 9,
      "delay_days": 1
    },
    {
      "task_id": "103",
      "catgory": "2",
      "position": 10,
      "delay_days": 1
    },
    {
      "task_id": "124",
      "catgory": "2",
      "position": 11,
      "delay_days": 1
    },
    {
      "task_id": "128",
      "catgory": "2",
      "position": 12,
      "delay_days": 1
    },
    {
      "task_id": "132",
      "catgory": "2",
      "position": 13,
      "delay_days": 1
    },
    {
      "task_id": "137",
      "catgory": "2",
      "position": 14,
      "delay_days": 1
    },
    {
      "task_id": "142",
      "catgory": "2",
      "position": 15,
      "delay_days": 1
    },
    {
      "task_id": "146",
      "catgory": "2",
      "position": 16,
      "delay_days": 1
    },
    {
      "task_id": "150",
      "catgory": "2",
      "position": 17,
      "delay_days": 1
    },
    {
      "task_id": "156",
      "catgory": "2",
      "position": 18,
      "delay_days": 1
    },
    {
      "task_id": "160",
      "catgory": "2",
      "position": 19,
      "delay_days": 1
    },
    {
      "task_id": "165",
      "catgory": "2",
      "position": 20,
      "delay_days": 1
    },
    {
      "task_id": "172",
      "catgory": "2",
      "position": 21,
      "delay_days": 1
    },
    {
      "task_id": "177",
      "catgory": "2",
      "position": 22,
      "delay_days": 1
    },
    {
      "task_id": "183",
      "catgory": "2",
      "position": 23,
      "delay_days": 1
    },
    {
      "task_id": "189",
      "catgory": "2",
      "position": 24,
      "delay_days": 1
    },
    {
      "task_id": "195",
      "catgory": "2",
      "position": 25,
      "delay_days": 1
    },
    {
      "task_id": "0",
      "catgory": "3",
      "position": 0,
      "delay_days": 1
    },
    {
      "task_id": "1",
      "catgory": "3",
      "position": 1,
      "delay_days": 6
    },
    {
      "task_id": "2",
      "catgory": "3",
      "position": 2,
      "delay_days": 6
    },
    {
      "task_id": "19",
      "catgory": "3",
      "position": 3,
      "delay_days": 6
    },
    {
      "task_id": "20",
      "catgory": "3",
      "position": 4,
      "delay_days": 6
    },
    {
      "task_id": "33",
      "catgory": "3",
      "position": 5,
      "delay_days": 6
    },
    {
      "task_id": "41",
      "catgory": "3",
      "position": 6,
      "delay_days": 6
    },
    {
      "task_id": "49",
      "catgory": "3",
      "position": 7,
      "delay_days": 6
    },
    {
      "task_id": "53",
      "catgory": "3",
      "position": 8,
      "delay_days": 6
    },
    {
      "task_id": "54",
      "catgory": "3",
      "position": 9,
      "delay_days": 6
    },
    {
      "task_id": "60",
      "catgory": "3",
      "position": 10,
      "delay_days": 6
    },
    {
      "task_id": "61",
      "catgory": "3",
      "position": 11,
      "delay_days": 6
    },
    {
      "task_id": "65",
      "catgory": "3",
      "position": 12,
      "delay_days": 6
    },
    {
      "task_id": "10",
      "catgory": "4",
      "position": 0,
      "delay_days": 1
    },
    {
      "task_id": "15",
      "catgory": "4",
      "position": 1,
      "delay_days": 5
    },
    {
      "task_id": "28",
      "catgory": "4",
      "position": 2,
      "delay_days": 5
    },
    {
      "task_id": "46",
      "catgory": "4",
      "position": 3,
      "delay_days": 5
    },
    {
      "task_id": "48",
      "catgory": "4",
      "position": 4,
      "delay_days": 5
    },
    {
      "task_id": "50",
      "catgory": "4",
      "position": 5,
      "delay_days": 5
    },
    {
      "task_id": "57",
      "catgory": "4",
      "position": 6,
      "delay_days": 5
    }]

    tasks_dict = {}
    for item in tasks_migration_array:
        task_id = item['task_id']
        cat_id = item['catgory']
        position = item['position']
        delay_days = item['delay_days']

        tasks_dict[task_id] = {'cat_id': cat_id, 'position': position, 'delay_days': delay_days}
    return tasks_dict


def tasks20_get_tasks_dict_stage():
    """this function returns a dict with all the tasks2.0 migration

    note that some tasks may be missing - these are simply not migrated
    """
    tasks_migration_array = [
    {
      "task_id": "3",
      "catgory": "1",
      "position": 0,
      "delay_days": 1
    },
    {
      "task_id": "4",
      "catgory": "1",
      "position": 1,
      "delay_days": 1
    },
    {
      "task_id": "5",
      "catgory": "1",
      "position": 2,
      "delay_days": 1
    },
    {
      "task_id": "6",
      "catgory": "1",
      "position": 3,
      "delay_days": 1
    },
    {
      "task_id": "7",
      "catgory": "1",
      "position": 4,
      "delay_days": 1
    },
    {
      "task_id": "13",
      "catgory": "1",
      "position": 5,
      "delay_days": 1
    }]

    tasks_dict = {}
    for item in tasks_migration_array:
        task_id = item['task_id']
        cat_id = item['catgory']
        position = item['position']
        delay_days = item['delay_days']

        tasks_dict[task_id] = {'cat_id': cat_id, 'position': position, 'delay_days': delay_days}
    return tasks_dict
