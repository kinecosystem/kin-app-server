"""The User model"""
from sqlalchemy_utils import UUIDType
from sqlalchemy.dialects.postgresql import INET

from kinappserver import db, config, app
from kinappserver.utils import InvalidUsage, OS_IOS, OS_ANDROID, parse_phone_number, increment_metric, gauge_metric, get_global_config, generate_memo, OS_ANDROID, OS_IOS, find_max_task
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
            print('failed to parse timezone: %s. using default' % tz)
            print(e)
            return int(DEFAULT_TIME_ZONE)

    is_new_user = False
    try:
        user = get_user(user_id)
        print('user %s already exists, updating data' % user_id)
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
        user_app_data.app_ver = app_ver
        user_app_data.next_task_ts = arrow.utcnow().timestamp
        user_app_data.next_task_memo = generate_memo()
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
        print('cant get user_id by truex_user_id. Exception: %s' % e)
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
    next_task_ts = db.Column(db.String(40), primary_key=False, nullable=True)  # the ts for th next task, can be None
    next_task_memo = db.Column(db.String(len(generate_memo())), primary_key=False, nullable=True)  # the memo for the user's next task.
    ip_address = db.Column(INET) # the user's last known ip
    country_iso_code = db.Column(db.String(10))  # country iso code based on last ip
    should_solve_captcha = db.Column(db.Boolean, unique=False, default=False) # obsolete, to be removed
    captcha_history = db.Column(db.JSON)
    should_solve_captcha_ternary = db.Column(db.Integer, unique=False, default=-1, nullable=False)  # -1 = no captcha, 0 = show captcha on next task, 1 = captcha required


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
            print('captcha_solved: user %s doesnt need to solve captcha' % user_id)
            return

        userAppData.should_solve_captcha_ternary = -1 # reset back to -1 (doesn't need to pass captcha)

        # save previous hints
        if userAppData.captcha_history is None:
            userAppData.captcha_history = [{'date': now, 'app_ver': userAppData.app_ver}]
        else:
            userAppData.captcha_history.append({'date': now, 'app_ver ': userAppData.app_ver})
        # turns out sqlalchemy cant detect json updates, and requires manual flagging:
        # https://stackoverflow.com/questions/30088089/sqlalchemy-json-typedecorator-not-saving-correctly-issues-with-session-commit/34339963#34339963
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(userAppData, "captcha_history")

        db.session.add(userAppData)
        db.session.commit()
    except Exception as e:
        print('failed to mark captcha solved for user_id %s' % user_id)
        print(e)


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
            print('could not calc country iso code for %s' % ip_address)
        db.session.add(userAppData)
        db.session.commit()
    except Exception as e:
        print(e)
        raise InvalidUsage('cant set user ip address')
    else:
        print('updated user %s ip to %s' % (user_id, ip_address))


def get_user_country_code(user_id):
    return UserAppData.query.filter_by(user_id=user_id).one().country_iso_code  # can be null


def get_next_task_memo(user_id):
    """returns the next memo for this user"""
    next_memo = None
    try:
        userAppData = UserAppData.query.filter_by(user_id=user_id).first()
        next_memo = userAppData.next_task_memo
        if next_memo is None:
            # set an initial value
            return get_and_replace_next_task_memo()
    except Exception as e:
        print(e)
        raise InvalidUsage('cant get next memo')
    else:
        return next_memo


def get_and_replace_next_task_memo(user_id):
    """return the next memo for this user and replace it with another"""
    next_memo = None
    try:
        userAppData = UserAppData.query.filter_by(user_id=user_id).first()
        next_memo = userAppData.next_task_memo
        userAppData.next_task_memo = generate_memo()
        db.session.add(userAppData)
        db.session.commit()
    except Exception as e:
        print(e)
        raise InvalidUsage('cant set next memo')
    else:
        return next_memo


