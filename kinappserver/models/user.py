"""The User model"""
from sqlalchemy_utils import UUIDType

from kinappserver import db, config
from kinappserver.utils import InvalidUsage, OS_IOS, OS_ANDROID, parse_phone_number, increment_metric, get_global_config, generate_memo
from kinappserver.push import push_send_gcm, push_send_apns, engagement_payload_apns, engagement_payload_gcm, compensated_payload_apns, compensated_payload_gcm, send_please_upgrade_push_2
from uuid import uuid4, UUID
from .push_auth_token import get_token_obj_by_user_id, should_send_auth_token, set_send_date

DEFAULT_TIME_ZONE = -4
KINIT_IOS_PACKAGE_ID_PROD = 'org.kinecosystem.kinit'  # AKA bundle id


class User(db.Model):
    """
    the user model
    """
    sid = db.Column(db.Integer(), db.Sequence('sid', start=1, increment=1), primary_key=False)
    user_id = db.Column(UUIDType(binary=False), primary_key=True, nullable=False)
    os_type = db.Column(db.String(10), primary_key=False, nullable=False)
    device_model = db.Column(db.String(40), primary_key=False, nullable=False)
    push_token = db.Column(db.String(200), primary_key=False, nullable=True)
    time_zone = db.Column(db.Integer(), primary_key=False, nullable=False)
    device_id = db.Column(db.String(40), primary_key=False, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now())
    onboarded = db.Column(db.Boolean, unique=False, default=False)
    public_address = db.Column(db.String(60), primary_key=False, unique=True, nullable=True)
    phone_number = db.Column(db.String(60), primary_key=False, nullable=True)
    deactivated = db.Column(db.Boolean, unique=False, default=False)
    auth_token = db.Column(UUIDType(binary=False), primary_key=False, nullable=True)
    package_id = db.Column(db.String(60), primary_key=False, nullable=True)
    screen_w = db.Column(db.String(20), primary_key=False, nullable=True)
    screen_h = db.Column(db.String(20), primary_key=False, nullable=True)
    screen_d = db.Column(db.String(20), primary_key=False, nullable=True)
    user_agent = db.Column(db.String(200), primary_key=False, nullable=True)  # optional, and filled via get_truex_activity

    def __repr__(self):
        return '<sid: %s, user_id: %s, os_type: %s, device_model: %s, push_token: %s, time_zone: %s, device_id: %s,' \
               ' onboarded: %s, public_address: %s, phone_number: %s, package_id: %s, screen_w: %s, screen_h: %s,' \
               ' screen_d: %s, user_agent: %s, deactivated: %s>' % (self.sid, self.user_id, self.os_type, self.device_model, self.push_token, self.time_zone,
                                                                                           self.device_id, self.onboarded, self.public_address, self.phone_number, self.package_id,
                                                                                self.screen_w, self.screen_h, self.screen_d, self.user_agent, self.deactivated)


def get_user(user_id):
    user = User.query.filter_by(user_id=user_id).first()
    if not user:
        raise InvalidUsage('no such user_id')
    return user


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
    user.device_model = device_model
    user.push_token = push_token
    user.time_zone = parse_timezone(time_zone)
    user.device_id = device_id
    user.auth_token = uuid4()
    user.screen_h = screen_h
    user.screen_w = screen_w
    user.screen_d = screen_d
    user.package_id = package_id
    db.session.add(user)
    db.session.commit()

    if is_new_user:
        user_app_data = UserAppData()
        user_app_data.user_id = user_id
        user_app_data.completed_tasks = '[]'
        user_app_data.app_ver = app_ver
        user_app_data.next_task_ts = None
        user_app_data.next_task_memo = generate_memo()
        db.session.add(user_app_data)
        db.session.commit()

        # get/create an auth token for this user
        get_token_obj_by_user_id(user_id)

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
                                       'phone_num': user.phone_number, 'auth_token': user.auth_token, 'deactivated': user.deactivated}
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
    user = User.query.filter_by(user_id=user_id).first()
    if not user:
        return None, None
    else:
        push_env = package_id_to_push_env(user.package_id)
        return user.os_type, user.push_token, push_env


