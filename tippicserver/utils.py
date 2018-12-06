from uuid import uuid4

import logging as log
from datadog import statsd
from flask import config
import os
import requests
import phonenumbers
import redis
import json
import random
import arrow
from tippicserver import config, app


ERROR_ORDERS_COOLDOWN = -1
ERROR_NO_GOODS = -2

KINIT_MEMO_PREFIX = '1-kit-'
ORDER_ID_LENGTH = 21

OS_ANDROID = 'android'
OS_IOS = 'iOS'

DEFAULT_MIN_CLIENT_VERSION = '0.1'

MAX_TXS_PER_USER = 100

REDIS_USERID_PREFIX = 'userid'


def generate_memo(is_manual=False):
    # generate a unique-ish id for txs, this goes into the memo field of txs
    env = config.DEPLOYMENT_ENV[0:1]  # either 's(tage)', 't(est)' or 'p(rod)'
    if is_manual:
        # indicates that the memo was generate for a manual transaction
        env = 'm'
    return KINIT_MEMO_PREFIX + env + str(uuid4().hex[:ORDER_ID_LENGTH])  # generate a memo string and send it to the client


def increment_metric(metric_name, count=1):
    """increment a counter with the given name and value"""
    # set env to undefined for local tests (which do not emit stats, as there's no agent)
    statsd.increment(metric_name, count, tags=['app:tippic,env:%s' % config.DEPLOYMENT_ENV])


def gauge_metric(metric_name, value, tags_str=''):
    """increment a counter with the given name and value"""
    # set env to undefined for local tests (which do not emit stats, as there's no agent)
    tags = 'app:tippic,env:%s' % config.DEPLOYMENT_ENV
    if tags_str:
        tags = tags + ',' + tags_str
    statsd.gauge(metric_name, value, tags=[tags])


def errors_to_string(errorcode):
    """ translate error codes to human-readable reasons """
    if errorcode == ERROR_ORDERS_COOLDOWN:
        return 'orders-cooldown'
    elif errorcode == ERROR_NO_GOODS:
        return 'no-goods'
    else:
        log.error('should never happen')
        return 'unknown-error'


def seconds_to_local_nth_midnight(tz_shift, delay_days):
    """ return the (integer) number of seconds to the next nth midnight at utc """
    from datetime import datetime, timedelta
    # get a datetime of the local (time-zone shifted) time:
    local_time_dt = (datetime.utcnow() + timedelta(hours=tz_shift))
    # get the next local day as date object:
    local_tomorrow_date = datetime.date(local_time_dt + timedelta(days=delay_days))
    # convert date object back to datetime. hack from https://stackoverflow.com/a/27760382/1277048
    tomorrow_dt = datetime.strptime(local_tomorrow_date.strftime('%Y%m%d'), '%Y%m%d') + timedelta(seconds=5)
    # calc hours until tomorrow
    return int((tomorrow_dt - local_time_dt).total_seconds())


def get_global_config():
    """return a dict with global flags for the clients"""
    d = {}
    d['phone_verification_enabled'] = config.PHONE_VERIFICATION_ENABLED
    d['auth_token_enabled'] = config.AUTH_TOKEN_ENABLED
    d['p2p_enabled'] = config.P2P_TRANSFERS_ENABLED
    d['p2p_min_kin'] = config.P2P_MIN_KIN_AMOUNT
    d['p2p_max_kin'] = config.P2P_MAX_KIN_AMOUNT
    d['backup_nag'] = True
    if config.TOS_URL is not '':
        d['tos'] = config.TOS_URL
    if config.FAQ_URL is not '':
        d['faq_url'] = config.FAQ_URL
    d['is_update_available'] = False
    d['force_update'] = False
    return d


