
import datetime
from kinappserver import db


class BlackhawkCreds(db.Model):
    """the BlackhawkCreds class stores info needed to connect to the OmniCodes API.

    most creds are static, but the auth_token needs to be replaced every 7 days.
    """
    account_id = db.Column(db.Integer(), primary_key=True)
    auth_token = db.Column(db.String(40), primary_key=False, nullable=True)
    username = db.Column(db.String(40), primary_key=False, nullable=True)
    password = db.Column(db.String(40), primary_key=False, nullable=True)
    digital_signature = db.Column(db.String(40), primary_key=False, nullable=True)
    token_generation_time = db.Column(db.DateTime(timezone=True))

    def __repr__(self):
        return '<token: %s, token_generation_time: %s>' % (self.auth_token, self.token_generation_time)


def replace_bh_token(new_token):
    """replaces the old token with a new one"""
    creds = db.session.query(BlackhawkCreds).one()
    creds.auth_token = new_token
    creds.token_generation_time = datetime.datetime.utcnow()
    db.session.add(creds)
    db.session.commit()
    return True


def get_bh_creds():
    """return the blackhawk credentials"""
    creds = db.session.query(BlackhawkCreds).one()
    d = {}
    d['account_id'] = creds.account_id
    d['token'] = creds.auth_token
    d['digital_signature'] = creds.digital_signature
    d['username'] = creds.username
    d['password'] = creds.password
    d['token_generation_time'] = creds.token_generation_time

    return d


def init_bh_creds(account_id, username, password, digital_signature):
    """creates an initial creds object, sans the token"""
    creds = BlackhawkCreds()
    creds.account_id = account_id
    creds.username = username
    creds.password = password
    creds.digital_signature = digital_signature

    db.session.add(creds)
    db.session.commit()