def list_all_users_app_data():
    """returns a dict of all the user-app-data"""
    response = {}
    users = UserAppData.query.order_by(UserAppData.user_id).all()
    for user in users:
        response[user.user_id] = {'user_id': user.user_id,  'app_ver': user.app_ver, 'update': user.update_at, 'completed_tasks': user.completed_tasks}
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
        print('Error: could not get push data for user %s' % user_id)
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
        print('cant push to user %s: no push token' % user_id)
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
        print('cant push to user %s: no push token' % user_id)
        return False
    if os_type == OS_IOS:
        from kinappserver.push import auth_push_apns, generate_push_id
        push_send_apns(token, auth_push_apns(generate_push_id(), str(auth_token), str(user_id)), push_env)
        push_send_apns(token, auth_push_apns(generate_push_id(), str(auth_token), str(user_id)), push_env) # send twice?
        print('sent apns auth token to user %s' % user_id)
    else:
        from kinappserver.push import gcm_payload, generate_push_id
        payload = gcm_payload('auth_token', generate_push_id(), {'type': 'auth_token', 'user_id': str(user_id), 'token': str(auth_token)})
        push_send_gcm(token, payload, push_env)
        print('sent gcm auth token to user %s' % user_id)

    if not set_send_date(user_id):
        print('could not set the send-date for auth-token for user_id: %s' % user_id)

    increment_metric('auth-token-sent')

    return True


def send_push_register(user_id):
    """send a message indicating that the client should re-register"""
    os_type, token, push_env = get_user_push_data(user_id)
    if token is None:
        print('cant push to user %s: no push token' % user_id)
        return False
    if os_type == OS_IOS:
        from kinappserver.push import register_push_apns, generate_push_id
        push_send_apns(token, register_push_apns(generate_push_id()), push_env)
        print('sent apns register to user %s' % user_id)
    else:
        from kinappserver.push import gcm_payload, generate_push_id
        payload = gcm_payload('register', generate_push_id(), {'type': 'register'})
        push_send_gcm(token, payload, push_env)
        print('sent gcm register to user %s' % user_id)

    increment_metric('register-push-sent')

    return True


def send_engagement_push(user_id, push_type):
    """sends an engagement push message to the user with the given user_id"""
    os_type, token, push_env = get_user_push_data(user_id)

    if token is None:
        print('cant push to user %s: no push token' % user_id)
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
        print('cant push to user %s: no push token' % user_id)
        return False

    if os_type == OS_IOS:
        push_send_apns(token, compensated_payload_apns(amount, task_title), push_env)
    else:
        push_send_gcm(token, compensated_payload_gcm(amount, task_title), push_env)
    return True


def store_next_task_results_ts(user_id, timestamp_str):
    """stores the given ts for the given user for later retrieval"""
    try:
        # stored as string, can be None
        user_app_data = UserAppData.query.filter_by(user_id=user_id).first()
        user_app_data.next_task_ts = timestamp_str
        db.session.add(user_app_data)
        db.session.commit()
    except Exception as e:
        print(e)
        raise InvalidUsage('cant set task result ts')


def get_next_task_results_ts(user_id):
    """return the task_result_ts field for the given user"""
    try:
        user_app_data = UserAppData.query.filter_by(user_id=user_id).first()
        if user_app_data is None:
            return None
        return user_app_data.next_task_ts  # can be None
    except Exception as e:
        print(e)
        print('cant get task result ts')
        raise InvalidUsage('cant get task result ts')