def extract_phone_number_from_firebase_id_token(id_token):
    """get the phone number from a firebase id-token"""
    phone_number = None
    try:
        from firebase_admin import auth
        decoded_token = auth.verify_id_token(id_token)
        phone_number = decoded_token['phone_number']
    except Exception as e:
        log.error('failed to decode the firebase token: %s' % e)
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
        log.error('could not get url: %s' % (url, e))
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
            log.error('could not verify file at %s' % processed_url)
            fail_flag = True

    # ios
    dot_index = split_path[1].find('.')
    for resolution in ('', '@2x', '@3x'):
        processed_url = split_path[0] + '/ios/' + split_path[1][:dot_index] + resolution + split_path[1][dot_index:]
        if not test_url(processed_url):
            log.error('could not verify file at %s' % processed_url)
            fail_flag = True

    if fail_flag:
        log.error('could not fully verify image %s' % url)
        return False
    return True


def sqlalchemy_pool_status():
    """returns and prints a dict with various db stats"""
    from tippicserver import db
    from sqlalchemy.pool import QueuePool
    pool_size = QueuePool.size(db.engine.pool)
    checkedin = QueuePool.checkedin(db.engine.pool)
    overflow = QueuePool.overflow(db.engine.pool)
    checkedout = QueuePool.checkedout(db.engine.pool)

    log.info("Pool size: %d  Connections in pool: %d " \
           "Current Overflow: %d Current Checked out " \
           "connections: %d" % (pool_size, checkedin, overflow, checkedout))
    return {'pool_size': pool_size, 'checkedin': checkedin, 'overflow': overflow, 'checkedout': checkedout}


def parse_phone_number(number_to_parse, sender_number):
    """try to convert a raw input phone number into e.164"""
    #  first, try to parse the number as-is:
    parsed_number = parse_phone_number_naively(number_to_parse)
    if parsed_number:
        log.info('parse_phone_number: naively parsed phone number')
        return parsed_number

    # try to parse with the sender's number as a clue
    if sender_number:
        parsed_number = parse_phone_number_by_sender_country_code(sender_number, number_to_parse)
        if parsed_number:
            log.info('parse_phone_number: parsed phone number by sender_number')
            return parsed_number

    # give up, just return the original number:
    log.error('parse_phone_number: failed to parse phone number. returning raw number')
    return number_to_parse


def parse_phone_number_naively(number_to_parse):
    """naively attempt to format a number into e.164. should fail (return None) for local numbers"""
    try:
        formatted_sent_number = phonenumbers.parse(number_to_parse, None)
    except phonenumbers.NumberParseException as e:
        log.error('parse_phone_number_naively: cant parse number')
        return None
    else:
        return phonenumbers.format_number(formatted_sent_number, phonenumbers.PhoneNumberFormat.E164)


def parse_phone_number_by_sender_country_code(sender_number, number_to_parse):
    """this function attempts to format the given 'sent_number' into a phone_number,
    based on the the 'sender_number''s country code"""
    try:
        formatted_sender_number = phonenumbers.parse(sender_number, None)
        country_code = formatted_sender_number.country_code
        formatted_sent_number = phonenumbers.parse(number_to_parse, phonenumbers.region_code_for_country_code(country_code))
    except phonenumbers.NumberParseException as e:
        log.error('parse_phone_number_by_sender_country_code: cant parse number with sender\'s country code')
        return None
    else:
        return phonenumbers.format_number(formatted_sent_number, phonenumbers.PhoneNumberFormat.E164)


def print_creation_statement():
    """prints out db creation statement. useful"""
    from sqlalchemy.schema import CreateTable
    from sqlalchemy.dialects import postgresql
    from .models import UserAppData, User, ACL, BackupQuestion, PhoneBackupHints, EmailTemplate, BlacklistedEncPhoneNumber, SystemConfig
    log.info(CreateTable(User.__table__).compile(dialect=postgresql.dialect()))
    log.info(CreateTable(UserAppData.__table__).compile(dialect=postgresql.dialect()))
    log.info(CreateTable(ACL.__table__).compile(dialect=postgresql.dialect()))
    log.info(CreateTable(BackupQuestion.__table__).compile(dialect=postgresql.dialect()))
    log.info(CreateTable(PhoneBackupHints.__table__).compile(dialect=postgresql.dialect()))
    log.info(CreateTable(EmailTemplate.__table__).compile(dialect=postgresql.dialect()))
    log.info(CreateTable(BlacklistedEncPhoneNumber.__table__).compile(dialect=postgresql.dialect()))
    log.info(CreateTable(SystemConfig.__table__).compile(dialect=postgresql.dialect()))



