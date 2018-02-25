'''The User model'''
from sqlalchemy_utils import UUIDType
import json

from kinappserver import db
from kinappserver.utils import InvalidUsage, send_apns, send_gcm


class User(db.Model):
    '''
    the user model
    '''
    sid = db.Column(db.Integer(), db.Sequence('sid', start=1, increment=1), primary_key=False)
    user_id = db.Column(UUIDType(binary=False), primary_key=True, nullable=False)
    os_type = db.Column(db.String(10), primary_key=False, nullable=False)
    device_model = db.Column(db.String(40), primary_key=False, nullable=False)
    push_token = db.Column(db.String(200), primary_key=False, nullable=True)
    time_zone = db.Column(db.String(10), primary_key=False, nullable=False)
    device_id = db.Column(db.String(40), primary_key=False, nullable=True)
    created_at = db.Column(db.DateTime(timezone=False), server_default=db.func.now())
    onboarded = db.Column(db.Boolean, unique=False, default=False)

    def __repr__(self):
        return '<sid: %s, user_id: %s, os_type: %s, device_model: %s, push_token: %s, time_zone: %s, device_id: %s, onboarded: %s>' % (self.sid, self.user_id, self.os_type, self.device_model, self.push_token, self.time_zone, self.device_id, self.onboarded)


def get_user(user_id):
    user = User.query.filter_by(user_id=user_id).first()
    if not user:
        raise InvalidUsage('no such user_id')
    return user


def user_exists(user_id):
    user = User.query.filter_by(user_id=user_id).first()
    return True if user else False


def is_onboarded(user_id):
    '''returns wheather the user has an account or None if there's no such user.'''
    try:
        return User.query.filter_by(user_id=user_id).first().onboarded
    except Exception as e:
        return None


def set_onboarded(user_id, onboarded):
    '''set the onbarded field of the user in the db'''
    user = get_user(user_id)
    user.onboarded = onboarded
    db.session.add(user)
    db.session.commit()


def create_user(user_id, os_type, device_model, push_token, time_zone, device_id, app_ver):
    '''create a new user and commit to the database. should only fail if the user_id is duplicate'''
    if user_exists(user_id):
            raise InvalidUsage('refusing to create user. user_id %s already exists' % user_id)
    user = User()
    user.user_id = user_id
    user.os_type = os_type
    user.device_model = device_model
    user.push_token = push_token
    user.time_zone = time_zone
    user.device_id = device_id
    db.session.add(user)
    db.session.commit()

    user_app_data = UserAppData()
    user_app_data.user_id = user_id
    user_app_data.completed_tasks = '[]'
    user_app_data.app_ver = app_ver
    db.session.add(user_app_data)
    db.session.commit()


def update_user_token(user_id, push_token):
    '''updates the user's token with a new one'''
    user = get_user(user_id)
    user.push_token = push_token
    db.session.add(user)
    db.session.commit()


def list_all_users():
    '''returns a dict of all the whitelisted users and their PAs (if available)'''
    response = {}
    users = User.query.order_by(User.user_id).all()
    for user in users:
        response[str(user.user_id)] = {'sid': user.sid, 'os': user.os_type, 'push_token': user.push_token, 'time_zone': user.time_zone, 'device_id': user.device_id, 'device_model': user.device_model, 'onboarded': user.onboarded}
    return response


class UserAppData(db.Model):
    '''
    the user app data model tracks the version of the app installed @ the client
    '''
    user_id = db.Column('user_id', UUIDType(binary=False), db.ForeignKey("user.user_id"), primary_key=True, nullable=False)
    app_ver = db.Column(db.String(40), primary_key=False, nullable=False)
    update_at = db.Column(db.DateTime(timezone=False), server_default=db.func.now(), onupdate=db.func.now())
    completed_tasks = db.Column(db.JSON)


def update_user_app_version(user_id, app_ver):
    '''update the user app version'''
    try:
        userAppData = UserAppData.query.filter_by(user_id=user_id).first()
        userAppData.app_ver = app_ver
        db.session.add(userAppData)
        db.session.commit()
    except Exception as e:
        print(e)
        raise InvalidUsage('cant set user app data')


def list_all_users_app_data():
    '''returns a dict of all the user-app-data'''
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


def get_task_ids_for_user(user_id):
    '''get the list of current task_ids for this user.
       the current policy is to hand the user the n+1 task, 
       which happens to be the len(completed tasks):
       len(0) == 1
       len(0,1) == 2
       len(0,1,2) == 3 etc
    '''
    user_app_data = get_user_app_data(user_id)
    if len(user_app_data.completed_tasks) == 0:
        return ['0']
    else:
        return [str(len(json.loads(user_app_data.completed_tasks)))]


def get_user_push_data(user_id):
    '''returns the os_type and the token for the given user_id'''
    user = User.query.filter_by(user_id=user_id).first()
    if not user:
        return None, None
    else:
        return user.os_type, user.push_token


def send_push_tx_completed(user_id, tx_hash, amount, task_id):
    '''send a message indicating that the tx has been successfully completed'''
    os_type, token = get_user_push_data(user_id)
    if token is None:
        print('cant push to user %s: no push token' % user_id)
        return False
    if os_type == 'iOS': #TODO move to consts
        payload = {} #TODO finalize this
        send_apns(token, payload)
    else:
        payload = {'type': 'tx_completed', 'user_id': user_id, 'tx_hash': tx_hash, 'kin': amount, 'task_id': task_id}
        send_gcm(token, payload)
    return True