def get_users_for_engagement_push(scheme):
    """get user_ids for an engagement scheme"""
    from datetime import datetime, timedelta
    from kinappserver.models import get_tasks_for_user
    now = arrow.utcnow().shift(seconds=60).timestamp  # add a small timeshift to account for calculation time
    user_ids = {OS_IOS: [], OS_ANDROID: []}

    if scheme not in ['engage-recent', 'engage-week']:
        print('invalid scheme:%s' % scheme)
        raise InvalidUsage('invalid scheme: %s' % scheme)

    if scheme == 'engage-recent':
        # get all user_ids that:
        # (1) have active tasks and 
        # (2) did not log in today and
        # (3) last login was sometimes in the last 4 days
        today = datetime.date(datetime.today())
        four_days_ago = datetime.date(datetime.today() + timedelta(days=-4))

        all_pushable_users = User.query.filter(User.push_token != None).filter(User.deactivated == False).all()
        for user in all_pushable_users:
            try:
                from .blacklisted_phone_numbers import is_userid_blacklisted
                if is_userid_blacklisted(user.user_id):
                    print('skipping user %s - blacklisted' % user.user_id)
                    continue

                if should_block_user_by_country_code(user.user_id):
                    print('skipping user %s - country not supported' % user.user_id)
                    continue

                # filter out users with no tasks AND ALSO users with future tasks:
                tasks = get_tasks_for_user(user.user_id)
                if tasks == []:
                    print('skipping user %s - no active task, now: %s' % (user.user_id, now))
                    continue

                next_task_ts = tasks[0]['start_date']
                if tasks[0]['start_date'] > now:
                    print('skipping user %s - next task is due at %s, now: %s' % (user.user_id, next_task_ts, now))
                    continue

                last_active = UserAppData.query.filter_by(user_id=user.user_id).first().update_at
                last_active_date = datetime.date(last_active)

                if today == last_active_date:
                    print('skipping user %s: was active today. now: %s' % (user.user_id, now))
                    continue
                if last_active_date < four_days_ago:
                    print('skipping user %s: last active more than 4 days ago. now: %s' % (user.user_id, now))
                    continue

                print('adding user %s with last_active: %s. now: %s' % (user.user_id, last_active_date, now))
                if user.os_type == OS_IOS:
                    user_ids[OS_IOS].append(user.user_id)
                else:
                    user_ids[OS_ANDROID].append(user.user_id)

            except Exception as e:
                print('caught exception trying to calculate push for user %s' % user.user_id)
                print(e)
                continue
        return user_ids

    elif scheme == 'engage-week':
        # get all tokens that:
        # (1) have active tasks and 
        # (2) logged in exactly a week ago
        # (3) last login was sometimes in the last 4 days
        seven_days_ago = datetime.date(datetime.today() + timedelta(days=-7))

        all_pushable_users = User.query.filter(User.push_token != None).filter(User.deactivated == False).all()
        for user in all_pushable_users:
            try:
                from .blacklisted_phone_numbers import is_userid_blacklisted
                if is_userid_blacklisted(user.user_id):
                    print('skipping user %s - blacklisted' % user.user_id)
                    continue

                if should_block_user_by_country_code(user.user_id):
                    print('skipping user %s - country not supported' % user.user_id)
                    continue

                tasks = get_tasks_for_user(user.user_id)
                if tasks == []:
                    print('skipping user %s - no active task, now: %s' % (user.user_id, now))
                    continue

                next_task_ts = tasks[0]['start_date']
                if tasks[0]['start_date'] > now:
                    print('skipping user %s - next task is due at %s, now: %s' % (user.user_id, next_task_ts, now))
                    continue

                last_active = UserAppData.query.filter_by(user_id=user.user_id).first().update_at
                last_active_date = datetime.date(last_active)

                if seven_days_ago != last_active_date:
                    print('skipping user %s: last active not seven days ago, now: %s' % (user.user_id, now))
                    continue
            
                print('adding user %s with last_active: %s. now: %s' % (user.user_id, last_active_date, now))
                if user.os_type == OS_IOS:
                    user_ids[OS_IOS].append(user.push_token)
                else:
                    user_ids[OS_ANDROID].append(user.push_token)

            except Exception as e:
                print('caught exception trying to calculate push for user %s' % user.user_id)
                print(e)
                continue
        return user_ids
    else:
        print('unknown scheme')
        return None


