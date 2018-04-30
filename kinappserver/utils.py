from uuid import uuid4

from datadog import statsd
from flask import config

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
    env = config.DEPLOYMENT_ENV[0:1] # either 's(tage)', 't(est)' or 'p(rod)'
    return KINIT_MEMO_PREFIX + env + str(uuid4().hex[:ORDER_ID_LENGTH]) # generate a memo string and send it to the client


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