def random_string(length=8):
    return ''.join(random.choice('0123456789ABCDEF') for i in range(length))


def random_percent():
    return random.randint(0, 100)


def read_json_from_cache(key):
    try:
        data = app.redis.get(key)
        if not data:
            raise InternalError('could not find key %s in cache' % key)
        return json.loads(data.decode())
    except Exception as e:
        log.error('could not read json data from cache with key %s. e=%s. data=%s' % (key, e, data))
        return None


def write_json_to_cache(key, val, ttl=30*60):
    if val is None:
        log.error('write_json_to_cache: refusing to store None value')
        return False
    try:
        app.redis.setex(key, ttl, json.dumps(val))
        return True
    except Exception as e:
        log.error('failed to write json data to cache with key %s and value %s. exception: %s' % (key, val, e))
        return False


def write_payment_data_to_cache(memo, user_id, task_id, timestamp, send_push=True):
    return write_json_to_cache('memo:%s' % memo, {'user_id': str(user_id), 'task_id': str(task_id), 'timestamp': timestamp, 'send_push': send_push})


def read_payment_data_from_cache(memo):
    data = read_json_from_cache('memo:%s' % memo)
    return data['user_id'], data['task_id'], data['timestamp'], data['send_push']


def passed_captcha(captcha_token):
    """get and parse a re-captcha result"""
    try:
        params = {
            'secret': app.recaptcha_secret,
            'response': captcha_token,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded", "charset": "utf-8"}
        res = requests.post('https://www.google.com/recaptcha/api/siteverify', params=params, headers=headers)
        res.raise_for_status()
    except Exception as e:
        #TODO add retry
        log.error('caught exception (%s) getting captcha results from google')
        return False
    else:
        try:
            captcha_result = json.loads(res.text)

            if config.DEBUG:
                log.info('setting fake successful captcha results for debug configuration')
                captcha_result ={'apk_package_name': config.APK_PACKAGE_NAME, 'challenge_ts': str(arrow.utcnow()), 'success': True}

            apk_name = captcha_result.get('apk_package_name', None)
            challenge_ts = captcha_result.get('challenge_ts', None)
            captcha_success = captcha_result.get('success', None)
            if None in (apk_name, challenge_ts, captcha_success) and not config.DEBUG:
                log.error('missing fields in captcha result')
                return False

            if apk_name != config.APK_PACKAGE_NAME:
                log.error('failed captcha results: invalid apk name: %s' % captcha_result['apk_package_name'])
                return False

            captcha_secs_ago = (arrow.get(challenge_ts) - arrow.utcnow()).total_seconds()
            if captcha_secs_ago > config.CAPTCHA_STALE_THRESHOLD_SECS:
                log.error('failed captcha results: solved %s secs ago' % captcha_secs_ago)
                return False

            if captcha_success:
                return True

        except Exception as e:
            log.error('failed processing captcha. e: %s' % e)

    return False


def get_country_code_by_ip(ip_addr):
    try:
        if not ip_addr:
            return None
        return app.geoip_reader.get(ip_addr)['country']['iso_code']
    except Exception as e:
        log.error('cant convert ip %s to country code' % ip_addr)

        return None


def commit_json_changed_to_orm(obj_to_commit, changed_fields_list):
    from tippicserver import db
    # turns out sqlalchemy cant detect json updates, and requires manual flagging:
    # https://stackoverflow.com/questions/30088089/sqlalchemy-json-typedecorator-not-saving-correctly-issues-with-session-commit/34339963#34339963
    from sqlalchemy.orm.attributes import flag_modified
    for field_name in changed_fields_list:
        flag_modified(obj_to_commit, field_name)
    db.session.add(obj_to_commit)
    db.session.commit()