def get_userid_by_address(address):
    """return the userid associated with the given address or return None"""
    try:
        user = User.query.filter_by(public_address=address).first()
        if user is None:
            return None
        else:
            return user.user_id  # can be None
    except Exception as e:
        print('cant get user userid by address. Exception: %s' % e)
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
        print('cant get address by user_id. Exception: %s' % e)
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
                print('refusing to overwrite phone number for user_id %s' % user_id)
                raise InvalidUsage('trying to overwrite an existing phone number with a different one')
        else:
            user.enc_phone_number = encrypted_number
            db.session.add(user)
            db.session.commit()

        # does this number belong to another user? if so, de-activate the old user.
        deactivate_by_enc_phone_number(encrypted_number, user_id)

    except Exception as e:
        print('cant add phone number to user_id: %s. Exception: %s' % (user_id, e))
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
        print('cant get user address by phone. Exception: %s' % e)
        raise


def get_active_user_id_by_enc_phone(enc_phone_number):
    try:
        user = User.query.filter_by(enc_phone_number=enc_phone_number).filter_by(deactivated=False).first()
        if user is None:
            return None
        else:
            return user.user_id  # can be None
    except Exception as e:
        print('cant get active user_id by enc phone. Exception: %s' % e)
        raise


def get_user_ids_by_enc_phone(enc_phone_number):
    try:
        users = User.query.filter_by(enc_phone_number=enc_phone_number).all()
        return [user.user_id for user in users]
    except Exception as e:
        print('cant get user_ids by enc phone. Exception: %s' % e)
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
        print('cant get user phone by user_id. Exception: %s' % e)
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
        print('cant get user(s) address by phone. Exception: %s' % e)
        raise


def match_phone_number_to_address(phone_number, sender_user_id):
    """get the address associated with this phone number"""
    # get the sender's un-enc phone number by the userid:
    sender_enc_phone_number = get_enc_phone_number_by_user_id(sender_user_id)
    if not sender_enc_phone_number:
        # should never happen while phone v. is active
        print('should never happen: cant get user\'s phone number. user_id: %s' % sender_user_id)

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
            print('match_phone_number_to_address: applied special israeli-number logic to parse number: %s' % enc_phone_num_2)

    return parsed_address


def get_address_by_enc_phone_number(enc_phone_number):
    try:
        user = User.query.filter(User.enc_phone_number==enc_phone_number).filter_by(deactivated=False).first()
        if user is None:
            print('cant find user for encrypted phone number: %s' % enc_phone_number)
            return None
        else:
            return user.public_address  # can be None
    except Exception as e:
        print('cant get user address by phone. Exception: %s' % e)
        raise


def deactivate_by_enc_phone_number(enc_phone_number, new_user_id, activate_user=False):
    """deactivate any active user with the given phone number except the one with user_id

    this function deactivates the previous active user with the given phone number AND
    also duplicates his history into the new user.
    """
    new_user_id = str(new_user_id)

    if activate_user: # used in backup-restore
        print('activating user %s prior to deactivating all other user_ids' % new_user_id)
        db.engine.execute("update public.user set deactivated=false where user_id='%s'" % new_user_id)
    try:
        # find candidates to de-activate (except user_id)
        users = User.query.filter(User.enc_phone_number == enc_phone_number).filter(User.user_id != new_user_id).filter(User.deactivated == False).all()
        if users is []:
            return None  # nothing to do
        else:
            user_ids_to_deactivate = [user.user_id for user in users]
            print('deactivating user_ids: %s:' % user_ids_to_deactivate)
            # there should only ever be 1 at most, so log warning
            if len(user_ids_to_deactivate) > 1:
                print('warning: too many user_ids to deactivate were found: %s' % user_ids_to_deactivate)

            for user_id_to_deactivate in user_ids_to_deactivate:
                # deactivate and copy task_history
                db.engine.execute("update public.user set deactivated=true where enc_phone_number='%s' and user_id='%s'" % (enc_phone_number, user_id_to_deactivate))

                completed_tasks_query = "update user_app_data set completed_tasks = Q.col1, next_task_ts = Q.col2 from (select completed_tasks as col1, next_task_ts as col2 from user_app_data where user_id='%s') as Q where user_app_data.user_id = '%s'" % (user_id_to_deactivate, UUID(new_user_id))
                db.engine.execute(completed_tasks_query)

                # also delete the new user's history and plant the old user's history instead
                db.engine.execute("delete from public.user_task_results where user_id='%s'" % UUID(new_user_id))
                db.engine.execute("update public.user_task_results set user_id='%s' where user_id='%s'" % (UUID(new_user_id), user_id_to_deactivate))

    except Exception as e:
        print('cant deactivate_by_phone_number. Exception: %s' % e)
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


