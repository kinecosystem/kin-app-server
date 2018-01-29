'''The model for the Kin App Server.'''
from uuid import uuid4
import datetime
import redis_lock
from sqlalchemy_utils import UUIDType

from kinappserver import db, config, app
from kinappserver.utils import InvalidUsage

class User(db.Model):
    '''
    the user model
    '''
    sid = db.Column(db.Integer(), db.Sequence('sid', start=1, increment=1), primary_key=False)
    user_id = db.Column(UUIDType(binary=False), primary_key=True, nullable=False)
    os_type = db.Column(db.String(10), primary_key=False, nullable=False)
    device_model = db.Column(db.String(40), primary_key=False, nullable=False)
    push_token = db.Column(db.String(80), primary_key=False, nullable=True)
    time_zone = db.Column(db.String(10), primary_key=False, nullable=False)
    device_id = db.Column(db.String(40), primary_key=False, nullable=False)


    def __repr__(self):
        return '<sid: %s, user_id: %s, os_type: %s, device_model: %s, push_token: %s, time_zone: %s, device_id: %s>' % (self.sid, self.user_id, self.os_type, self.device_model, self.push_token, self.time_zone, self.device_id)

def get_user(user_id):
    user = User.query.filter_by(user_id=user_id).first()
    if not user:
        raise InvalidUsage('no such user_id')
    return user

def user_exists(user_id):
    user = User.query.filter_by(user_id=user_id).first()
    return True if user else False

def create_user(user_id, os_type, device_model, push_token, time_zone, device_id):
    '''create a new user and commit to the database. should only fail if the userid is duplicate'''
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

def update_user_token(user_id, push_token):
    '''updates the user's token with a new one'''
    user = get_user(user_id)
    print('user:%s', user)
    user.push_token = push_token
    db.session.add(user)
    db.session.commit()

def list_all_users():
    '''returns a dict of all the whitelisted users and their PAs (if available)'''
    response = {}
    users = User.query.order_by(User.user_id).all()
    for user in users:
        response[user.user_id] = {'sid': user.sid, 'os': user.os_type, 'push_token': user.push_token, 'timezone': user.time_zone, 'device_id': user.device_id, 'device_model': user.device_model}
    return response
