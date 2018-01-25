'''The model for the Kin Wallet Service.'''
from uuid import uuid4
import datetime
import redis_lock

from kinwalletservice import db, config, app
from kinwalletservice.utils import InvalidUsage

class User(db.Model):
    '''
    '''
    user_id = db.Column(db.String(80), unique=True, nullable=True)

    def __repr__(self):
        return '<user_id: %s>' % (self.user_id)

def get_user(user_id):
    user = User.query.filter_by(user_id=user_id).first()
    if not user:
        raise InvalidUsage('no such user_id')
    return user


def user_exists(user_id):
    user = User.query.filter_by(user_id=user_id).first()
    return True if user else False


def create_user(user_id):
    if user_exists(user_id):
            raise InvalidUsage('refusing to create user. User-id %s already exists' % user_id)
    user = User()
    user.user_id = user_id
    db.session.add(user)
    db.session.commit()

def list_all_users():
    '''returns a dict of all the whitelisted users and their PAs (if available)'''
    response = {}
    users = User.query.order_by(User.user_id).all()
    for user in users:
        response[user.user_id] = ''
    return response