def nuke_user_data(phone_number, nuke_all = False):
    """nuke user's data by phone number. by default only nuke the active user"""
    # find the active user with this number:
    if nuke_all:
        print('nuking all users with the phone number: %s' % phone_number)
        user_ids = get_all_user_id_by_phone(phone_number)
    else:
        # only the active user
        print('nuking the active user with the phone number: %s' % phone_number)
        user_ids = [get_active_user_id_by_phone(phone_number)]
    for user_id in user_ids:
        db.engine.execute("delete from good where tx_hash in (select tx_hash from transaction where user_id='%s')" % (user_id))
        db.engine.execute("delete from public.transaction where user_id='%s'" % (user_id))
        db.engine.execute("delete from public.user_task_results where user_id='%s'" % (user_id))
        db.engine.execute('update public.user_app_data set completed_tasks=\'"[]"\' where user_id=\'%s\'' % (user_id))

    # also erase the backup hints for the phone
    db.engine.execute("delete from phone_backup_hints where enc_phone_number='%s'" % app.encryption.encrypt(phone_number))

    return user_ids if len(user_ids) > 0 else None


def get_user_config(user_id):
    """return the user-specific config based on the global config"""
    global_config = get_global_config()
    user_app_data = get_user_app_data(user_id)
    os_type = get_user_os_type(user_id)

    # customize the p2p tx flag
    if config.P2P_TRANSFERS_ENABLED:

        if not user_app_data:
            print('could not customize user config. disabling p2p txs for this user')
            global_config['p2p_enabled'] = False
        elif len(user_app_data.completed_tasks) < config.P2P_MIN_TASKS:
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

    if disable_phone_verification:
        print('disabling phone verification for userid %s' % user_id)
        global_config['phone_verification_enabled'] = False

    if disable_backup_nag:
        print('disabling backup nag for userid %s' % user_id)
        global_config['backup_nag'] = False


    print('user config for %s: %s' % (user_id, global_config))

    return global_config


def get_user_report(user_id):
    """return a json with all the interesting user-data"""
    print('getting user report for %s' % user_id)
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
        user_report['completed_tasks'] = user_app_data.completed_tasks
        user_report['next_task_ts'] = user_app_data.next_task_ts
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
        print('caught exception in get_user_report:%s' % e)
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
        print('restore_user_by_address: cant find enc_phone_number for current user_id %s. aborting' % current_user_id)
        return None
    try:
        from .backup import get_user_backup_hints_by_enc_phone
        hints = get_user_backup_hints_by_enc_phone(curr_enc_phone_number)
    except Exception as e:
        print('cant get hints for enc_phone_number %s. e:%s' % (curr_enc_phone_number, e))
        return None
    else:
        if hints == []:
            print('no hints found for enc_phone_number %s. aborting' % curr_enc_phone_number)
            return None
        # else - found hints, okay to continue with the restore

    # 2. find the original user_id from the given address
    original_user_id = get_userid_by_address(address)
    if not original_user_id:
        print('restore_user_by_address: cant find the original user_id for the given address. aborting')
        return None

    # ensure the user_id actually belongs to the same phone number as the current user_id
    original_enc_phone_number = get_enc_phone_number_by_user_id(original_user_id)
    if not original_enc_phone_number or (original_enc_phone_number != curr_enc_phone_number):
        print('restore_user_by_address: phone number mismatch. current=%s, original=%s' % (curr_enc_phone_number, original_enc_phone_number))
        return None

    # 3. activate the original user, deactivate the current one and
    # 4. copy the tasks from the current_user_id back onto the original user_id
    deactivate_by_enc_phone_number(curr_enc_phone_number, original_user_id, True)

    # copy the (potentially new device data and new push token to the old user)
    if not migrate_restored_user_data(current_user_id, original_user_id):
        print('restore_user_by_address: failed to migrate device-specific data from the temp user_id %s to the restored user-id %s' % (current_user_id, original_user_id))

    # 5. return the (now active) original user_id.
    print('restore_user_by_address: successfully restored the original user_id: %s' % original_user_id)
    return original_user_id


