from kinappserver import db
import logging as log
from kinappserver.utils import InvalidUsage, OS_ANDROID, OS_IOS
from distutils.version import LooseVersion


class SystemConfig(db.Model):
    """SytemConfig is a table with various configuration options that are coded into the db"""
    sid = db.Column(db.Integer(), db.Sequence('sid', start=1, increment=1), primary_key=True)
    block_clients_below_version_android = db.Column('block_clients_below_version_android', db.String(100), nullable=False, primary_key=False)
    block_clients_below_version_ios = db.Column('block_clients_below_version_ios', db.String(100), nullable=False, primary_key=False)
    update_available_below_version_android = db.Column('update_available_below_version_android', db.String(100), nullable=False, primary_key=False)
    update_available_below_version_ios = db.Column('update_available_below_version_ios', db.String(100), nullable=False, primary_key=False)
    categories_extra_data = db.Column(db.JSON)  # all sorts of extra global data pertaining to categories

#TODO cache this to sace sql access
def get_system_config():
    try:
        return db.session.query(SystemConfig).one()
    except Exception as e:
        log.warning('get_system_config: cant find sysconfig in the db. returning default value. e:%s' % e)
        return None


def get_block_clients_below_version(os_type):
    sysconfig = get_system_config()
    if not sysconfig:
        #log.error('cant find value for block-clients-below in the db. using default')
        return '0'

    if os_type == OS_ANDROID:
        return sysconfig.block_clients_below_version_android
    elif os_type == OS_IOS:
        return sysconfig.block_clients_below_version_ios
    raise InvalidUsage('no such os_type: %s' % os_type)


def update_available_below_version(os_type):
    sysconfig = get_system_config()
    if not sysconfig:
        log.warning('cant find value for update-available-below in the db. using default')
        return '0'

    if os_type == OS_ANDROID:
        return sysconfig.update_available_below_version_android
    elif os_type == OS_IOS:
        return sysconfig.update_available_below_version_ios
    raise InvalidUsage('no such os_type: %s' % os_type)


def should_force_update(os, app_ver):
    if os == OS_ANDROID and LooseVersion(app_ver) < LooseVersion(get_block_clients_below_version(OS_ANDROID)):
            return True
    elif os == OS_IOS and LooseVersion(app_ver) < LooseVersion(get_block_clients_below_version(OS_IOS)):
            return True
    return False


def is_update_available(os, app_ver):
    if os == OS_ANDROID and LooseVersion(app_ver) < LooseVersion(update_available_below_version(OS_ANDROID)):
            return True
    elif os == OS_IOS and LooseVersion(app_ver) < LooseVersion(update_available_below_version(OS_IOS)):
            return True
    return False


def set_force_update_below(os_type, app_ver):
    """sets the given app_ver for the given os_type as into the db"""
    if os_type not in (OS_ANDROID, OS_IOS):
        raise InvalidUsage('invalid os type: %s' % os_type)
    if app_ver in (None, ''):
        raise InvalidUsage('invalid app_ver: %s' % app_ver)

    sysconfig = db.session.query(SystemConfig).one()
    if os_type == OS_ANDROID:
        sysconfig.block_clients_below_version_android = app_ver
    elif os_type == OS_IOS:
        sysconfig.block_clients_below_version_ios = app_ver
    db.session.add(sysconfig)
    db.session.commit()
    log.info('set force-update-below for os_type %s to %s' % (os_type, app_ver))


def set_update_available_below(os_type, app_ver):
    """sets the given app_ver for the given os_type as into the db"""
    if os_type not in (OS_ANDROID, OS_IOS):
        raise InvalidUsage('invalid os type: %s' % os_type)
    if app_ver in (None, ''):
        raise InvalidUsage('invalid app_ver: %s' % app_ver)

    sysconfig = db.session.query(SystemConfig).one()
    if os_type == OS_ANDROID:
        sysconfig.update_available_below_version_android = app_ver
    elif os_type == OS_IOS:
        sysconfig.update_available_below_version_ios = app_ver
    db.session.add(sysconfig)
    db.session.commit()
    log.info('set update-available-below for os_type %s to %s' % (os_type, app_ver))


def get_categories_extra_data():
    sys_config = get_system_config()
    if sys_config is None or sys_config.categories_extra_data is None:
        # return some hard coded default value
        import emoji
        sweet_text=emoji.emojize('Sweet! :love-you_gesture:')
        return {'no_tasks': {'title': sweet_text, 'subtitle': 'You\'re all done for today'}, 'default': {'title': 'Hi there', 'subtitle': 'Here are today\'s activities'}}
    return sys_config.categories_extra_data


def update_categories_extra_data(json_obj):
    import json
    db.engine.execute("update system_config set categories_extra_data=%s;", (json.dumps(json_obj),))
