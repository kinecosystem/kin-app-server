import uuid

from kinappserver import amqp_publisher, config
from kinappserver.utils import InvalidUsage, OS_IOS, OS_ANDROID, increment_metric



def generate_push_id():
    return uuid.uuid4().hex


def engagement_payload_apns(push_type):
    push_id = generate_push_id()
    # TODO report push_id
    if push_type in ('engage-recent', 'engage-week'):
        return apns_payload("", "Let's earn some Kin!", push_type, push_id)


def engagement_payload_gcm(push_type):
    push_id = generate_push_id()
    # TODO report push_id
    if push_type in ('engage-recent', 'engage-week'):
        return gcm_payload(push_type, push_id, {'title': '', 'body': "Let's earn some Kin!"})
    else:
        raise InvalidUsage('no such push type: %s' % push_type)


def compensated_payload_apns(amount, task_title):
    push_id = generate_push_id()
    # TODO report push_id
    return apns_payload("", "You have been awarded %s KIN for completing task \"%s\"" % (amount, task_title), 'engage-recent', push_id)


def compensated_payload_gcm(amount, task_title):
    push_id = generate_push_id()
    return gcm_payload('engage-recent', push_id, {'title': '', 'body': "You have been awarded %s KIN for completing task \"%s\"" % (amount, task_title)})


def send_please_upgrade_push(user_id):
    """sends a push to the given userid to please upgrade"""
    push_id = generate_push_id()
    push_type = 'please_upgrade'
    from kinappserver.models import get_user_push_data
    os_type, token = get_user_push_data(user_id)
    if token:
        if os_type == OS_ANDROID:
            increment_metric('pleaseupgrade-android')
            return  # not supported yet
            # print('sending please-upgrade push message to GCM user %s' % user_id)
            # send_gcm(token, gcm_payload(push_type, push_id, {'title': '', 'body': "Please upgrade the app to get the next task"}))
        else:
            increment_metric('pleaseupgrade-ios')
            print('sending please-upgrade push message to APNS user %s' % user_id)
            send_apns(token, apns_payload("", "Please upgrade the app to get the next task", push_type, push_id))
    else:
        print('not sending please-upgrade push to user_id %s: no token' % user_id)
    return


def apns_payload(title, body, push_type, push_id, sound='default'):
    """generate an apns payload"""
    payload_dict = {'aps': {'alert': {'title': title, 'body': body}, 'sound': sound}, 'kin': {'push_type': push_type, 'push_id': push_id}}

    print('the payload: %s' % payload_dict)
    return payload_dict


def gcm_payload(push_type, push_id, message_dict):
    payload = {
            'push_type': push_type,
            'push_id': push_id,
            'message': message_dict
        }
    return payload


def send_gcm(token, payload):
    amqp_publisher.send_gcm("eshu-key", payload, [token], False, config.GCM_TTL_SECS)


def send_apns(token, payload):
    amqp_publisher.send_apns("eshu-key", payload, [token])