def send_push_tx_completed(user_id, tx_hash, amount, task_id):
    """send a message indicating that the tx has been successfully completed"""
    os_type, token, push_env = get_user_push_data(user_id)
    if token is None:
        print('cant push to user %s: no push token' % user_id)
        return False
    if os_type == OS_IOS:
        print('sending tx_completed for ios is not supported yet - or needed')
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
    import arrow
    from kinappserver.models import get_tasks_for_user
    now = arrow.utcnow().shift(seconds=60).timestamp  # add a small timeshift to account for calculation time
    user_ids = {OS_IOS: [], OS_ANDROID: []}

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
        # allow (and ignore) re-submissions of the SAME number, but reject new numbers
        if user.phone_number is not None:
            if user.phone_number == number:
                return  # all good, do nothing
            else:
                raise InvalidUsage('trying to overwrite an existing phone number with a different one')
        else:
            user.phone_number = number
            db.session.add(user)
            db.session.commit()

        # does this number belong to another user? if so, de-activate the old user.

        deactivate_by_phone_number(number, user_id)

    except Exception as e:
        print('cant add phone number to user_id: %s. Exception: %s' % (user_id, e))
        raise


def get_active_user_id_by_phone(phone_number):
    try:
        user = User.query.filter_by(phone_number=phone_number).filter_by(deactivated=False).first()
        if user is None:
            return None
        else:
            return user.user_id  # can be None
    except Exception as e:
        print('cant get user address by phone. Exception: %s' % e)
        raise


def get_phone_number_by_user_id(user_id):
    try:
        user = User.query.filter_by(user_id=user_id).filter_by(deactivated=False).first()
        if user is None:
            return None
        else:
            return user.phone_number  # can be None
    except Exception as e:
        print('cant get user phone by user_id. Exception: %s' % e)
        raise


def is_user_phone_verified(user_id):
    """return true iff the user passed phone-verification"""
    return get_phone_number_by_user_id(user_id) is not None


def get_all_user_id_by_phone(phone_number):
    try:
        users = User.query.filter_by(phone_number=phone_number).all()
        return [user.user_id for user in users]
    except Exception as e:
        print('cant get user(s) address by phone. Exception: %s' % e)
        raise


def match_phone_number_to_address(phone_number, sender_user_id):
    """get the address associated with this phone number"""
    # get the sender's phone number:
    sender_phone_number = get_phone_number_by_user_id(sender_user_id)
    if not sender_phone_number:
        # should never happen while phone v. is active
        print('should never happen: cant get user\'s phone number. user_id: %s' % sender_user_id)
    parsed_address = get_address_by_phone_number(parse_phone_number(phone_number, sender_phone_number))

    if parsed_address is None:
        # special handling for Israeli numbers: perhaps the number was stored in the db with a leading zero.
        # in the db: +9720527702891
        # from the client: 0527702891
        massaged_number = '+972' + phone_number
        parsed_address = get_address_by_phone_number(massaged_number)
        if parsed_address:
            print('match_phone_number_to_address: applied special israeli-number logic to parse number: %s' % massaged_number)

    return parsed_address


def get_address_by_phone_number(phone_number):
    try:
        user = User.query.filter(User.phone_number==phone_number).filter_by(deactivated=False).first()
        if user is None:
            print('cant find user for phone number: %s' % phone_number)
            return None
        else:
            return user.public_address  # can be None
    except Exception as e:
        print('cant get user address by phone. Exception: %s' % e)
        raise


### not in use ###
def get_address_by_phone_numbers(phone_numbers):
    """"attempt to find a public address by a list of phone numbers

    return None if no phone number exists or if the address wasn't set
    if more than one matches, just get one
    """
    try:
        user = User.query.filter(User.phone_number.in_(phone_numbers)).filter_by(deactivated=False).first()
        if user is None:
            return None
        else:
            return user.public_address  # can be None
    except Exception as e:
        print('cant get user address by phone. Exception: %s' % e)
        raise



def deactivate_by_phone_number(phone_number, user_id):
    """deactivate any active user with the given phone number except the one with user_id

    this function deactivates the previous active user with the given phone number AND
    also duplicates his history into the new user.
    """
    try:
        # find candidates to de-activate (except user_id)
        users = User.query.filter(User.phone_number == phone_number).filter(User.user_id != user_id).filter(User.deactivated == False).all()
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

                #connection = db.session.connection()
                #try:
                #    rescount = connection.execute("select resource_id,count(resource_id) as total FROM resourcestats")
                #    # do something
                #finally:
                #    connection.close()

                db.engine.execute("update public.user set deactivated=true where phone_number='%s' and user_id='%s'" % (phone_number, user_id_to_deactivate))
                db.engine.execute("update user_app_data set completed_tasks = Q.col1, next_task_ts = Q.col2 from (select completed_tasks as col1, next_task_ts as col2 from user_app_data where user_id='%s') as Q where user_app_data.user_id = '%s'" % (user_id_to_deactivate, UUID(user_id)))


                #db.engine.execute("update public.user set deactivated=true where phone_number='%s' and user_id='%s'; update user_app_data set completed_tasks = Q.col1, next_task_ts = Q.col2 from (select completed_tasks as col1, next_task_ts as col2 from user_app_data where user_id='%s') as Q where user_app_data.user_id = '%s'" % (phone_number, user_id_to_deactivate, user_id_to_deactivate, UUID(user_id)))



                # also delete the new user's history and plant the old user's history instead
                db.engine.execute("delete from public.user_task_results where user_id='%s'" % UUID(user_id))
                db.engine.execute("update public.user_task_results set user_id='%s' where user_id='%s'" % (UUID(user_id), user_id_to_deactivate))

    except Exception as e:
        print('cant deactivate_by_phone_number. Exception: %s' % e)
        raise


