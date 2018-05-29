import arrow

from kinappserver import db, config
from kinappserver.utils import InternalError
from sqlalchemy_utils import UUIDType, ArrowType
import uuid


class PushAuthToken(db.Model):
    """the PushAuth class hold data related to the push-authentication mechanism.
    """

    user_id = db.Column('user_id', UUIDType(binary=False), db.ForeignKey("user.user_id"), primary_key=True, nullable=False)
    authenticated = db.Column(db.Boolean, unique=False, default=False)
    send_date = db.Column(ArrowType)
    ack_date = db.Column(ArrowType)
    auth_token = db.Column(UUIDType(binary=False), unique=True, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now())

    def __repr__(self):
        return '<user_id: %s, authenticated: %s, send_date: %s, ack_date: %s, token: %s, updated_at: %s' % (self.user_id, self.authenticated, self.send_date, self.ack_date, self.auth_token, self.updated_at)


def get_token_obj_by_user_id(user_id):
    """returns the token object for this user, and creates one if one doesn't exist"""
    push_auth_token = PushAuthToken.query.filter_by(user_id=user_id).first()
    if not push_auth_token:
        # create one on the fly. throws exception if the user doesn't exist
        return create_token(user_id)

    return push_auth_token


def create_token(user_id):
    """create an authentication token for the given user_id"""
    try:
        push_auth_token = PushAuthToken()
        push_auth_token.user_id = user_id
        push_auth_token.auth_token = uuid.uuid4()
        push_auth_token.authenticated = False

        db.session.add(push_auth_token)
        db.session.commit()
    except Exception as e:
        print('cant add PushAuthToken to db with id %s. e:%s' % (user_id, e))
    else:
        return push_auth_token


def refresh_token(user_id):
    """regenerate the token"""
    push_auth_token = get_token_obj_by_user_id(user_id)
    push_auth_token.auth_token = uuid.uuid4()

    db.session.add(push_auth_token)
    db.session.commit()


def set_send_date(user_id):
    """update the send_date for this user_id's token"""
    push_auth_token = get_token_obj_by_user_id(user_id)
    push_auth_token.send_date = arrow.utcnow()

    db.session.add(push_auth_token)
    db.session.commit()
    return True


def ack_auth_token(user_id, token):
    """called when a user acks a push token

    returns true if all went well, false otherwise
    """
    push_auth_token = get_token_obj_by_user_id(user_id)
    if str(push_auth_token.auth_token) == str(token):
        print('user_id %s successfully acked the push token' % user_id)
        set_ack_date(user_id)
        return True
    else:
        print('user_id %s failed to ack the (internal) push token: %s with this token %s' % (user_id, str(push_auth_token.auth_token), token))
        return False


def set_ack_date(user_id):
    """update the ack_date for this user_id's token"""
    push_auth_token = get_token_obj_by_user_id(user_id)
    push_auth_token.ack_date = arrow.utcnow()
    push_auth_token.authenticated = True

    db.session.add(push_auth_token)
    db.session.commit()


def get_token_by_user_id(user_id):
    """return the token uuid itself for this user_id"""
    push_auth_token = get_token_obj_by_user_id(user_id)
    if push_auth_token:
        return push_auth_token.auth_token


def print_auth_tokens():
    print('printing all auth tokens:')
    push_auth_tokens = PushAuthToken.query.all()
    for token in push_auth_tokens:
        print(token)
    return {str(token.user_id): str(token.auth_token) for token in push_auth_tokens}


def should_send_auth_token(user_id):
    """determines whether a user should be sent an auth push token"""
    if not config.AUTH_TOKEN_ENABLED:
        return False

    token_obj = get_token_obj_by_user_id(user_id)
    if token_obj.send_date is None:
        # always send to a user that hasn't been sent yet
        return True

    # if more than AUTH_TOKEN_SEND_INTERVAL_DAYS passed, resend and refresh the token
    elif (arrow.utcnow() - token_obj.send_date).total_seconds() > 60*60*24*int(config.AUTH_TOKEN_SEND_INTERVAL_DAYS):
        print('refreshing auth token for user %s' % user_id)
        refresh_token()
        return True

    return False


def is_user_authenticated(user_id):
    """returns True if the user is currently authenticated"""
    token_obj = get_token_obj_by_user_id(user_id)
    return token_obj.authenticated
