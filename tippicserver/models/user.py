"""The User model"""
from sqlalchemy_utils import UUIDType
from sqlalchemy.dialects.postgresql import INET
import logging as log

from tippicserver import db, config, app
from tippicserver.utils import InvalidUsage, OS_IOS, OS_ANDROID, parse_phone_number, increment_metric, gauge_metric, get_global_config, generate_memo, OS_ANDROID, OS_IOS, commit_json_changed_to_orm
from uuid import uuid4, UUID
from .push_auth_token import get_token_obj_by_user_id, should_send_auth_token, set_send_date
import arrow
import json
from distutils.version import LooseVersion
from .backup import get_user_backup_hints_by_enc_phone
from time import sleep

DEFAULT_TIME_ZONE = -4
TIPPIC_IOS_PACKAGE_ID_PROD = 'org.kinecosystem.tippic'  # AKA bundle id
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

    def __repr__(self):
        return '<sid: %s, user_id: %s, os_type: %s, device_model: %s, push_token: %s, time_zone: %s, device_id: %s,' \
               ' onboarded: %s, public_address: %s, enc_phone_number: %s, package_id: %s, deactivated: %s'\
               % (self.sid, self.user_id, self.os_type, self.device_model, self.push_token, self.time_zone,
                  self.device_id, self.onboarded, self.public_address, self.enc_phone_number, self.package_id,
                  self.deactivated)


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
    # TODO cache the results?
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


def create_user(user_id, os_type, device_model, push_token, time_zone, device_id, app_ver, package_id):
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
    user.package_id = package_id
    db.session.add(user)
    db.session.commit()

    if is_new_user:
        user_app_data = UserAppData()
        user_app_data.user_id = user_id
        user_app_data.app_ver = app_ver
        db.session.add(user_app_data)
        db.session.commit()

        # get/create an auth token for this user
        get_token_obj_by_user_id(user_id)
    else:
        increment_metric('reregister')

    return is_new_user


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
    ip_address = db.Column(INET) # the user's last known ip
    country_iso_code = db.Column(db.String(10))  # country iso code based on last ip
    captcha_history = db.Column(db.JSON)
    should_solve_captcha_ternary = db.Column(db.Integer, unique=False, default=0, nullable=False)  # -1 = no captcha, 0 = show captcha on next task, 1 = captcha required



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


def list_all_users_app_data():
    """returns a dict of all the user-app-data"""
    response = {}
    users = UserAppData.query.order_by(UserAppData.user_id).all()
    for user in users:
        response[user.user_id] = {'user_id': user.user_id,  'app_ver': user.app_ver, 'update': user.update_at}
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
    if package_id == TIPPIC_IOS_PACKAGE_ID_PROD:
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

#
# def store_next_task_results_ts(user_id, task_id, timestamp_str, cat_id=None):
#     """stores the given ts for the given user and task_id for later retrieval
#
#     if cat_id is given, ignore the task_id.
#     """
#     try:
#         if cat_id is None:
#             from .task2 import get_cat_id_for_task_id
#             cat_id = get_cat_id_for_task_id(task_id)
#
#         # stored as string, can be None
#         user_app_data = UserAppData.query.filter_by(user_id=user_id).first()
#         user_app_data.next_task_ts_dict[cat_id] = timestamp_str
#         db.session.add(user_app_data)
#
#         commit_json_changed_to_orm(user_app_data, ['next_task_ts_dict'])
#     except Exception as e:
#         raise InvalidUsage('cant set task result ts. e:%s' % e)

#
# def get_next_task_results_ts(user_id, cat_id):
#     """return the task_result_ts field for the given user and task category"""
#     try:
#         user_app_data = UserAppData.query.filter_by(user_id=user_id).first()
#         if user_app_data is None:
#             return None
#         return user_app_data.next_task_ts_dict.get(cat_id, 0)  # can be None
#     except Exception as e:
#         log.error('cant get task result ts. e: %s' % e)
#         raise InvalidUsage('cant get task result ts')


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

    # also erase the backup hints for the phone
    db.engine.execute("delete from phone_backup_hints where enc_phone_number='%s'" % app.encryption.encrypt(phone_number))

    return user_ids if len(user_ids) > 0 else None


def get_user_config(user_id):
    """return the user-specific config based on the global config"""
    global_config = get_global_config()
    user_app_data = get_user_app_data(user_id)
    os_type = get_user_os_type(user_id)

    # turn off phone verification for older clients:
    disable_phone_verification = False
    disable_backup_nag = True
    if os_type == OS_ANDROID and LooseVersion(user_app_data.app_ver) <= LooseVersion(config.BLOCK_ONBOARDING_ANDROID_VERSION):
        disable_phone_verification = True
    elif os_type == OS_IOS and LooseVersion(user_app_data.app_ver) <= LooseVersion(config.BLOCK_ONBOARDING_IOS_VERSION):
        disable_phone_verification = True

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
        user_report['last_app_launch'] = user_app_data.update_at
        user_report['ip_addr'] = user_app_data.ip_address
        user_report['country_iso_code'] = user_app_data.country_iso_code
        user_report['auth_token'] = {}
        user_report['auth_token']['sent_date'] = str(push_token_entry.send_date)
        user_report['auth_token']['ack_date'] = str(push_token_entry.ack_date)
        user_report['auth_token']['authenticated'] = str(push_token_entry.authenticated)
        user_report['auth_token']['token'] = str(push_token_entry.auth_token)
        user_report['package_id'] = str(user.package_id)
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

    delete_user_transactions = '''delete from transaction where user_id='%s';'''
    delete_p2p_txs_sent = '''delete from p2_p_transaction where sender_user_id='%s';'''
    delete_p2p_txs_received = '''delete from p2_p_transaction where receiver_user_id='%s';'''
    delete_phone_backup_hints = '''delete from phone_backup_hints where enc_phone_number in (select enc_phone_number from public.user where user_id='%s');'''
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
        log.info('deleting txs...')
        db.engine.execute(delete_user_transactions % uid)
        log.info('deleting p2p txs...')
        db.engine.execute(delete_p2p_txs_sent % uid)
        db.engine.execute(delete_p2p_txs_received % uid)
        log.info('deleting backup hints...')
        db.engine.execute(delete_phone_backup_hints % uid)
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