def fix_user_task_history(user_id):
    #TODO add try-catch
    """ find this user's phone number make sure this user_id has the most updated task history"""
    enc_phone_number = get_enc_phone_number_by_user_id(user_id)
    # find the user_id that has the most tasks and copy it
    prepared_stmt = '''select public.user_app_data.completed_tasks from public.user, public.user_app_data where public.user.user_id=public.user_app_data.user_id and public.user.enc_phone_number='%s' order by cast(user_app_data.completed_tasks as varchar) desc limit 1;'''
    results = db.engine.execute(prepared_stmt % (enc_phone_number))
    completed_tasks = results.fetchone()[0]
    print('planting completed_tasks into user_id %s: %s' % (user_id, completed_tasks))
    db.engine.execute("delete from public.user_task_results where user_id='%s';" % UUID(user_id))
    db.engine.execute('update public.user_app_data set completed_tasks=\'"%s"\' where user_id=\'%s\';' % (str(completed_tasks), UUID(user_id)))


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
        print('failed to migrate resteod used data. e=%s' % e)
        return False
    else:
        return True


def fix_user_completed_tasks(user_id):
    user_app_data = get_user_app_data(user_id)
    print('user tasks:%s' % user_app_data.completed_tasks)
    try:
        json.loads(user_app_data.completed_tasks)
    except Exception as e:
        print('detected bad completed tasks')
        #convert the bad tasks into good tasks:
        fixed_tasks = json.dumps(user_app_data.completed_tasks)
        print('the fix tasks: %s' % fixed_tasks)
        #write the tasks back to the db:
        user_app_data.completed_tasks = fixed_tasks
        db.session.add(user_app_data)
        db.session.commit()
    else:
        print('nothing to fix')
    return


def should_block_user_by_client_version(user_id):
    """determines whether this user_id should be blocked based on the client version"""
    from distutils.version import LooseVersion
    try:
        os_type = get_user_os_type(user_id)
        client_version = get_user_app_data(user_id).app_ver
    except Exception as e:
        print('should_block_user_by_client_version: cant get os_type/client version for user_id %s' % user_id)
        return False
    else:
        if os_type == OS_ANDROID:
            if LooseVersion(client_version) <= LooseVersion(config.BLOCK_ONBOARDING_ANDROID_VERSION):
                print('should block android version (%s), config: %s' % (client_version, config.BLOCK_ONBOARDING_ANDROID_VERSION))
                return True
        else: # OS_IOS
            if LooseVersion(client_version) <= LooseVersion(config.BLOCK_ONBOARDING_IOS_VERSION):
                print('should block ios version (%s), config: %s' % (client_version, config.BLOCK_ONBOARDING_IOS_VERSION))
                return True
    return False


def should_block_user_by_phone_prefix(user_id):
    """determines whether to block a user by her phone prefix"""
    try:
        phone_number = get_unenc_phone_number_by_user_id(user_id)
        for prefix in app.blocked_phone_prefixes:
            if phone_number.find(prefix) == 0:
                print('should_block_user_by_phone_prefix: should block user_id %s with phone number %s' % (user_id, phone_number))
                return True
    except Exception as e:
        print('should_block_user_by_phone_prefix for userid %s: caught exception: %s' % (user_id, e))
    return False


