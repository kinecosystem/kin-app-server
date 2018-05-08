from uuid import uuid4

from datadog import statsd
from flask import config
import os
import requests


from kinappserver import config


ERROR_ORDERS_COOLDOWN = -1
ERROR_NO_GOODS = -2

KINIT_MEMO_PREFIX = '1-kit-'
ORDER_ID_LENGTH = 21

OS_ANDROID = 'android'
OS_IOS = 'iOS'

DEFAULT_MIN_CLIENT_VERSION = '0.1'

MAX_TXS_PER_USER = 50


def generate_memo():
    # generate a unique-ish id for txs, this goes into the memo field of txs
    env = config.DEPLOYMENT_ENV[0:1]  # either 's(tage)', 't(est)' or 'p(rod)'
    return KINIT_MEMO_PREFIX + env + str(uuid4().hex[:ORDER_ID_LENGTH])  # generate a memo string and send it to the client


def increment_metric(metric_name, count=1):
    """increment a counter with the given name and value"""
    # set env to undefined for local tests (which do not emit stats, as there's no agent)
    statsd.increment('kinitapp.%s.%s' % (config.DEPLOYMENT_ENV, metric_name), count)


def errors_to_string(errorcode):
    """ translate error codes to human-readable reasons """
    if errorcode == ERROR_ORDERS_COOLDOWN:
        return 'orders-cooldown'
    elif errorcode == ERROR_NO_GOODS:
        return 'no-goods'
    else:
        print('should never happen')
        return 'unknown-error'


def seconds_to_local_nth_midnight(tz_shift, delay_days):
    """ return the (integer) number of seconds to the next nth midnight at utc """
    from datetime import datetime, timedelta
    # get a datetime of the local (time-zone shifted) time:
    local_time_dt = (datetime.utcnow() + timedelta(hours=tz_shift))
    # get the next local day as date object:
    local_tomorrow_date = datetime.date(local_time_dt + timedelta(days=delay_days))
    # convert date object back to datetime. hack from https://stackoverflow.com/a/27760382/1277048
    tomorrow_dt = datetime.strptime(local_tomorrow_date.strftime('%Y%m%d'), '%Y%m%d')
    # calc hours until tomorrow
    return int((tomorrow_dt - local_time_dt).total_seconds())


def get_global_config():
    """return a dict with global flags for the clients"""
    d = {}
    d['phone_verification_enabled'] = config.PHONE_VERIFICATION_ENABLED
    d['auth_token_enabled'] = config.AUTHENTICATION_TOKEN_ENABLED
    d['p2p_enabled'] = config.P2P_TRANSFERS_ENABLED
    d['p2p_min_kin'] = config.P2P_MIN_KIN_AMOUNT
    d['p2p_max_kin'] = config.P2P_MAX_KIN_AMOUNT
    d['p2p_min_tasks'] = config.P2P_MIN_TASKS
    if config.TOS_URL is not '':
        d['tos'] = config.TOS_URL
    return d


def extract_phone_number_from_firebase_id_token(id_token):
    """get the phone number from a firebase id-token"""
    phone_number = None
    try:
        from firebase_admin import auth
        decoded_token = auth.verify_id_token(id_token)
        phone_number = decoded_token['phone_number']
    except Exception as e:
        print('failed to decode the firebase token: %s' % e)
    return phone_number


class InvalidUsage(Exception):
    status_code = 400

    def __init__(self, message, status_code=None, payload=None):
        Exception.__init__(self)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv['message'] = self.message
        return rv


class InternalError(Exception):
    status_code = 500

    def __init__(self, message, status_code=None, payload=None):
        Exception.__init__(self)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv['message'] = self.message
        return rv


def test_url(url):
    """returns true iff the given url is accessible"""
    try:
        requests.get(url).raise_for_status()
    except Exception as e:
        print(e)
        print('could not get url: %s' % url)
        return False
    else:
        return True


def test_image(url):
    """ensures that the given url is accessible for both android and ios

    returns True if all's well, False otherwise
    """
    fail_flag = False
    split_path = os.path.split(url)
    # android:
    for resolution in ('hdpi', 'mdpi', 'xhdpi', 'xxhdpi', 'xxxhdpi'):
        processed_url = split_path[0] + '/android/' + resolution + '/' + split_path[1]
        if not test_url(processed_url):
            print('could not verify file at %s' % processed_url)
            fail_flag = True

    # ios
    dot_index = split_path[1].find('.')
    for resolution in ('', '@2x', '@3x'):
        processed_url = split_path[0] + '/ios/' + split_path[1][:dot_index] + resolution + split_path[1][dot_index:]
        if not test_url(processed_url):
            print('could not verify file at %s' % processed_url)
            fail_flag = True

    if fail_flag:
        print('could not fully verify image %s' % url)
        return False
    return True


def sqlalchemy_pool_status():
    """returns and prints a dict with various db stats"""
    from kinappserver import db
    from sqlalchemy.pool import QueuePool
    pool_size = QueuePool.size(db.engine.pool)
    checkedin = QueuePool.checkedin(db.engine.pool)
    overflow = QueuePool.overflow(db.engine.pool)
    checkedout = QueuePool.checkedout(db.engine.pool)

    print("Pool size: %d  Connections in pool: %d " \
           "Current Overflow: %d Current Checked out " \
           "connections: %d" % (pool_size, checkedin, overflow, checkedout))
    return {'pool_size': pool_size, 'checkedin': checkedin, 'overflow': overflow, 'checkedout': checkedout}