def get_pa_for_users():
    """For all the users that dont have pa, try to get it from a past transaction"""
    users = User.query.filter(User.public_address==None).all()
    for user in users:
        from .transaction import get_pa_from_transactions
        pa = get_pa_from_transactions(user.user_id)
        if pa:
            print('about to set address %s to userid: %s' % (pa, user.user_id))
            db.engine.execute("update public.user set public_address='%s' where user_id='%s'" % (pa, user.user_id))


def get_associated_user_ids(user_id):
    """get a list of all the user_ids associated with the given user_id through phone-identification.
    the list also includes the original user_id.
    """
    user = get_user(user_id)
    if user.phone_number is None:
        return [user_id]
    else:
        users = User.query.filter(User.phone_number == user.phone_number).all()
        return [str(user.user_id) for user in users]


def find_missing_txs():
    users = User.query.all()
    missing_txs = []
    num_missing_txs_by_user = {}
    for user in users:
        missing_txs_count = 0
        #print('checking user %s: ' % user.user_id)

        user_app_data = get_user_app_data(user.user_id)
        completed_tasks = user_app_data.completed_tasks

        # get the task results
        from .task import get_user_task_results
        user_task_results_ids_dict = {result.task_id: result.update_at for result in get_user_task_results(user.user_id)}
        #import json
        #for task_id in json.loads(completed_tasks):
        #    if task_id not in user_task_results_ids_dict.keys():
        #        print('cant find task results for task id (%s) for userid (%s)' % (task_id, user.user_id))
        #        pass
        #    else:
        #        #  print('found task results for task_id %s for user_id (%s)' % (task_id, user.user_id))
        #        pass

        from .transaction import list_user_transactions
        user_txs = list_user_transactions(user.user_id)
        tx_task_ids = []
        for tx in user_txs:
            if not tx.incoming_tx:
                tx_task_ids.append(tx.tx_info['task_id'])

        # see if there any task results for which we have no txs
        for task_id in user_task_results_ids_dict.keys():
            if task_id not in tx_task_ids:
                from .task import get_reward_for_task
                reward = get_reward_for_task(task_id)
                #print('cant find tx for task_id %s for user_id %s' % (task_id, user.user_id))
                missing_txs.append((user.user_id, task_id, reward, user_task_results_ids_dict[task_id]))
                missing_txs_count = missing_txs_count + 1
            else:
                #  print('found tx for task id (%s) for user_id (%s)' % (task_id, user.user_id))
                pass
        if missing_txs_count > 0:
            num_missing_txs_by_user[str(user.user_id)] = missing_txs_count
    return missing_txs


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
    return user_ids if len(user_ids)>0 else None


def get_user_config(user_id):
    """return the user-specific config based on the global config"""
    global_config = get_global_config()

    # customize the p2p tx flag
    if config.P2P_TRANSFERS_ENABLED:
        user_app_data = get_user_app_data(user_id)
        if not user_app_data:
            print('could not customize user config. disabling p2p txs for this user')
            global_config['p2p_enabled'] = False
        elif len(user_app_data.completed_tasks) < config.P2P_MIN_TASKS:
            global_config['p2p_enabled'] = False

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
        user_report['phone_number'] = user.phone_number
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
        user_report['auth_token'] = {}
        user_report['auth_token']['sent_date'] = str(push_token_entry.send_date)
        user_report['auth_token']['ack_data'] = str(push_token_entry.ack_date)
        user_report['auth_token']['authenticated'] = str(push_token_entry.authenticated)
        user_report['package_id'] = str(user.package_id)
        user_report['screen_w'] = user.screen_w
        user_report['screen_h'] = user.screen_h
        user_report['screen_d'] = user.screen_d
        user_report['user_agent'] = user.user_agent
    except Exception as e:
        print('caught exception in get_user_report:%s' % e)
    return user_report