def should_allow_user_by_phone_prefix(user_id):
    """determines whether to allow a user based on her phone prefix"""
    try:
        phone_number = get_unenc_phone_number_by_user_id(user_id)
        if not phone_number:
            print('should_allow_user_by_phone_prefix - no phone number. allowing user')
            return True

        for prefix in app.allowed_phone_prefixes:
            if phone_number.find(prefix) == 0:
                return True
    except Exception as e:
        print('should_allow_user_by_phone_prefix for userid %s: caught exception: %s' % (user_id, e))

    print('should_allow_user_by_phone_prefix: not allowing user_id %s with phone number %s' % (user_id, phone_number))
    return False


def should_block_user_by_country_code(user_id):
    """determines whether to block users by their country code"""
    try:
        country_code = get_user_country_code(user_id)
        if country_code in app.blocked_country_codes:
            print('should_block_user_by_country_code: should block user_id %s with country_code %s' % (user_id, country_code))
            return True
    except Exception as e:
        print('should_block_user_by_country_code for userid %s: caught exception %s' % (user_id, e))
        return False


def delete_all_user_data(user_id, are_u_sure=False):
    """delete all user data from the db. this erases all the users associated with the same phone number"""
    print('preparing to delete all info related to user_id %s' % user_id)

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
        print('refusing to delete data for user with no phone number')
        return
    uids = get_user_ids_by_enc_phone(enc_phone)
    print('WARNING: will delete all data of the following %s user_ids: %s' % (len(uids), uids))
    if not are_u_sure:
        print('refusing to delete users. if youre sure, send with force flag')
        return

    for uid in uids:
        print('deleting all data related to user_id %s' % uid)
        print('deleting goods...')
        db.engine.execute(delete_user_goods % uid)
        print('deleting orders...')
        db.engine.execute(delete_user_orders % uid)
        print('deleting txs...')
        db.engine.execute(delete_user_transactions % uid)
        print('deleting p2p txs...')
        db.engine.execute(delete_p2p_txs_sent % uid)
        db.engine.execute(delete_p2p_txs_received % uid)
        print('deleting backup hints...')
        db.engine.execute(delete_phone_backup_hints % uid)
        print('deleting task results...')
        db.engine.execute(delete_task_results % uid)
        print('deleting auth tokens...')
        db.engine.execute(delete_auth_token % uid)
        print('deleting user data...')
        db.engine.execute(delete_app_data % uid)
        db.engine.execute(delete_user % uid)
        print('done with user_id: %s' % uid)


def count_registrations_for_phone_number(phone_number):
    """returns the number of registrations for the given unenc phone number"""
    enc_phone_number = app.encryption.encrypt(phone_number)
    count_users_with_enc_phone_number = '''select count(*) from public.user where enc_phone_number='%s';'''
    count = db.engine.execute(count_users_with_enc_phone_number % enc_phone_number).scalar()
    return count if count else 0


