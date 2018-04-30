"""The User model"""
from sqlalchemy_utils import UUIDType

from kinappserver import db
from kinappserver.utils import InvalidUsage, OS_IOS, OS_ANDROID
from kinappserver.push import send_gcm, send_apns, engagement_payload_apns, engagement_payload_gcm
from uuid import uuid4

DEFAULT_TIME_ZONE = -4


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

    def __repr__(self):
        return '<sid: %s, user_id: %s, os_type: %s, device_model: %s, push_token: %s, time_zone: %s, device_id: %s,' \
               ' onboarded: %s, public_address: %s, phone_number: %s, deactivated: %s>' % (self.sid, self.user_id, self.os_type, self.device_model, self.push_token, self.time_zone,
                                                                                           self.device_id, self.onboarded, self.public_address, self.phone_number, self.deactivated)


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


def create_user(user_id, os_type, device_model, push_token, time_zone, device_id, app_ver):
    """create a new user and commit to the database. should only fail if the user_id is duplicate"""

    def parse_timezone(tz):
        """convert -02:00 to -2 or set reasonable default"""
        try:
            return int(tz[:(tz.find(':'))])
        except Exception as e:
            print('failed to parse timezone: %s. using default' % tz)
            print(e)
            return int(DEFAULT_TIME_ZONE)

    if user_exists(user_id):
            raise InvalidUsage('refusing to create user. user_id %s already exists' % user_id)
    user = User()
    user.user_id = user_id
    user.os_type = os_type
    user.device_model = device_model
    user.push_token = push_token
    user.time_zone = parse_timezone(time_zone)
    user.device_id = device_id
    user.auth_token = uuid4()
    db.session.add(user)
    db.session.commit()

    user_app_data = UserAppData()
    user_app_data.user_id = user_id
    user_app_data.completed_tasks = '[]'
    user_app_data.app_ver = app_ver
    user_app_data.next_task_ts = None
    db.session.add(user_app_data)
    db.session.commit()


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


def get_user_push_data(user_id):
    """returns the os_type and the token for the given user_id"""
    user = User.query.filter_by(user_id=user_id).first()
    if not user:
        return None, None
    else:
        return user.os_type, user.push_token


def send_push_tx_completed(user_id, tx_hash, amount, task_id):
    """send a message indicating that the tx has been successfully completed"""
    os_type, token = get_user_push_data(user_id)
    if token is None:
        print('cant push to user %s: no push token' % user_id)
        return False
    if os_type == OS_IOS:
        print('sending tx_completed for ios is not supported yet - or needed')
    else:
        from kinappserver.push import gcm_payload, generate_push_id
        payload = gcm_payload('tx_completed', generate_push_id(), {'type': 'tx_completed', 'user_id': user_id, 'tx_hash': tx_hash, 'kin': amount, 'task_id': task_id})
        send_gcm(token, payload)
    return True


def send_engagement_push(user_id, push_type, token=None, os_type=None):
    """sends an engagement push message to the user with the given user_id"""
    if None in (token, os_type):
        os_type, token = get_user_push_data(user_id)

    if token is None:
        print('cant push to user %s: no push token' % user_id)
        return False

    if os_type == OS_IOS:
        send_apns(token, engagement_payload_apns(push_type))
    else:
        send_gcm(token, engagement_payload_gcm(push_type))
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


def get_tokens_for_push(scheme):
    """get push tokens for a scheme"""
    from datetime import datetime, timedelta
    from kinappserver.models import get_tasks_for_user
    tokens = {OS_IOS: [], OS_ANDROID: []}

    if scheme == 'engage-recent':
        # get all tokens that:
        # (1) have active tasks and 
        # (2) did not log in today and
        # (3) last login was sometimes in the last 4 days
        today = datetime.date(datetime.today())
        four_days_ago = datetime.date(datetime.today() + timedelta(days=-4))

        all_pushable_users = User.query.filter(User.push_token != None).all()
        for user in all_pushable_users:
            try:

                if get_tasks_for_user(user.user_id) == []:
                    print('skipping user %s - no active task' % user.user_id)
                    continue

                last_active = UserAppData.query.filter_by(user_id=user.user_id).first().update_at
                last_active_date = datetime.date(last_active)

                if today == last_active_date:
                    print('skipping user %s: was active today' % user.user_id)
                    continue
                if last_active_date < four_days_ago:
                    print('skipping user %s: last active more than 4 days ago' % user.user_id)
                    continue

                print('adding user %s with last_active: %s' % (user.user_id, last_active_date))
                if user.os_type == OS_IOS:
                    tokens[OS_IOS].append(user.push_token)
                else:
                    tokens[OS_ANDROID].append(user.push_token)

            except Exception as e:
                print('caught exception trying to calculate push for user %s' % user.user_id)
                print(e)
                continue
        return tokens

    elif scheme == 'engage-week':
        # get all tokens that:
        # (1) have active tasks and 
        # (2) logged in exactly a week ago
        # (3) last login was sometimes in the last 4 days
        seven_days_ago = datetime.date(datetime.today() + timedelta(days=-7))

        all_pushable_users = User.query.filter(User.push_token != None).all()
        for user in all_pushable_users:
            try:

                if get_tasks_for_user(user.user_id) == []:
                    print('skipping user %s - no active task' % user.user_id)
                    continue

                last_active = UserAppData.query.filter_by(user_id=user.user_id).first().update_at
                last_active_date = datetime.date(last_active)

                if seven_days_ago != last_active_date:
                    print('skipping user %s: last active not seven days ago' % user.user_id)
                    continue
            
                print('adding user %s with last_active: %s' % (user.user_id, last_active_date))
                if user.os_type == OS_IOS:
                    tokens[OS_IOS].append(user.push_token)
                else:
                    tokens[OS_ANDROID].append(user.push_token)

            except Exception as e:
                print('caught exception trying to calculate push for user %s' % user.user_id)
                print(e)
                continue
        return tokens
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
    raise InvalidUsage('cant get user_id by address')


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
        raise InvalidUsage('cant get user address by user_id')


def set_user_phone_number(user_id, number):
    """sets a phone number to the user's entry"""
    try:
        user = get_user(user_id)
        # allow (and ignore) re-submissions of the SAME number, but reject new numbers
        if user.phone_number is not None:

            # does this number belong to another user? if so, de-activate the old user.
            deactivate_by_phone_number(number)

            if user.phone_number == number:
                return
            else:
                raise InvalidUsage('trying to overwrite an existing phone number')
        user.phone_number = number
        db.session.add(user)
        db.session.commit()
    except Exception as e:
        print('cant add phone number to user_id: %s. Exception: %s' % (user_id, e))


def get_address_by_phone(phone_number):
    """"attempt to find a public address by phone number

    return None if no phone number exists or if the address wasn't set
    """
    try:
        user = User.query.filter_by(phone_number=phone_number).first()
        if user is None:
            return None
        else:
            return user.public_address  # can be None
    except Exception as e:
        print('cant get user address by phone. Exception: %s' % e)
    raise InvalidUsage('cant get address by phone')


def deactivate_by_phone_number(user_id, phone_number):
    """deactivate any user except user_id with this phone_number"""
    results = db.engine.execute("update public.user set deactivate=true where phone_number=%s and user_id!=%s" % (phone_number, user_id))
    print('deactivated %s users with phone_number:%s' % (len(results), phone_number))