def count_missing_txs():
    """counts the number of users with missing txs in their data == users we owe money to"""

    missing_txs = []

    # get the list of tasks and their rewards:
    tasks_d = {}
    res = db.engine.execute('SELECT task_id, price from public.task')
    tasks = res.fetchall()
    for task in tasks:
        tasks_d[task[0]] = task[1]

    # get all the phone numbers in the system
    res2 = db.engine.execute('SELECT distinct enc_phone_number from public.user where enc_phone_number is not null')
    distinct_enc_phone_numbers = res2.fetchall()

    compensated_task_ids_query = '''select t2.tx_info->>'task_id' as task_id from public.user t1 inner join transaction t2 on t1.user_id=t2.user_id where t1.enc_phone_number='%s';'''
    completed_task_ids_query = '''select t2.task_id from public.user t1 inner join user_task_results t2 on t1.user_id=t2.user_id where t1.enc_phone_number='%s';'''

    # for each phone number, find
    for enc_number in distinct_enc_phone_numbers:
        try:
            if len(missing_txs) > 500:
                # stop here no need to go over more than 500.
                break

            sleep(0.1)  # lets not kill the db
            enc_number = enc_number[0]

            compensated_tasks = []
            res3 = db.engine.execute(compensated_task_ids_query % enc_number)  # safe
            res = res3.fetchall()
            for item in res:
                compensated_tasks.append(item[0])

            completed = []
            res4 = db.engine.execute(completed_task_ids_query % enc_number)  # safe
            res = res4.fetchall()
            for item in res:
                completed.append(item[0])

            uncompensated = list(set(completed) - set(compensated_tasks))
            if len(uncompensated) != 0:
                print('found uncompensated tasks: %s for number %s' % (uncompensated, enc_number))
                # get the active user id for that phone number
                res5 = db.engine.execute("SELECT user_id from public.user where enc_phone_number='%s' and deactivated=false" % enc_number)
                active_user_id = res5.fetchone()[0]
                for task_id in uncompensated:
                    reward = tasks_d[task_id]
                    missing_txs.append({'user_id': active_user_id, 'task_id': task_id, 'reward': reward})
        except Exception as e:
            print('exception while processing enc_phone_number: %s' % enc_number)

    print('missing txs: %s' % missing_txs)
    gauge_metric('missing-txs', len(missing_txs))


def re_register_all_users():
    """sends a push message to all users with a phone"""
    all_phoned_users = User.query.filter(User.enc_phone_number != None).filter(User.deactivated == False).all()
    print('sending register to %s users' % len(all_phoned_users))
    counter = 0
    for user in all_phoned_users:

        if user.os_type != OS_ANDROID:
            print('skipping user with ios client')
            continue
        user_app_data = get_user_app_data(user.user_id)
        from distutils.version import LooseVersion
        if user_app_data.app_ver is None or LooseVersion(user_app_data.app_ver) < LooseVersion('1.2.1'):
            print('skipping user with client ver %s' % user_app_data.app_ver)
            continue

        sleep(0.1)  # lets not choke the server
        send_push_register(user.user_id)
        counter = counter + 1


def automatically_raise_captcha_flag(user_id):
    """this function will raise ths given user_id's captcha flag if the time is right.

    note that this function will set the flag to 0, so the captcha will only be presented on the n+1 task
    """
    if not config.CAPTCHA_AUTO_RAISE:
        return

    os_type = get_user_os_type(user_id)
    if os_type == OS_IOS:
        #print('not raising captcha for ios device %s' % user_id)
        return

    # get the user's current task
    # and also the captcha status and history - all are in the user_app_data
    uad = get_user_app_data(user_id)
    if uad.should_solve_captcha_ternary != -1:
        #print('raise_captcha_if_needed: user %s captcha flag already at %s. doing nothing' % (user_id, uad.should_solve_captcha_ternary))
        return

    max_task = find_max_task(json.loads(uad.completed_tasks))
    if max_task % config.CAPTCHA_TASK_MODULO == 0:
        # ensure the last captcha wasnt solved today
        now = arrow.utcnow()
        recent_captcha = 0 if uad.captcha_history is None else max([item['date'] for item in uad.captcha_history])
        print(recent_captcha)
        last_captcha_secs_ago = (now - arrow.get(recent_captcha)).total_seconds()
        if last_captcha_secs_ago > config.CAPTCHA_SAFETY_COOLDOWN_SECS:
            # more than a day ago, so raise:
            print('raise_captcha_if_needed:  user %s, current task_id = %s, last captcha was %s secs ago, so raising flag' % (user_id, max_task, last_captcha_secs_ago))
            set_should_solve_captcha(user_id)
        #else:
        #    print('raise_captcha_if_needed: user %s, current task_id = %s, last captcha was %s secs ago, so not raising flag' % (user_id, max_task, last_captcha_secs_ago))

